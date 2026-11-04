#[tokio::main]
async fn main() {
    if let Err(error) = betterlinuxcnc_services::run().await {
        betterlinuxcnc_error_client::report("cam-link", "operation_failed", &error.to_string());
        eprintln!("Cannot start CAM link service: {error}");
        std::process::exit(1);
    }
}
