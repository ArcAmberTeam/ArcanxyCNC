pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs as NativeDialogs
import BetterCnc.Ui 1.0
import BetterCnc.Manual 1.0
import BetterCnc.Toolpath 1.0
import BetterCnc.Program 1.0
import BetterCnc.Chrome 1.0

Rectangle {
    id: workspace
    objectName: "workspace"
    color: Theme.base
    property string interfaceMode: "professional"
    property bool settingsOpen: false
    function openSettings() {
        stopJog(); settingsOpen = true; settings.focusBack();
    }
    function closeSettings() {
        settingsOpen = false; chrome.focusSettings();
    }
    property string guidedStage: "prepare"
    readonly property bool guided: interfaceMode === "guided"
    onInterfaceModeChanged: { stopJog(); if (!settingsOpen) forceActiveFocus(); }
    onGuidedStageChanged: { stopJog(); forceActiveFocus(); }
    property Item focusedItem: null
    property var backend: null
    property bool kioskMode: false
    readonly property var machine: backend && backend.snapshot ? backend.snapshot : ({})
    readonly property var program: backend ? backend.program : null
    readonly property string axesKey: (machine.axes || []).join(",")
    readonly property var configuredAxes: axesKey ? axesKey.split(",") : []
    property string lastConnectionMessage: ""
    readonly property string previewFailure: program && !program.previewBusy && program.previewError
        ? program.filePath + "\n" + program.previewError : ""
    onPreviewFailureChanged: if (previewFailure) errors.present(program.previewError, "preview")
    property var activeJogKeys: ({})
    readonly property bool popupActive: errors.visible || dialogs.visible || openFile.visible || saveFile.visible || programPicker.visible
    signal quitRequested()
    focus: true

    function stopJog() {
        activeJogKeys = ({});
        manualPanel.cancelJogGesture();
        if (backend) backend.stopJog();
    }
    function showBackendFailure(title, message) {
        if (dialogs.visible && (dialogs.actionId === "file.edit" || dialogs.actionId === "tool.edit"))
            dialogs.validationError = message;
        errors.present(message, title === "连接失败" ? "connection" : "operation");
    }
    function syncMachine() {
        const axes = machine.axes || [];
        if (axes.length && axes.indexOf(manualPresentation.selectedAxis) < 0)
            manualPresentation.selectedAxis = axes[0];
        if (machine.motionMode) manualPresentation.mode = machine.motionMode;
        const jointCount = Number(machine.jointCount || (machine.joints ? machine.joints.length : 0));
        if (manualPresentation.selectedJoint >= jointCount) manualPresentation.selectedJoint = 0;
        const maximum = Number(machine.jogMaxVelocity || machine.maxVelocity || 0) * 60;
        if (maximum > 0 && manualPresentation.jogVelocity <= 0)
            manualPresentation.jogVelocity = Math.min(maximum, machine.linearUnits === 1 ? 600 : 24);
        else if (maximum > 0 && manualPresentation.jogVelocity > maximum)
            manualPresentation.jogVelocity = maximum;
        if (!machine.connected) {
            stopJog();
            const reason = machine.message || "";
            if (!machine.connecting && reason && reason !== lastConnectionMessage) showBackendFailure("连接失败", reason);
            lastConnectionMessage = machine.connecting ? "" : reason;
        } else lastConnectionMessage = "";
    }
    function requestCommand(id, payload) {
        if (!backend) return;
        if (id !== "jog.start") stopJog();
        if (id === "file.open" || id === "file.open-sample") {
            if (payload.path) backend.openProgram(payload.path);
            else if (kioskMode) { programPicker.saveMode = false; programPicker.open(); }
            else openFile.open();
        } else if (id === "file.reload") backend.reloadProgram();
        else if (id === "file.save") {
            if (kioskMode) { programPicker.saveMode = true; programPicker.open(); }
            else saveFile.open();
        }
        else if (id === "file.quit") { if (!kioskMode) quitRequested(); }
        else if (id === "file.save-edits") {
            if (program) backend.saveProgram(program.filePath, payload.text);
        } else if (id === "tool.save") {
            backend.saveToolTableText(payload.text);
        } else if (id === "view.grid-custom") toolpathPresentation.setChoice("grid", payload.value + "mm");
        else backend.dispatch(id, payload);
    }
    onPopupActiveChanged: if (popupActive) stopJog()
    onBackendChanged: Qt.callLater(syncMachine)
    Connections {
        target: workspace.backend
        function onSnapshotChanged() { workspace.syncMachine(); }
        function onErrorOccurred(message) { workspace.stopJog(); workspace.showBackendFailure("操作失败", message); }
        function onNoticeOccurred(message) { dialogs.openMessage("操作提示", message); }
    }
    Connections {
        target: manualPresentation
        function onControlTabChanged() {
            workspace.stopJog();
            if (workspace.guided) workspace.guidedStage = "device";
            if (workspace.machine.connected)
                workspace.requestCommand("machine.mode", {mode: manualPresentation.controlTab});
        }
    }
    property int programHeight: height <= 640 ? 120 : 184
    property bool initialized: false
    readonly property int maximumProgramHeight: Math.max(90, Math.min(340, panes.height - 247))
    readonly property bool compact: width <= 900
    readonly property int sidebarWidth: compact ? 280 : 304
    readonly property bool menuOpen: chrome.menuOpen
    readonly property bool viewShortcutsEnabled: !settingsOpen && !popupActive && !chrome.menuOpen && !editing()

    function editing() {
        let item = focusedItem;
        while (item) {
            if (item instanceof TextInput || item instanceof TextEdit || item instanceof ComboBox)
                return true;
            item = item.parent;
        }
        return false;
    }
    function previewFocused() {
        let item = focusedItem;
        while (item) {
            if (item === toolpathPanel) return true;
            item = item.parent;
        }
        return false;
    }
    function setProgramHeight(value) {
        programHeight = Math.round(Math.max(90, Math.min(maximumProgramHeight, value)));
    }
    onMaximumProgramHeightChanged: if (initialized) setProgramHeight(programHeight)
    Component.onCompleted: {
        initialized = true;
        setProgramHeight(programHeight);
    }

    ProfessionalLayout {
        id: professionalLayout
        width: panes.width; height: panes.height
        sidebarWidth: workspace.sidebarWidth
        programHeight: workspace.programHeight
    }
    GuidedLayout {
        id: guidedLayout
        width: panes.width; height: panes.height
        sidebarWidth: workspace.sidebarWidth
        stage: workspace.guidedStage
    }
    readonly property WorkspaceLayout layout: guided ? guidedLayout : professionalLayout

    ManualState { id: manualPresentation; objectName: "manualState" }
    ToolpathState { id: toolpathPresentation; objectName: "toolpathState" }
    ChromeActions {
        id: chromeActions
        manual: manualPresentation
        preview: toolpathPresentation
        machine: workspace.machine
        program: workspace.program
        recentFiles: workspace.backend ? workspace.backend.recentFiles : []
        allowQuit: !workspace.kioskMode
        allowExternalTools: !workspace.kioskMode
        onCommandRequested: (actionId, payload) => workspace.requestCommand(actionId, payload)
        onDialogRequested: (actionId, title, axis) => dialogs.openDialog(actionId, title, axis)
    }
    ChromeBar {
        id: chrome
        width: parent.width
        height: implicitHeight
        visible: !workspace.settingsOpen
        compact: workspace.compact
        interfaceMode: workspace.interfaceMode
        guidedStage: workspace.guidedStage
        onSettingsRequested: workspace.openSettings()
        onStageRequested: stage => workspace.guidedStage = stage
        actions: chromeActions
        preview: toolpathPresentation
    }
    Item {
        id: panes
        visible: !workspace.settingsOpen
        x: Theme.gap
        y: chrome.height + Theme.gap
        width: parent.width - Theme.gap * 2
        height: parent.height - y - 40
        ManualPanel {
            id: manualPanel
            x: workspace.layout.manualRect.x; y: workspace.layout.manualRect.y
            width: workspace.layout.manualRect.width; height: workspace.layout.manualRect.height
            visible: workspace.layout.manualVisible
            presentation: manualPresentation
            machine: workspace.machine
            history: workspace.backend ? workspace.backend.history : []
            onCommandRequested: (actionId, payload) => workspace.requestCommand(actionId, payload)
            onJogStopRequested: workspace.stopJog()
            compact: workspace.compact
            onDialogRequested: (actionId, title, axis) => dialogs.openDialog(actionId, title, axis)
        }
        ToolpathPanel {
            id: toolpathPanel
            x: workspace.layout.previewRect.x; y: workspace.layout.previewRect.y
            width: workspace.layout.previewRect.width; height: workspace.layout.previewRect.height
            visible: workspace.layout.previewVisible
            presentation: toolpathPresentation
            machine: workspace.machine
            program: workspace.program
            compact: workspace.width <= 1100
        }
        Rectangle {
            id: sash
            objectName: "programSeparator"
            visible: workspace.layout.separatorVisible
            x: workspace.layout.programRect.x
            y: parent.height - workspace.programHeight - height
            width: workspace.layout.programRect.width
            height: 7
            color: Theme.base
            activeFocusOnTab: true
            Accessible.role: Accessible.Grip
            Accessible.name: "调整程序区高度"
            UiDivider { width: parent.width; height: 1 }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 2
                width: 26
                height: 2
                radius: 2
                color: sashMouse.containsMouse ? Theme.accent : Theme.borderControl
            }
            Rectangle { anchors.fill: parent; color: "transparent"; border.width: 2; border.color: Theme.accent; visible: sash.activeFocus }
            MouseArea {
                id: sashMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.SizeVerCursor
                preventStealing: true
                onPressed: sash.forceActiveFocus(Qt.MouseFocusReason)
                onPositionChanged: mouse => {
                    if (pressed) {
                        const point = mapToItem(panes, mouse.x, mouse.y);
                        workspace.setProgramHeight(panes.height - point.y);
                    }
                }
            }
            Keys.onUpPressed: workspace.setProgramHeight(workspace.programHeight + 10)
            Keys.onDownPressed: workspace.setProgramHeight(workspace.programHeight - 10)
        }
        ProgramPanel {
            machine: workspace.machine
            program: workspace.program
            onCommandRequested: (actionId, payload) => workspace.requestCommand(actionId, payload)
            x: workspace.layout.programRect.x; y: workspace.layout.programRect.y
            width: workspace.layout.programRect.width; height: workspace.layout.programRect.height
            visible: workspace.layout.programVisible
            onDialogRequested: (actionId, title, axis) => dialogs.openDialog(actionId, title, axis)
        }
    }
    WorkspaceGuide {
        x: panes.x + workspace.layout.guideRect.x
        y: panes.y + workspace.layout.guideRect.y
        width: workspace.layout.guideRect.width; height: workspace.layout.guideRect.height
        visible: !workspace.settingsOpen && workspace.guided && workspace.layout.guideVisible
        stage: workspace.guidedStage
        actions: chromeActions
        onStageRequested: stage => workspace.guidedStage = stage
    }
    WorkspaceStatus {
        visible: !workspace.settingsOpen
        anchors.bottom: parent.bottom
        width: parent.width
        machine: workspace.machine
    }
    WorkspaceSettings {
        id: settings
        anchors.fill: parent
        visible: workspace.settingsOpen
        interfaceMode: workspace.interfaceMode
        preview: toolpathPresentation
        actions: chromeActions
        firmwareUpdater: workspace.backend && workspace.backend.firmwareUpdater ? workspace.backend.firmwareUpdater : null
        mesaUpdate: workspace.backend && workspace.backend.mesaUpdate ? workspace.backend.mesaUpdate : null
        mesaFlash: workspace.backend && workspace.backend.mesaFlash ? workspace.backend.mesaFlash : null
        onBackRequested: workspace.closeSettings()
        onInterfaceModeRequested: mode => workspace.interfaceMode = mode
        onCommandRequested: (actionId, payload) => workspace.requestCommand(actionId, payload)
    }
    DialogHost {
        id: dialogs
        objectName: "dialogHost"
        machine: workspace.machine
        program: workspace.program
        touchTarget: manualPresentation.touchTarget
        toolTableText: workspace.backend ? workspace.backend.toolTableText : ""
        onSubmitted: (actionId, payload) => workspace.requestCommand(actionId, payload)
    }
    ErrorDialog { id: errors }
    NativeDialogs.FileDialog {
        id: openFile
        objectName: "openProgramDialog"
        title: "打开加工程序"
        nameFilters: ["加工程序 (*.ngc *.nc *.tap)", "所有文件 (*)"]
        fileMode: NativeDialogs.FileDialog.OpenFile
        onAccepted: if (workspace.backend) workspace.backend.openProgram(selectedFile.toString())
    }
    ProgramFilePicker {
        id: programPicker
        objectName: "programFilePicker"
        files: workspace.backend && workspace.backend.programFiles ? workspace.backend.programFiles : null
        onFileChosen: path => {
            if (!workspace.backend) return;
            if (saveMode && workspace.program) workspace.backend.saveProgram(path, workspace.program.text);
            else workspace.backend.openProgram(path);
        }
    }
    NativeDialogs.FileDialog {
        id: saveFile
        objectName: "saveProgramDialog"
        title: "程序另存为"
        nameFilters: ["加工程序 (*.ngc)", "所有文件 (*)"]
        fileMode: NativeDialogs.FileDialog.SaveFile
        defaultSuffix: "ngc"
        onAccepted: if (workspace.backend && workspace.program)
            workspace.backend.saveProgram(selectedFile.toString(), workspace.program.text)
    }
    WorkspaceShortcuts {
        settingsOpen: workspace.settingsOpen
        manualControlsEnabled: manualPanel.visible && !workspace.previewFocused()
        onManualRequested: if (workspace.guided) workspace.guidedStage = "device"
        popupActive: workspace.popupActive
        menuOpen: workspace.menuOpen
        viewShortcutsEnabled: workspace.viewShortcutsEnabled
        configuredAxes: workspace.configuredAxes
        machine: workspace.machine
        onCommandRequested: (actionId, payload) => workspace.requestCommand(actionId, payload)
        manual: manualPresentation
        preview: toolpathPresentation
        actions: chromeActions
    }
    Keys.onPressed: event => {
        if (!manualPanel.visible || workspace.previewFocused() || !workspace.viewShortcutsEnabled || manualPresentation.controlTab !== "manual" || event.isAutoRepeat) return;
        const keys = {};
        keys[Qt.Key_Left] = ["X", -1]; keys[Qt.Key_Right] = ["X", 1];
        keys[Qt.Key_Down] = ["Y", -1]; keys[Qt.Key_Up] = ["Y", 1];
        keys[Qt.Key_PageDown] = ["Z", -1]; keys[Qt.Key_PageUp] = ["Z", 1];
        const jointMode = manualPresentation.mode === "joint";
        const jog = jointMode ? (event.key === Qt.Key_Left ? [null, -1] : event.key === Qt.Key_Right ? [null, 1] : null) : keys[event.key];
        if (!jog || (!jointMode && (workspace.machine.axes || []).indexOf(jog[0]) < 0)) return;
        if (jointMode && !Number(workspace.machine.jointCount || (workspace.machine.joints ? workspace.machine.joints.length : 0))) return;
        if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) return;
        workspace.stopJog();
        if (!jointMode) manualPresentation.selectedAxis = jog[0];
        const pressed = {}; pressed[event.key] = true; workspace.activeJogKeys = pressed;
        manualPanel.startJog(jog[1]);
        event.accepted = true;
    }
    Keys.onReleased: event => {
        if (!event.isAutoRepeat && workspace.activeJogKeys[event.key]) {
            workspace.stopJog();
            event.accepted = true;
        }
    }

}
