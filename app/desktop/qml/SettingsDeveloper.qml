pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import BetterCnc.Ui 1.0

//--------//
// BEGIN: MaintenanceAccountSettings
Column {
    id: root
    property var account: null
    property bool editing: false
    property string validation: ""
    spacing: 12
    function clearPassword() { password.clear(); confirmation.clear(); }
    onVisibleChanged: {
        clearPassword(); editing = false; validation = "";
        if (visible && account) account.refresh();
    }
    UiText { text: "账户管理"; font.pixelSize: 18; font.weight: Font.DemiBold }
    UiText { text: "cnc-maint 运维账户"; font.pixelSize: 16 }
    UiText {
        objectName: "maintenance-account-status"
        width: parent.width; wrapMode: Text.WordWrap
        text: root.account ? root.account.message : "账户管理服务不可用"
    }
    Row {
        spacing: 12
        UiButton {
            objectName: "maintenance-account-enable"
            text: root.account && root.account.known && root.account.enabled ? "修改密码" : "开启并设置密码"
            enabled: !!root.account && root.account.available && root.account.known && !root.account.busy
            onClicked: { root.editing = true; root.validation = ""; password.forceActiveFocus(); }
        }
        UiButton {
            objectName: "maintenance-account-disable"
            text: "关闭维护登录"
            enabled: !!root.account && root.account.known && root.account.enabled && !root.account.busy
            onClicked: { root.clearPassword(); root.editing = false; root.account.disable(); }
        }
        UiButton {
            objectName: "maintenance-account-refresh"
            text: "刷新"
            enabled: !!root.account && !root.account.busy
            onClicked: root.account.refresh()
        }
    }
    Column {
        width: parent.width; spacing: 10
        visible: root.editing
        UiText { text: "新密码" }
        UiTextField {
            id: password
            objectName: "maintenance-account-password"
            width: Math.min(360, parent.width)
            echoMode: TextInput.Password
            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
            maximumLength: 256
            Accessible.name: "cnc-maint 新密码"
        }
        UiText { text: "确认密码" }
        UiTextField {
            id: confirmation
            objectName: "maintenance-account-confirmation"
            width: password.width
            echoMode: TextInput.Password
            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
            maximumLength: 256
            Accessible.name: "再次输入 cnc-maint 密码"
        }
        UiText {
            objectName: "maintenance-account-validation"
            visible: root.validation.length > 0
            text: root.validation; color: Theme.warning
        }
        Row {
            spacing: 12
            UiButton {
                objectName: "maintenance-account-save"
                text: "确认并开启"
                enabled: !!root.account && !root.account.busy
                onClicked: {
                    if (!password.text || password.text !== confirmation.text) {
                        root.validation = "请填写密码，并确保两次输入一致";
                        return;
                    }
                    const accepted = root.account.setPassword(password.text);
                    root.clearPassword();
                    root.validation = "";
                    if (accepted) root.editing = false;
                }
            }
            UiButton {
                text: "取消"
                onClicked: { root.clearPassword(); root.editing = false; root.validation = ""; }
            }
        }
    }
}
// END: MaintenanceAccountSettings
//--------//
