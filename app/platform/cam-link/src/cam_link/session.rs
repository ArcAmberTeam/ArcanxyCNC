use super::{
    config::Options,
    feedback::{self, Task, Writer},
    homing,
    inbox::Inbox,
    manual::Jog,
    protocol::{self, params, Error, Result},
    transfer::Transfer,
    wf_transhoming,
};
use serde_json::{json, Value};
use std::{collections::HashSet, sync::Arc, time::Duration};
use subtle::ConstantTimeEq;
use tokio::{
    io::{AsyncRead, AsyncWrite},
    sync::watch,
};

pub(super) struct Service {
    pub options: Options,
    pub token: Option<Vec<u8>>,
    pub inbox: Inbox,
    pub io: Duration,
    pub idle: Duration,
}
struct Session {
    service: Arc<Service>,
    writer: Writer,
    _output: Task,
    transfer: Transfer,
    jog: Jog,
    subscription: Option<Task>,
    failed: watch::Sender<bool>,
}
impl Session {
    async fn route(&mut self, method: &str, p: Value) -> Result<Value> {
        let service = &self.service;
        match method {
            "jog.start" | "jog.keepalive" | "jog.stop" => {
                self.jog
                    .request(&service.options.control_socket, method, p)
                    .await
            }
            "ping" => {
                params(&p, &[])?;
                Ok(json!({"alive":true}))
            }
            "upload.begin" | "upload.chunk" | "upload.finish" | "upload.abort"
            | "upload.receipt" => self.transfer.request(&service.inbox, method, p).await,
            "home.start" | "home.status" | "home.cancel" => {
                homing::request(&service.options, method, p).await
            }
            "workflow.start" | "workflow.status" | "workflow.cancel" | "job.start"
            | "job.status" | "job.cancel" => {
                wf_transhoming::request(&service.options, &service.inbox, method, p).await
            }
            "status.get" => {
                params(&p, &[])?;
                feedback::status(&service.options.control_socket, &service.inbox).await
            }
            "status.subscribe" => {
                params(&p, &["interval"])?;
                if !p["interval"]
                    .as_f64()
                    .is_some_and(|v| (1.0..=60.).contains(&v))
                {
                    return Err(Error::new(
                        "invalid_params",
                        "interval must be 1 to 60 seconds",
                    ));
                }
                // Abort before taking the writer lock; no old events after the ACK.
                self.unsubscribe().await;
                Ok(json!({"subscribed":true,"interval":p["interval"]}))
            }
            "status.unsubscribe" => {
                params(&p, &[])?;
                self.unsubscribe().await;
                Ok(json!({"subscribed":false}))
            }
            _ => Err(Error::new(
                "unsupported_method",
                "unsupported CAM Link method",
            )),
        }
    }
    async fn unsubscribe(&mut self) {
        if let Some(task) = self.subscription.take() {
            task.stop().await;
        }
    }
    fn subscribe(&mut self, interval: f64) {
        let service = self.service.clone();
        let writer = self.writer.clone();
        let failed = self.failed.clone();
        self.subscription = Some(Task(tokio::spawn(async move {
            loop {
                let mut event = json!({"version":2,"event":"machine.status"});
                match feedback::status(&service.options.control_socket, &service.inbox).await {
                    Ok(status) => event["data"] = status,
                    Err(error) => event["error"] = error.wire(),
                }
                if feedback::send(&writer, "STATUS", &event, service.io)
                    .await
                    .is_err()
                {
                    let _ = failed.send(true);
                    return;
                }
                tokio::time::sleep(Duration::from_secs_f64(interval)).await;
            }
        })));
    }
}
pub(super) async fn run<S: AsyncRead + AsyncWrite + Unpin + Send + 'static>(
    stream: S,
    service: Arc<Service>,
) -> Result<()> {
    let (reader, writer) = tokio::io::split(stream);
    let mut reader = tokio::io::BufReader::with_capacity(protocol::MAX_FRAME + 24, reader);
    let (failed, mut failure) = watch::channel(false);
    let (writer, output) = feedback::channel(writer, service.io, failed.clone());
    let mut session = Session {
        service: service.clone(),
        writer,
        _output: output,
        transfer: Transfer::default(),
        jog: Jog::default(),
        subscription: None,
        failed,
    };
    let mut authenticated = false;
    let mut ids = HashSet::new();
    loop {
        let request = tokio::select! {
            _=failure.changed()=>return Ok(()),
            request=protocol::read(&mut reader,if authenticated{service.idle}else{service.io},service.io)=>request,
        };
        let request = match request {
            Ok(request) => request,
            Err(error) => {
                if !matches!(error.code.as_str(), "io_error" | "timeout") {
                    feedback::send(
                        &session.writer,
                        "ERROR",
                        &json!({"version":2,"requestId":error.request_id,"error":error.wire()}),
                        service.io,
                    )
                    .await?;
                }
                session.jog = Jog::default();
                session.transfer = Transfer::default();
                session.unsubscribe().await;
                // Send FIN before discarding an invalid frame's unread body. This
                // preserves the error receipt instead of resetting TCP immediately.
                let _ = feedback::shutdown(&session.writer, service.io).await;
                return Ok(());
            }
        };
        let duplicate = ids.contains(&request.id);
        let limit = ids.len() >= 100000;
        let result = if duplicate {
            Err(Error::new("duplicate_request", "requestId was used"))
        } else if limit {
            Err(Error::new("session_limit", "reconnect to continue"))
        } else {
            ids.insert(request.id.clone());
            if !authenticated {
                let valid = request.method == "session.auth"
                    && match &service.token {
                        None => request.params == json!({}),
                        Some(token) => {
                            params(&request.params, &["token"]).is_ok()
                                && request.params["token"]
                                    .as_str()
                                    .is_some_and(|s| bool::from(s.as_bytes().ct_eq(token)))
                        }
                    };
                if valid {
                    authenticated = true;
                    Ok(json!({"authenticated":true}))
                } else {
                    Err(Error::new("unauthorized", "authenticate first"))
                }
            } else {
                session.route(&request.method, request.params).await
            }
        };
        match result {
            Ok(result) => {
                feedback::send(
                    &session.writer,
                    "REPLY",
                    &json!({"version":2,"requestId":request.id,"result":result}),
                    service.io,
                )
                .await?;
                if request.method == "status.subscribe" {
                    session.subscribe(result["interval"].as_f64().unwrap());
                }
            }
            Err(error) => {
                betterlinuxcnc_error_client::report("cam-link", &error.code, &error.message);
                if matches!(request.method.as_str(), "upload.chunk" | "upload.finish") && !duplicate
                {
                    session.transfer = Transfer::default();
                }
                feedback::send(
                    &session.writer,
                    "ERROR",
                    &json!({"version":2,"requestId":request.id,"error":error.wire()}),
                    service.io,
                )
                .await?;
            }
        }
        if !authenticated || limit {
            return Ok(());
        }
    }
}
