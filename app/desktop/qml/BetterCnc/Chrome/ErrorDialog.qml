pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import BetterCnc.Ui 1.0
import BetterCnc.Catalog 1.0

//--------//
// BEGIN: Operator error dialog
Popup {
    id: root
    objectName: "errorDialog"
    property var notices: []
    property int overflowCount: 0
    property bool detailsExpanded: false
    property bool animationPaused: false
    property bool copied: false
    readonly property var current: notices.length ? notices[0] : ({raw: "", context: ""})
    readonly property var explanation: Catalog.explainError(current.raw, current.context)
    readonly property string rawMessage: String(current.raw || "")
    readonly property string copyText: explanation.title + "\n\n" + explanation.explanation
        + "\n\n原始错误：\n" + rawMessage
    parent: Overlay.overlay
    popupType: Popup.Item
    z: 1000
    width: Math.min(500, parent ? parent.width - 32 : 500)
    height: Math.min(body.implicitHeight + 92, parent ? parent.height - 32 : 560)
    x: parent ? (parent.width - width) / 2 : 0
    y: parent ? (parent.height - height) / 2 : 0
    padding: 20
    modal: true
    dim: true
    focus: true
    closePolicy: Popup.CloseOnEscape
    enter: Transition { }
    exit: Transition { }
    Overlay.modal: Rectangle { color: Theme.scrim }
    background: UiSurface { radius: 12; shadowStrength: 3 }

    function present(raw, context) {
        const message = String(raw || "");
        if (!message) return;
        const bounded = message.length > 8192 ? message.slice(0, 8192) + "\n（内容过长，已截断；完整信息请查看日志。）" : message;
        if (notices.some(function(item) { return item.raw === bounded; })) return;
        const next = notices.slice();
        if (next.length >= 32) { next.pop(); overflowCount++; }
        next.push({raw: bounded, context: context || "operation"});
        notices = next;
        if (!visible) open();
    }
    onOpened: acknowledge.forceActiveFocus()
    onRawMessageChanged: {
        detailsExpanded = false;
        animationPaused = false;
        copied = false;
        if (visible) scroll.contentY = 0;
    }
    onClosed: {
        notices = notices.slice(1);
        if (notices.length) Qt.callLater(root.open);
        else overflowCount = 0;
    }

    contentItem: Item {
        Flickable {
            id: scroll
            anchors.top: parent.top
            anchors.bottom: footer.top
            anchors.bottomMargin: 12
            width: parent.width
            clip: true
            contentWidth: width
            contentHeight: body.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: UiScrollBar { }
            ColumnLayout {
                id: body
                width: scroll.width
                spacing: 12
                UiText {
                    objectName: "error-title"
                    text: root.explanation.title
                    textFormat: Text.PlainText
                    font.pixelSize: Theme.titleSize
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    Accessible.role: Accessible.Heading
                }
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: width * 305 / 500
                    Image {
                        anchors.fill: parent
                        source: Catalog.errorIllustration(root.explanation.animation, true)
                        fillMode: Image.PreserveAspectFit
                    }
                    AnimatedImage {
                        id: animation
                        objectName: "error-animation"
                        anchors.fill: parent
                        source: root.visible ? Catalog.errorIllustration(root.explanation.animation, false) : ""
                        fillMode: Image.PreserveAspectFit
                        playing: root.visible
                        paused: root.animationPaused
                        visible: status === Image.Ready
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    UiText { text: "原因示意 · 非机床实时画面"; color: Theme.secondary; Layout.fillWidth: true }
                    UiButton {
                        objectName: "error-animation-toggle"
                        text: root.animationPaused ? "播放动画" : "暂停动画"
                        enabled: animation.status === Image.Ready
                        onClicked: root.animationPaused = !root.animationPaused
                    }
                }
                UiText {
                    objectName: "error-explanation"
                    text: root.explanation.explanation
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                UiButton {
                    objectName: "error-details-toggle"
                    text: root.detailsExpanded ? "收起原始信息" : "查看原始信息"
                    onClicked: root.detailsExpanded = !root.detailsExpanded
                }
                TextArea {
                    id: details
                    objectName: "error-details"
                    visible: root.detailsExpanded
                    Layout.fillWidth: true
                    text: root.rawMessage
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.WrapAnywhere
                    readOnly: true
                    selectByMouse: true
                    font.family: Theme.mono
                    font.pixelSize: 12
                    color: Theme.text
                    background: Rectangle { color: Theme.input; radius: 6 }
                }
                UiText {
                    visible: root.overflowCount > 0
                    text: "错误较多，另有 " + root.overflowCount + " 条未在队列中保留，请查看日志。"
                    color: Theme.secondary
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }
        TextEdit { id: clipboard; visible: false; text: root.copyText; textFormat: TextEdit.PlainText }
        RowLayout {
            id: footer
            width: parent.width
            anchors.bottom: parent.bottom
            UiButton {
                objectName: "error-copy"
                text: root.copied ? "已复制" : "复制错误信息"
                onClicked: { clipboard.selectAll(); clipboard.copy(); clipboard.deselect(); root.copied = true; }
            }
            Item { Layout.fillWidth: true }
            UiButton {
                id: acknowledge
                objectName: "error-acknowledge"
                text: root.notices.length > 1 ? "下一条（" + (root.notices.length - 1) + "）" : "关闭"
                kind: "primary"
                onClicked: root.close()
            }
        }
    }
}
// END: Operator error dialog
//--------//
