pragma ComponentBehavior: Bound
import QtQuick
import BetterCnc.Manual 1.0
import BetterCnc.Toolpath 1.0
import BetterCnc.Chrome 1.0

Item {
    id: root
    property bool settingsOpen: false
    property bool manualControlsEnabled: true
    signal manualRequested(string mode)
    property bool popupActive: false
    property bool menuOpen: false
    property bool viewShortcutsEnabled: false
    property var configuredAxes: []
    property var machine: ({})
    signal commandRequested(string actionId, var payload)
    required property ManualState manual
    required property ToolpathState preview
    required property ChromeActions actions
    Shortcut { sequence: "F3"; enabled: !root.popupActive && !root.settingsOpen; onActivated: { root.manualRequested("manual"); root.manual.controlTab = "manual"; } }
    Shortcut { sequence: "F5"; enabled: !root.popupActive && !root.settingsOpen; onActivated: { root.manualRequested("mdi"); root.manual.controlTab = "mdi"; } }
    Repeater {
        model: root.configuredAxes
        delegate: Item {
            id: axisShortcut
            required property string modelData
            Shortcut {
                sequence: axisShortcut.modelData
                enabled: root.viewShortcutsEnabled && root.manualControlsEnabled
                onActivated: root.manual.selectedAxis = axisShortcut.modelData
            }
        }
    }
    Shortcut {
        sequence: "V"
        enabled: root.viewShortcutsEnabled
        onActivated: {
            const views = ["p", "z", "z2", "x", "y"];
            root.preview.setChoice("view", views[(views.indexOf(root.preview.choices.view) + 1) % views.length]);
        }
    }
    Shortcut { sequence: "D"; enabled: root.viewShortcutsEnabled; onActivated: root.preview.rotate = !root.preview.rotate }
    Shortcut { sequence: "!"; enabled: root.viewShortcutsEnabled; onActivated: root.preview.setChoice("units", root.preview.choices.units === "mm" ? "inch" : "mm") }
    Shortcut { sequence: "@"; enabled: root.viewShortcutsEnabled; onActivated: root.preview.setChoice("position", root.preview.choices.position === "actual" ? "commanded" : "actual") }
    Shortcut { sequence: "#"; enabled: root.viewShortcutsEnabled; onActivated: root.preview.setChoice("coordinates", root.preview.choices.coordinates === "relative" ? "machine" : "relative") }
    Shortcut { sequence: "F1"; autoRepeat: false; enabled: !!root.machine.connected; onActivated: root.actions.activate("machine.estop") }
    Shortcut { sequence: "F2"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("machine.power") }
    Shortcut { sequence: "O"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("file.open") }
    Shortcut { sequence: "Ctrl+R"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("file.reload") }
    Shortcut { sequence: "Ctrl+S"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("file.save") }
    Shortcut { sequence: "Ctrl+K"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("view.clear") }
    Shortcut { sequence: "R"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("program.run") }
    Shortcut { sequence: "T"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("program.step") }
    Shortcut { sequence: "P"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("program.pause") }
    Shortcut { sequence: "S"; autoRepeat: false; enabled: root.viewShortcutsEnabled; onActivated: root.actions.activate("program.resume") }
    Shortcut { sequence: "Escape"; autoRepeat: false; enabled: !root.popupActive && !root.menuOpen; onActivated: root.commandRequested("program.stop", {}) }
    Shortcut { sequence: "Home"; autoRepeat: false; enabled: root.manualControlsEnabled && root.viewShortcutsEnabled && !!root.machine.connected; onActivated: root.manual.mode === "joint" ? root.commandRequested("machine.home", {joint: root.manual.selectedJoint}) : root.actions.activate("machine.home-" + root.manual.selectedAxis) }
    Shortcut { sequence: "End"; autoRepeat: false; enabled: root.manualControlsEnabled && root.viewShortcutsEnabled; onActivated: root.actions.activate("machine.touch-off", "工件对刀") }
}
