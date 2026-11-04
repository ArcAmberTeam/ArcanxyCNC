pragma ComponentBehavior: Bound
import QtQuick
import BetterCnc.Ui 1.0
import BetterCnc.Chrome 1.0

Column {
    id: root
    property var machine: ({})
    property var updater: null
    property var mesaUpdate: null
    property var mesaFlash: null
    readonly property var mesaState: mesaUpdate ? mesaUpdate.state : ({phase: "not_checked", message: "Mesa 更新服务尚未安装"})
    readonly property var flashState: mesaFlash ? mesaFlash.state : ({phase: "not_checked", message: ""})
    readonly property bool flashing: ["scheduled", "checking", "verified", "verifying_identity", "writing", "verifying", "programmed_pending_power_cycle"].indexOf(flashState.phase) >= 0
    readonly property bool hasFirmware: ["release_available", "downloaded"].indexOf(mesaState.phase) >= 0
        && !!mesaState.manifest && mesaState.manifest.firmware?.available === true
        && !!mesaState.installed_app_version && mesaState.manifest.compatible_app_version === mesaState.installed_app_version
    readonly property var updateState: updater ? updater.state : ({phase: "idle", message: "更新服务尚未安装", progress: 0})
    readonly property bool updating: ["checking", "downloading", "verifying", "scheduled", "installing"].indexOf(updateState.phase) >= 0
    spacing: 0
    MachineStatus { id: status; machine: root.machine }
    readonly property var facts: [
        {label: "应用", value: Qt.application.name || "BetterLinuxCNC"},
        {label: "应用版本", value: (Qt.application.version || "—") + (root.updater && root.updater.selfCompiled ? "（自编译）" : "")},
        {label: "操作系统", value: ({osx: "macOS", linux: "Linux", windows: "Windows"})[Qt.platform.os] || Qt.platform.os},
        {label: "机床状态", value: status.label, tone: status.tone},
        {label: "机床名称", value: machine.connected ? machine.machineName || "—" : "—"},
        {label: "配置文件", value: machine.connected ? machine.iniPath || "—" : "—"},
        {label: "配置轴", value: machine.connected && machine.axes?.length ? machine.axes.join(" · ") : "—"}
    ]
    Repeater {
        model: root.facts
        Item {
            id: fact
            required property var modelData
            width: root.width; height: Math.max(56, value.implicitHeight + 28)
            UiText { y: 16; width: 116; text: fact.modelData.label; color: Theme.secondary }
            UiText {
                id: value
                objectName: "settings-about-" + fact.modelData.label
                x: 132; y: 16; width: parent.width - x
                text: fact.modelData.value
                color: fact.modelData.tone || Theme.text
                wrapMode: Text.WrapAnywhere
            }
            UiDivider { anchors.bottom: parent.bottom; width: parent.width }
        }
    }
    Column {
        width: parent.width
        topPadding: 24
        spacing: 16
        UiText { text: "应用更新"; font.pixelSize: 18; font.weight: Font.DemiBold }
        Row {
            spacing: 12
            UiButton {
                objectName: "settings-firmware-update"
                text: root.updating ? "正在更新…" : "检查应用更新"
                height: 44
                enabled: !!root.updater && !!root.updater.available && !root.updating
                onClicked: root.updater.fetch()
            }
            UiButton {
                objectName: "settings-firmware-install"
                text: "安装并重启"
                kind: "primary"; height: 44
                visible: root.updateState.phase === "ready"
                enabled: !!root.updater && !!root.updater.available && !root.machine.busy && !root.machine.powered
                onClicked: root.updater.install()
            }
        }
        Rectangle {
            width: parent.width; height: 4; radius: 2
            visible: root.updateState.phase === "downloading"
            color: Theme.border
            Rectangle {
                width: parent.width * Number(root.updateState.progress || 0) / 100
                height: parent.height; radius: parent.radius; color: Theme.accentFill
            }
        }
        UiText {
            objectName: "settings-firmware-status"
            width: parent.width
            visible: text.length > 0
            text: root.updateState.message || ""
            color: root.updateState.phase === "error" ? Theme.danger : Theme.secondary
            wrapMode: Text.Wrap
        }
    }
    Column {
        width: parent.width
        topPadding: 28
        spacing: 16
        UiText { text: "Mesa 控制板更新"; font.pixelSize: 18; font.weight: Font.DemiBold }
        UiButton {
            objectName: "settings-mesa-check"
            text: root.mesaState.phase === "checking" ? "正在检查…" : "检查配套更新"
            height: 44
            enabled: !!root.mesaUpdate && !!root.mesaUpdate.available && root.mesaState.phase !== "checking"
            onClicked: root.mesaUpdate.check()
        }
        UiText {
            objectName: "settings-mesa-version"
            width: parent.width
            text: "配套版本：" + (root.mesaState.available_version || "—")
            color: Theme.secondary
        }
        UiButton {
            objectName: "settings-mesa-flash"
            text: "停机并烧录控制板"
            height: 44
            visible: root.hasFirmware
            enabled: !!root.mesaFlash && !!root.mesaFlash.available && !root.flashing
                && !root.updating && !!root.machine.connected && !root.machine.busy && !root.machine.powered
            onClicked: root.mesaFlash.request()
        }
        UiText {
            objectName: "settings-mesa-flash-status"
            width: parent.width
            visible: text.length > 0
            text: root.flashState.message || ""
            color: root.flashState.phase === "error" ? Theme.danger : Theme.secondary
            wrapMode: Text.Wrap
        }
        UiText {
            objectName: "settings-mesa-status"
            width: parent.width
            text: root.mesaState.message || ""
            color: root.mesaState.phase === "error" ? Theme.danger : Theme.secondary
            wrapMode: Text.Wrap
        }
        UiText {
            width: parent.width
            text: "系统定时检测配套版本。检查更新不会停机或烧录控制板。"
            color: Theme.secondary
            wrapMode: Text.Wrap
        }
    }
}
