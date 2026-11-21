//! One versioned document behind both structured settings and the text editor.

use crate::{
    configuration::{self, Document},
    ini,
};
use std::io;

//--------//
// BEGIN: ConfigurationDocumentSession
pub(super) struct Session {
    pub target: String,
    pub document: Option<Document>,
    pub error: String,
    pub demo: bool,
    pub saved: bool,
}

impl Session {
    pub fn new(target: &str, demo: bool) -> Self {
        let mut session = Self {
            target: target.into(),
            document: None,
            error: String::new(),
            demo,
            saved: false,
        };
        if demo {
            session.document = Some(Document {
                content: preview_ini(),
                revision: "preview".into(),
                label: "Preview INI (session only)".into(),
            });
        } else {
            session.reload();
        }
        session
    }
    pub fn reload(&mut self) {
        if self.demo {
            return;
        }
        match configuration::read(&self.target) {
            Ok(document) => {
                self.document = Some(document);
                self.error.clear();
            }
            Err(error) => {
                self.document = None;
                self.error = error.to_string();
            }
        }
    }
    pub fn text(&self) -> &str {
        self.document.as_ref().map_or("", |d| d.content.as_str())
    }
    pub fn save(&mut self, content: String) -> io::Result<()> {
        let document = self
            .document
            .as_ref()
            .ok_or_else(|| io::Error::other("No configuration loaded"))?;
        if self.target == "ini" {
            ini::validate(&content)?;
        } else {
            let _: serde_json::Value = serde_json::from_str(&content)?;
        }
        let updated = if self.demo {
            Document {
                content,
                ..document.clone()
            }
        } else {
            configuration::save(&self.target, &document.revision, content)?
        };
        self.document = Some(updated);
        self.saved = true;
        self.error.clear();
        Ok(())
    }
    pub fn patch(&mut self, changes: &[(String, String, String)]) -> io::Result<()> {
        let mut content = self.text().to_owned();
        for (section, key, value) in changes {
            content = ini::set(&content, section, key, value)?;
        }
        self.save(content)
    }
}

// END: ConfigurationDocumentSession
//--------//

fn preview_ini() -> String {
    let mut text = String::from("# Isolated preview. No machine connection.\n[EMC]\nMACHINE = PA Preview\n[KINS]\nJOINTS = 5\nKINEMATICS = trivkins coordinates=XYZAB\n[TRAJ]\nCOORDINATES = XYZAB\nLINEAR_UNITS = mm\nANGULAR_UNITS = degree\n[PA_CAM]\nDIMENSION_SOURCE = axis_travel\nTABLE_X_MM = 400\nTABLE_Y_MM = 300\nTABLE_Z_MM = 100\n");
    for (index, (axis, min, max)) in [
        ("X", "-0.100", "410.000"),
        ("Y", "0", "310"),
        ("Z", "-100", "0"),
        ("A", "-180", "180"),
        ("B", "-90", "90"),
    ]
    .iter()
    .enumerate()
    {
        text.push_str(&format!("\n[AXIS_{axis}]\nMIN_LIMIT = {min}\nMAX_LIMIT = {max}\nMAX_VELOCITY = 25\nMAX_ACCELERATION = 100\n\n[JOINT_{index}]\nHOME_SEQUENCE = {index}\nHOME_SEARCH_VEL = 5\nHOME_LATCH_VEL = 1\nHOME_OFFSET = 0\nHOME = 0\n"));
    }
    text
}
