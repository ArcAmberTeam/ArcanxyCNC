pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import BetterCnc.Ui 1.0
import BetterCnc.Toolpath 1.0
import BetterCnc.Chrome 1.0

// Full-window composition; all machine state and commands use the shared APIs.
Rectangle {
    id: root
    objectName: "settingsPage"
    required property ToolpathState preview
    required property ChromeActions actions
    property var firmwareUpdater: null
    property var mesaUpdate: null
    property var mesaFlash: null
    property var axisProfiles: null
    property var maintenanceAccount: null
    property string interfaceMode: "professional"
    property string section: "about"
    signal backRequested()
    signal interfaceModeRequested(string mode)
    signal commandRequested(string actionId, var payload)
    function focusBack() { backButton.forceActiveFocus(Qt.TabFocusReason); }
    onSectionChanged: scroller.contentY = 0
    color: Theme.base
    Rectangle {
        id: header
        width: parent.width; height: 64
        color: Theme.surface
        UiButton {
            id: backButton
            objectName: "settings-back"
            x: 16; anchors.verticalCenter: parent.verticalCenter
            width: 124; height: 44; text: "← 返回工作台"
            onClicked: root.backRequested()
        }
        UiText { x: 160; anchors.verticalCenter: parent.verticalCenter; text: "设置"; font.pixelSize: 22; font.weight: Font.DemiBold }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter; spacing: 12
            UiButton {
                objectName: "settings-estop"
                text: "急停"; iconName: "octagon"; kind: "danger"; width: 100; height: 44
                enabled: root.actions.canActivate("machine.estop")
                onClicked: root.actions.activate("machine.estop")
            }
            UiButton {
                objectName: "settings-stop"
                text: "停止"; iconName: "stop"; kind: "danger"; width: 100; height: 44
                enabled: root.actions.canActivate("program.stop")
                onClicked: root.actions.activate("program.stop")
            }
        }
        UiDivider { anchors.bottom: parent.bottom; width: parent.width; height: 1 }
    }
    readonly property var sections: [
        {id: "about", text: "关于本机"},
        {id: "interface", text: "界面与显示"},
        {id: "display", text: "刀路与视图"},
        {id: "machine", text: "加工设置"},
        {id: "developer", text: "开发者选项"}
    ]
    readonly property string sectionTitle: sections.find(item => item.id === section)?.text || "设置"
    Rectangle {
        id: sidebar
        objectName: "settingsSidebar"
        y: header.height
        width: root.width <= 900 ? 176 : 200
        height: parent.height - y
        color: Theme.surface
        UiDivider { anchors.right: parent.right; width: 1; height: parent.height; vertical: true }
        Column {
            x: 12; y: 24; width: parent.width - 24; spacing: 8
            Repeater {
                id: navigation
                model: root.sections
                UiButton {
                    id: category
                    required property var modelData
                    required property int index
                    objectName: "settings-tab-" + modelData.id
                    width: parent.width; height: 44; kind: "tab"
                    text: modelData.text
                    selected: root.section === modelData.id
                    Accessible.role: Accessible.PageTab
                    Accessible.name: text
                    contentItem: UiText {
                        text: category.text
                        leftPadding: 12
                        color: category.foreground
                        font.weight: category.selected ? Font.DemiBold : Font.Normal
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: root.section = modelData.id
                    function selectCategory(next) {
                        const target = (next + root.sections.length) % root.sections.length;
                        root.section = root.sections[target].id;
                        navigation.itemAt(target).forceActiveFocus(Qt.TabFocusReason);
                    }
                    Keys.onUpPressed: selectCategory(index - 1)
                    Keys.onDownPressed: selectCategory(index + 1)
                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                            selectCategory(event.key === Qt.Key_Home ? 0 : root.sections.length - 1);
                            event.accepted = true;
                        }
                    }
                }
            }
        }
    }
    UiText {
        id: sectionHeading
        objectName: "settingsSectionTitle"
        x: sidebar.width + 32; y: header.height + 28
        text: root.sectionTitle
        font.pixelSize: 24; font.weight: Font.DemiBold
        Accessible.role: Accessible.Heading
    }
    Flickable {
        id: scroller
        objectName: "settingsScroller"
        x: sidebar.width + 32; y: header.height + 80
        width: parent.width - x - 24; height: parent.height - y - 24
        contentWidth: width; contentHeight: content.height
        clip: true; boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: UiScrollBar { }
        Column {
            id: content
            width: Math.min(800, parent.width - 16); spacing: 24
            SettingsAbout {
                visible: root.section === "about"
                width: parent.width
                machine: root.actions.machine
                updater: root.firmwareUpdater
                mesaUpdate: root.mesaUpdate
                mesaFlash: root.mesaFlash
            }
            SettingsInterface {
                visible: root.section === "interface"
                width: parent.width
                interfaceMode: root.interfaceMode
                preview: root.preview
                onInterfaceModeRequested: mode => root.interfaceModeRequested(mode)
            }
            ToolpathSettings {
                width: parent.width
                visible: root.section === "display"
                presentation: root.preview
            }
            SettingsDeveloper {
                width: parent.width
                visible: root.section === "developer"
                account: root.maintenanceAccount
            }
            SettingsMachining {
                width: parent.width
                visible: root.section === "machine"
                actions: root.actions
                axisProfiles: root.axisProfiles
                onCommandRequested: (actionId, payload) => root.commandRequested(actionId, payload)
            }
        }
    }
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() {
            if (!root.visible) return;
            const item = root.Window.window.activeFocusItem;
            let ancestor = item;
            while (ancestor && ancestor !== content) ancestor = ancestor.parent;
            if (!ancestor || !item) return;
            const top = item.mapToItem(content, 0, 0).y;
            const bottom = top + item.height;
            scroller.contentY = Math.max(0, Math.min(scroller.contentHeight - scroller.height,
                top < scroller.contentY ? top : bottom > scroller.contentY + scroller.height ? bottom - scroller.height : scroller.contentY));
        }
    }
}
