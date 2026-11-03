import QtQuick
import BetterCnc.Ui 1.0

//--------//
// BEGIN: ProfessionalPageLayout
WorkspaceLayout {
    property string page: "preview"
    readonly property bool advancedPage: page === "advanced"
    readonly property real contentX: manualVisible ? sidebarWidth + Theme.gap : 0
    readonly property real contentWidth: width - contentX
    manualRect: Qt.rect(0, 0, sidebarWidth, height)
    manualVisible: page !== "preview"
    programRect: Qt.rect(contentX, 0, contentWidth, height)
    previewVisible: !advancedPage
    programVisible: advancedPage
    previewRect: Qt.rect(contentX, 0, contentWidth, height)
}
// END: ProfessionalPageLayout
//--------//
