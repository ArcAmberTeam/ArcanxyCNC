import QtQuick
import QtQuick.Controls
import QtTest
import BetterCnc.Catalog 1.0
import BetterCnc.Chrome 1.0

TestCase {
    name: "OperatorErrorCatalog"
    Component {
        id: dialogWindow
        ApplicationWindow {
            visible: true
            width: 1024
            height: 600
            ErrorDialog { }
        }
    }
    function test_longDetailsKeepDismissalVisible() {
        const host = createTemporaryObject(dialogWindow, null);
        verify(host !== null);
        const dialog = findChild(host, "errorDialog");
        dialog.present("Unknown device error\n".repeat(500), "operation");
        tryCompare(dialog, "opened", true);
        dialog.detailsExpanded = true;
        verify(waitForRendering(dialog.contentItem));
        const dismiss = findChild(host, "error-acknowledge");
        const point = dismiss.mapToItem(dialog.contentItem, 0, 0);
        verify(point.y >= 0);
        verify(point.y + dismiss.height <= dialog.contentItem.height);
        verify(dialog.rawMessage.length < 8300);
        verify(dialog.rawMessage.indexOf("已截断") >= 0);
        mouseClick(dismiss, dismiss.width / 2, dismiss.height / 2);
        tryCompare(dialog, "visible", false);
        host.close();
    }
    function test_knownErrors_data() {
        return [
            {tag: "travel", raw: "Linear move on line 18 would exceed Y's negative limit", animation: "axis-limit"},
            {tag: "switch", raw: "joint 1 on limit switch error", animation: "axis-limit"},
            {tag: "following", raw: "joint 2 following error", animation: "coordinate"},
            {tag: "homing", raw: "回零未配置：XYZ 电机通道尚未核验", animation: "coordinate"},
            {tag: "delete", raw: "自动加工不允许跳过带 / 的程序行", animation: "program"},
            {tag: "feed", raw: "第 18 行：Cannot do g1 with zero feed rate", animation: "feed-zero"},
            {tag: "arc", raw: "Radius to end of arc differs from radius to start: start=(X1.0000,Y2.0000) center=(X3.0000,Y4.0000) end=(X5.0000,Y6.0000) r1=1.0000 r2=2.0000 abs_err=1 rel_err=50.0000%", animation: "arc-radius"},
            {tag: "tool", raw: "Tool radius not less than arc radius with comp", animation: "tool-size"},
            {tag: "timeout", raw: "未收到命令回执，等待超时", animation: "unknown"},
            {tag: "connection", raw: "控制服务连接已断开", animation: "connection"},
            {tag: "unknown", raw: "<b>unrecognized device issue</b>", animation: "unknown"}
        ];
    }
    function test_knownErrors(data) {
        const result = Catalog.explainError(data.raw, "operation");
        compare(result.animation, data.animation);
        verify(result.title.length > 0);
        verify(result.explanation.length > 0);
    }
    function test_unknownContextsAndBoundedMatching() {
        compare(Catalog.explainError("opaque message", "connection").animation, "connection");
        compare(Catalog.explainError("opaque message", "preview").animation, "program");
        compare(Catalog.explainError("x".repeat(8192) + "Cannot do g1 with zero feed rate", "operation").animation, "unknown");
        const escaped = Catalog.errorIllustration("../../outside", false).toString();
        verify(escaped.endsWith("/assets/error-unknown.gif"));
    }
    function test_localIllustrations_data() {
        return ["r-plane", "coordinate", "spindle-stop", "not-monotonic", "connection",
            "unreachable", "collision", "tool-size", "axis-limit", "arc-radius", "feed-zero",
            "small-radius", "processing", "spindle-setup", "unknown", "entry-length",
            "file-access", "parameters", "program", "tool-setup"].map(function(name) {
                return {tag: name, name: name};
            });
    }
    Component { id: picture; Image { } }
    function test_localIllustrations(data) {
        for (const poster of [false, true]) {
            const item = createTemporaryObject(picture, null, {source: Catalog.errorIllustration(data.name, poster)});
            verify(item !== null);
            tryCompare(item, "status", Image.Ready);
        }
    }
}
