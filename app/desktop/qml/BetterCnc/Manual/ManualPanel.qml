pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import BetterCnc.Ui 1.0

//--------//
// BEGIN: ManualOperationPanel
Rectangle {
    id: root

    required property ManualState presentation
    property bool compact: false
    property bool showModeTabs: true
    property bool showOverrides: true
    property bool showActiveCodes: true
    property var machine: ({})
    property var history: []
    readonly property bool connected: !!machine.connected
    // Records a held UI gesture, never inferred machine motion.
    property bool jogHeld: false
    readonly property bool jogSafe: connected && !!machine.powered && !machine.estop
        && machine.mode === "manual" && machine.motionMode === presentation.mode
    readonly property bool canOperate: connected && !!machine.powered && !machine.estop && !machine.busy
    readonly property string axesKey: (machine.axes || []).join(",")
    readonly property string jointsKey: (Array.isArray(machine.joints) ? machine.joints
        : Array.from({length: Number(machine.jointCount || 0)}, (_, index) => index)).join(",")
    readonly property var axes: axesKey ? axesKey.split(",") : []
    readonly property var joints: jointsKey ? jointsKey.split(",").map(Number) : []
    readonly property var selectionValues: presentation.mode === "joint" ? joints : axes
    readonly property string jogAxis: {
        if (presentation.mode !== "joint") return presentation.selectedAxis;
        const mapping = machine.jointMap || {};
        const matches = Object.keys(mapping).filter(axis => Array.isArray(mapping[axis])
            && mapping[axis].length === 1 && mapping[axis][0] === presentation.selectedJoint);
        return matches.length === 1 ? matches[0] : "";
    }
    readonly property bool rotaryJog: ["A", "B", "C"].indexOf(jogAxis) >= 0
    readonly property real jogSpeedLimit: {
        const limits = (machine.axisLimits || {})[jogAxis] || {};
        const axisMaximum = Number(limits.maxVelocity || 0);
        const linearMaximum = Number(machine.jogMaxVelocity || machine.maxVelocity || 0);
        // Derive the unit and limit from the same axis to avoid a transient zero
        // while dependent bindings settle when returning from C/A to X/Y/Z.
        if (["A", "B", "C"].indexOf(jogAxis) >= 0)
            return axisMaximum > 0 ? axisMaximum * 60 : 0;
        return (axisMaximum > 0 ? Math.min(axisMaximum, linearMaximum) : linearMaximum) * 60;
    }
    readonly property string jogSpeedUnit: rotaryJog ? "度/分钟"
        : jogAxis && machine.linearUnits === 1 ? "毫米/分钟" : "机床单位/分钟"
    readonly property bool canJog: jogSafe && canOperate && (presentation.mode === "joint"
        ? joints.indexOf(presentation.selectedJoint) >= 0 : axes.indexOf(presentation.selectedAxis) >= 0)
    signal dialogRequested(string actionId, string title, string axis)
    signal commandRequested(string actionId, var payload)
    signal jogStopRequested()

    function permitted(id) {
        return connected && (!machine.capabilities || machine.capabilities[id] !== false);
    }
    function limitJogSpeed() {
        if (presentation.jogVelocity > jogSpeedLimit) {
            releaseJog();
            presentation.jogVelocity = jogSpeedLimit;
        }
    }
    onJogSpeedLimitChanged: limitJogSpeed()
    function startJog(direction) {
        if (jogHeld || !canJog || !permitted("jog.start") || presentation.jogVelocity <= 0
            || presentation.jogVelocity > jogSpeedLimit) return;
        jogHeld = true;
        commandRequested("jog.start", {axis: presentation.mode === "joint" ? presentation.selectedJoint : presentation.selectedAxis, direction: direction,
            velocity: presentation.jogVelocity / 60, increment: presentation.jogIncrement,
            mode: presentation.mode});
    }
    function releaseJog() {
        jogHeld = false;
        jogStopRequested();
    }
    function cancelJogGesture() { jogHeld = false; }
    onVisibleChanged: if (!visible) releaseJog()
    onJogSafeChanged: if (!jogSafe) releaseJog()
    Connections {
        target: root.presentation
        function onControlTabChanged() { root.releaseJog(); }
        function onSelectedAxisChanged() { root.releaseJog(); }
        function onSelectedJointChanged() { root.releaseJog(); }
        function onModeChanged() { root.releaseJog(); }
        function onJogVelocityChanged() { root.limitJogSpeed(); }
    }

    objectName: "manualPanel"
    implicitWidth: compact ? 280 : 304
    color: Theme.sidebar
    radius: 0
    clip: true

    Connections {
        target: root.Window.window
        function onActiveChanged() { if (!root.Window.window.active) root.releaseJog(); }
        function onActiveFocusItemChanged() {
            const focused = root.Window.window.activeFocusItem;
            if (!focused) return;
            let ancestor = focused;
            while (ancestor && ancestor !== contentColumn) ancestor = ancestor.parent;
            if (!ancestor) return;
            const top = focused.mapToItem(contentColumn, 0, 0).y;
            const bottom = top + focused.height;
            const requested = top < scroller.contentY ? top
                : bottom > scroller.contentY + scroller.height ? bottom - scroller.height
                : scroller.contentY;
            scroller.contentY = Math.max(0, Math.min(scroller.contentHeight - scroller.height, requested));
        }
    }

    Flickable {
        id: scroller
        objectName: "manualScroller"
        anchors.fill: parent
        anchors.rightMargin: 1
        contentWidth: width
        contentHeight: contentColumn.height
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        clip: true
        ScrollBar.vertical: UiScrollBar {}

        Column {
            id: contentColumn
            width: scroller.width

            Item {
                width: parent.width
                visible: root.showModeTabs
                height: visible ? 44 : 0

                Row {
                    id: tabs
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4

                    function selectTab(tab) {
                        root.presentation.controlTab = tab;
                        (tab === "manual" ? manualTabButton : mdiTabButton).forceActiveFocus(Qt.TabFocusReason);
                    }

                    UiButton {
                        id: manualTabButton
                        objectName: "manualTab"
                        text: "手动操作 [F3]"
                        kind: "tab"
                        selected: root.presentation.controlTab === "manual"
                        Accessible.role: Accessible.PageTab
                        Accessible.name: text
                        onClicked: root.presentation.controlTab = "manual"
                        Keys.onLeftPressed: tabs.selectTab("mdi")
                        Keys.onRightPressed: tabs.selectTab("mdi")
                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                                tabs.selectTab(event.key === Qt.Key_Home ? "manual" : "mdi");
                                event.accepted = true;
                            }
                        }
                    }

                    UiButton {
                        id: mdiTabButton
                        objectName: "mdiTab"
                        text: "手动输入 [F5]"
                        kind: "tab"
                        selected: root.presentation.controlTab === "mdi"
                        Accessible.role: Accessible.PageTab
                        Accessible.name: text
                        onClicked: root.presentation.controlTab = "mdi"
                        Keys.onLeftPressed: tabs.selectTab("manual")
                        Keys.onRightPressed: tabs.selectTab("manual")
                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                                tabs.selectTab(event.key === Qt.Key_Home ? "manual" : "mdi");
                                event.accepted = true;
                            }
                        }
                    }
                }

                UiDivider {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                }
            }

            Item {
                id: manualArea
                readonly property int panelPadding: root.compact ? 12 : 18
                readonly property int verticalPadding: root.compact ? 12 : 16
                width: parent.width
                height: visible ? manualContent.height + verticalPadding * 2 : 0
                visible: root.presentation.controlTab === "manual"

                Column {
                    id: manualContent
                    x: manualArea.panelPadding
                    y: manualArea.verticalPadding
                    width: parent.width - manualArea.panelPadding * 2

                    RowLayout {
                        width: parent.width
                        height: 30
                        spacing: 7

                        UiText {
                            text: root.presentation.mode === "joint" ? "关节：" : "坐标轴："
                            font.pixelSize: Theme.labelSize
                            color: Theme.secondary
                            Layout.preferredWidth: 53
                            Layout.fillHeight: true
                            verticalAlignment: Text.AlignVCenter
                        }

                        RowLayout {
                            id: axisSelector
                            spacing: 5
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            function selectAxis(index) {
                                const next = (index + root.selectionValues.length) % root.selectionValues.length;
                                if (root.presentation.mode === "joint") root.presentation.selectedJoint = Number(root.selectionValues[next]);
                                else root.presentation.selectedAxis = String(root.selectionValues[next]);
                                axisRepeater.itemAt(next).forceActiveFocus(Qt.TabFocusReason);
                            }

                            Repeater {
                                id: axisRepeater
                                model: root.selectionValues

                                RadioButton {
                                    id: axisButton
                                    required property var modelData
                                    required property int index
                                    objectName: (root.presentation.mode === "joint" ? "joint" : "axis") + modelData
                                    text: String(modelData)
                                    checked: root.presentation.mode === "joint" ? root.presentation.selectedJoint === Number(modelData)
                                             : root.presentation.selectedAxis === String(modelData)
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Theme.controlHeight
                                    padding: 0
                                    hoverEnabled: true
                                    indicator: null
                                    Accessible.name: text

                                    contentItem: Item {
                                        Row {
                                            anchors.centerIn: parent
                                            spacing: 5

                                            UiSurface {
                                                width: 10
                                                height: 10
                                                anchors.verticalCenter: parent.verticalCenter
                                                radius: 5
                                                color: axisButton.checked ? Theme.accentFill : Theme.hover

                                                Rectangle {
                                                    anchors.centerIn: parent
                                                    width: 4
                                                    height: 4
                                                    radius: 2
                                                    color: "white"
                                                    visible: axisButton.checked
                                                }
                                            }

                                            UiText {
                                                text: axisButton.text
                                                font.family: Theme.mono
                                                font.pixelSize: 12
                                                color: axisButton.checked ? Theme.accent : Theme.text
                                            }
                                        }
                                    }

                                    background: UiSurface {
                                        focusHighlighted: axisButton.visualFocus
                                        pressed: axisButton.down
                                        color: axisButton.checked ? Theme.accentSoft : axisButton.hovered ? Theme.hover : Theme.input
                                    }

                                    onClicked: {
                                        if (root.presentation.mode === "joint") root.presentation.selectedJoint = Number(modelData);
                                        else root.presentation.selectedAxis = String(modelData);
                                    }
                                    Keys.onLeftPressed: axisSelector.selectAxis(index - 1)
                                    Keys.onRightPressed: axisSelector.selectAxis(index + 1)
                                    Keys.onUpPressed: axisSelector.selectAxis(index - 1)
                                    Keys.onDownPressed: axisSelector.selectAxis(index + 1)
                                }
                            }
                        }
                    }

                    Item {
                        width: 1
                        height: 12
                    }

                    RowLayout {
                        width: parent.width
                        height: 44
                        spacing: 6

                        JogButton {
                            objectName: "jogMinus"
                            text: "−"
                            Layout.preferredWidth: 48
                            Layout.preferredHeight: 44
                            Accessible.name: "负向点动"
                            enabled: root.jogHeld ? root.jogSafe : root.canJog && root.permitted("jog.start")
                            onJogPressed: root.startJog(-1)
                            onJogReleased: root.releaseJog()
                        }

                        JogButton {
                            objectName: "jogPlus"
                            text: "+"
                            Layout.preferredWidth: 48
                            Layout.preferredHeight: 44
                            Accessible.name: "正向点动"
                            enabled: root.jogHeld ? root.jogSafe : root.canJog && root.permitted("jog.start")
                            onJogPressed: root.startJog(1)
                            onJogReleased: root.releaseJog()
                        }

                        UiComboBox {
                            objectName: "jogIncrement"
                            model: ["连续点动", "0.1000", "0.0100", "0.0010", "0.0001"]
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            Accessible.name: "点动方式与步距"
                            onActivated: {
                                root.releaseJog();
                                root.presentation.jogIncrement = currentIndex === 0 ? 0 : Number(currentText);
                            }
                        }
                    }

                    UiText {
                        width: parent.width
                        height: 24
                        text: "触屏按住 250 毫秒启动 · 松开或滑动停止"
                        font.pixelSize: 11
                        color: Theme.muted
                        verticalAlignment: Text.AlignVCenter
                    }

                    RowLayout {
                        width: parent.width
                        height: 30
                        spacing: 5

                        UiButton {
                            objectName: "homeAll"
                            text: "全部回零"
                            font.pixelSize: Theme.labelSize
                            leftPadding: 3
                            rightPadding: 3
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.preferredHeight: Theme.controlHeight
                            enabled: root.canOperate && root.permitted("machine.home-all")
                            onClicked: root.commandRequested("machine.home-all", {})
                        }

                        UiButton {
                            objectName: "workTouchOff"
                            text: "工件对刀"
                            font.pixelSize: Theme.labelSize
                            leftPadding: 3
                            rightPadding: 3
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.preferredHeight: Theme.controlHeight
                            enabled: root.canOperate && root.presentation.mode === "world" && root.permitted("machine.touch-off")
                            onClicked: root.dialogRequested("machine.touch-off", "工件对刀", root.presentation.selectedAxis)
                        }

                        UiButton {
                            objectName: "toolTouchOff"
                            text: "刀具对刀"
                            font.pixelSize: Theme.labelSize
                            leftPadding: 3
                            rightPadding: 3
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.preferredHeight: Theme.controlHeight
                            enabled: root.canOperate && root.presentation.mode === "world" && root.permitted("tool.touch-off")
                            onClicked: root.dialogRequested("tool.touch-off", "刀具对刀", root.presentation.selectedAxis)
                        }
                    }

                    UiText {
                        objectName: "homingUnavailableReason"
                        width: parent.width
                        visible: text.length > 0
                        text: root.machine.homeAllUnavailableReason || ""
                        wrapMode: Text.Wrap
                        font.pixelSize: 11
                        color: Theme.muted
                        topPadding: 5
                        bottomPadding: 5
                    }

                    UiCheckBox {
                        objectName: "overrideLimits"
                        width: parent.width
                        height: 27
                        text: "临时解除硬限位"
                        checked: !!root.machine.limitOverride
                        interactive: false
                        enabled: root.canOperate && root.permitted("machine.override-limits")
                        onClicked: root.commandRequested("machine.override-limits", {enabled: !checked})
                    }

                    Item {
                        width: parent.width
                        height: 120

                        UiDivider {
                            y: 13
                            width: parent.width
                            height: 1
                        }

                        UiText {
                            y: 34
                            width: 53
                            text: "主轴："
                            color: Theme.secondary
                            font.pixelSize: Theme.labelSize
                        }

                        Column {
                            x: 60
                            y: 27
                            width: parent.width - 60
                            spacing: 5

                            RowLayout {
                                width: parent.width
                                height: 28
                                spacing: 5

                                UiButton {
                                    objectName: "spindleCounterclockwise"
                                    iconName: "left"
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 30
                                    Layout.preferredWidth: 60
                                    Layout.preferredHeight: 28
                                    leftPadding: 6
                                    rightPadding: 6
                                    Accessible.name: "主轴反转"
                                    ToolTip.visible: hovered
                                    ToolTip.text: "主轴反转"
                                    enabled: root.canOperate && root.permitted("spindle.ccw")
                                    onClicked: root.commandRequested("spindle.ccw", {})
                                }

                                UiButton {
                                    objectName: "spindleStop"
                                    text: "停止"
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 60
                                    Layout.preferredWidth: 60
                                    Layout.preferredHeight: 28
                                    leftPadding: 6
                                    rightPadding: 6
                                    enabled: root.canOperate && root.permitted("spindle.stop")
                                    onClicked: root.commandRequested("spindle.stop", {})
                                }

                                UiButton {
                                    objectName: "spindleClockwise"
                                    iconName: "right"
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 30
                                    Layout.preferredWidth: 60
                                    Layout.preferredHeight: 28
                                    leftPadding: 6
                                    rightPadding: 6
                                    Accessible.name: "主轴正转"
                                    ToolTip.visible: hovered
                                    ToolTip.text: "主轴正转"
                                    enabled: root.canOperate && root.permitted("spindle.cw")
                                    onClicked: root.commandRequested("spindle.cw", {})
                                }
                            }

                            RowLayout {
                                width: parent.width
                                height: 28
                                spacing: 5

                                UiButton {
                                    objectName: "spindleDecrease"
                                    text: "−"
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 28
                                    leftPadding: 6
                                    rightPadding: 6
                                    Accessible.name: "降低主轴转速"
                                    enabled: root.canOperate && root.permitted("spindle.decrease")
                                    onClicked: root.commandRequested("spindle.decrease", {})
                                }

                                UiButton {
                                    objectName: "spindleIncrease"
                                    text: "+"
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 28
                                    leftPadding: 6
                                    rightPadding: 6
                                    Accessible.name: "提高主轴转速"
                                    enabled: root.canOperate && root.permitted("spindle.increase")
                                    onClicked: root.commandRequested("spindle.increase", {})
                                }
                            }

                            UiCheckBox {
                                objectName: "spindleBrake"
                                width: parent.width
                                height: 27
                                text: "主轴制动"
                                checked: !!root.machine.spindleBrake
                                interactive: false
                                enabled: root.canOperate && root.permitted("spindle.brake")
                                onClicked: root.commandRequested("spindle.brake", {enabled: !checked})
                            }
                        }
                    }

                    Item {
                        width: parent.width
                        height: 62

                        UiText {
                            y: 13
                            width: 53
                            text: "冷却："
                            color: Theme.secondary
                            font.pixelSize: Theme.labelSize
                        }

                        Column {
                            x: 60
                            y: 8
                            width: parent.width - 60

                            UiCheckBox {
                                objectName: "mistCoolant"
                                width: parent.width
                                height: 27
                                text: "喷雾冷却"
                                checked: !!root.machine.mist
                                interactive: false
                                enabled: root.canOperate && root.permitted("coolant.mist")
                                onClicked: root.commandRequested("coolant.mist", {enabled: !checked})
                            }

                            UiCheckBox {
                                objectName: "floodCoolant"
                                width: parent.width
                                height: 27
                                text: "切削液冷却"
                                checked: !!root.machine.flood
                                interactive: false
                                enabled: root.canOperate && root.permitted("coolant.flood")
                                onClicked: root.commandRequested("coolant.flood", {enabled: !checked})
                            }
                        }
                    }
                }
            }

            MdiControls {
                width: parent.width
                visible: root.presentation.controlTab === "mdi"
                compact: root.compact
                history: root.history
                canOperate: root.canOperate
                commandAllowed: root.permitted("mdi.execute")
                onCommandRequested: (actionId, payload) => root.commandRequested(actionId, payload)
            }

            OverrideControls {
                width: parent.width
                visible: root.showOverrides
                presentation: root.presentation
                machine: root.machine
                jogSpeedLimit: root.jogSpeedLimit
                jogSpeedUnit: root.jogSpeedUnit
                compact: root.compact
                onCommandRequested: (actionId, payload) => root.commandRequested(actionId, payload)
                onJogStopRequested: root.releaseJog()
            }

            Item {
                id: activeCodes
                width: parent.width
                height: visible ? 6 + 17 + 8 + codes.height + 12 : 0
                visible: root.showActiveCodes && root.presentation.controlTab === "mdi"

                UiText {
                    x: 18
                    y: 6
                    height: 17
                    text: "当前模态指令："
                    color: Theme.secondary
                    font.pixelSize: Theme.labelSize
                }

                Rectangle {
                    id: codes
                    objectName: "activeCodes"
                    x: 18
                    y: 31
                    width: parent.width - 36
                    height: codeText.implicitHeight + 20
                    color: Theme.input
                    UiDivider { width: parent.width }

                    UiText {
                        id: codeText
                        x: 10
                        y: 10
                        width: parent.width - 20
                        text: root.machine.activeCodes || "—"
                        color: Theme.secondary
                        font.family: Theme.mono
                        font.pixelSize: Theme.labelSize
                        lineHeightMode: Text.FixedHeight
                        lineHeight: 21
                        wrapMode: Text.Wrap
                    }
                }
            }

            Item {
                width: 1
                height: 10
            }
        }
    }

    UiDivider {
        anchors.right: parent.right
        height: parent.height
        width: 1
        vertical: true
    }
}
// END: ManualOperationPanel
//--------//
