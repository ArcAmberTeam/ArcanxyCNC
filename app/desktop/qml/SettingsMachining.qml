pragma ComponentBehavior: Bound
import QtQuick
import BetterCnc.Ui 1.0
import BetterCnc.Manual 1.0
import BetterCnc.Chrome 1.0

//--------//
// BEGIN: MachiningSettings
Column {
    id: root
    required property ChromeActions actions
    property var axisProfiles: null
    readonly property var machine: root.actions.machine
    readonly property var activeAxes: machine.connected ? machine.axes || [] : []
    readonly property var profileState: axisProfiles ? axisProfiles.state : ({})
    readonly property var operation: profileState.operation || ({})
    property int targetAxisCount: activeAxes.length >= 3 && activeAxes.length <= 5 ? activeAxes.length : 3
    readonly property var targetProfile: (profileState.profiles || []).find(item => item.axis_count === targetAxisCount) || ({})
    readonly property bool switching: operation.phase === "scheduled" || operation.phase === "switching"
    readonly property bool idle: !!machine.connected && machine.powered === false
        && machine.busy === false && !machine.paused && machine.spindleSpeed === 0
        && machine.spindleDirection === 0
    function selectAxes(count) {
        root.targetAxisCount = count;
        if (root.axisProfiles && root.axisProfiles.available && !root.axisProfiles.busy
            && root.idle && root.targetProfile.available
            && root.activeAxes.join("") !== ({3: "XYZ", 4: "XYZC", 5: "XYZAC"})[count])
            root.axisProfiles.request(count);
    }
    signal commandRequested(string actionId, var payload)
    spacing: 20
    Column {
        width: parent.width; spacing: 12
        UiText { text: "加工轴数"; font.pixelSize: 18; font.weight: Font.DemiBold }
        Row {
            width: parent.width; spacing: 12
            Repeater {
                model: [{count: 3, axes: "XYZ"}, {count: 4, axes: "XYZC"}, {count: 5, axes: "XYZAC"}]
                UiButton {
                    required property var modelData
                    objectName: "machining-axes-" + modelData.count
                    width: (parent.width - 24) / 3; height: 52; kind: "tab"
                    text: modelData.count + " 轴 · " + modelData.axes
                    selected: root.activeAxes.join("") === modelData.axes
                    enabled: !root.switching && !(root.axisProfiles && root.axisProfiles.busy)
                    Accessible.role: Accessible.RadioButton
                    Accessible.checkable: true
                    Accessible.checked: selected
                    onClicked: root.selectAxes(modelData.count)
                }
            }
        }
        UiText {
            objectName: "machining-axis-status"
            width: parent.width; wrapMode: Text.WordWrap; color: Theme.secondary
            text: root.activeAxes.length
                ? "当前实际轴：" + root.activeAxes.join(" / ")
                    + (root.activeAxes.join("") === ({3: "XYZ", 4: "XYZC", 5: "XYZAC"})[root.targetAxisCount]
                       ? " · 已生效" : " · 目标 " + root.targetAxisCount + " 轴尚未生效")
                : "机床未连接，实际轴数待确认"
        }
        UiText {
            width: parent.width; wrapMode: Text.WordWrap; color: Theme.secondary
            text: "选择轴数后自动写入当前 INI，同步更新 HAL 并重启控制。C → Axis3；A → Axis4，A 轴限位 ±90°。"
        }
        UiText {
            objectName: "machining-profile-reason"
            width: parent.width; wrapMode: Text.WordWrap
            color: root.targetProfile.available ? Theme.secondary : Theme.warning
            text: !root.switching && !root.targetProfile.available && root.targetProfile.reason
                ? "尚未写入目标 " + root.targetAxisCount + " 轴配置：\n" + root.targetProfile.reason
                : root.axisProfiles && root.axisProfiles.message ? root.axisProfiles.message
                : root.targetProfile.available ? "配置已就绪，可自动写入当前 INI / HAL"
                : "当前参数不足，尚未写入目标 " + root.targetAxisCount + " 轴配置"
        }
        UiButton {
            objectName: "machining-profile-apply"
            width: Math.min(260, parent.width); height: 44; kind: "primary"
            text: root.switching ? "正在写入并重启…" : "重试写入当前 INI"
            enabled: !!root.axisProfiles && root.axisProfiles.available && !root.axisProfiles.busy
                && !!root.targetProfile.available && !root.switching && root.idle
            onClicked: root.axisProfiles.request(root.targetAxisCount)
        }
        UiText {
            visible: !!root.machine.connected && !root.idle
            width: parent.width; wrapMode: Text.WordWrap; color: Theme.warning
            text: "请先停止加工、关闭主轴和机床使能，再应用轴数配置。"
        }
    }
    UiDivider { width: parent.width }
    Column {
        width: parent.width; spacing: 8
        UiText { text: "程序执行"; font.pixelSize: 18; font.weight: Font.DemiBold }
        Repeater {
            model: [{id: "program.optional", text: "可选停止（M1）"}, {id: "program.block-delete", text: "跳过 / 标记程序行"}]
            UiCheckBox {
                required property var modelData
                objectName: "settings-" + modelData.id
                text: modelData.text; height: 44; width: parent.width
                checked: root.actions.isSelected({id: modelData.id})
                interactive: false
                enabled: root.actions.canActivate(modelData.id)
                onClicked: root.actions.activate(modelData.id)
            }
        }
    }
    UiDivider { width: parent.width }
    ManualSettings {
        width: parent.width
        machine: root.actions.machine
        onCommandRequested: (actionId, payload) => root.commandRequested(actionId, payload)
    }
}
// END: MachiningSettings
//--------//
