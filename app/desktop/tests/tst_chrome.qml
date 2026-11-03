import QtQuick
import QtTest
import BetterCnc.Catalog 1.0
import "../qml" as App

TestCase {
    id: testCase
    name: "ChromeController"
    when: windowShown
    width: 1100
    height: 820
    property var window
    property var backend
    Component { id: appComponent; App.Main { } }
    Component { id: backendComponent; FakeBackend { } }
    function findVisual(item, name) {
        if (!item) return null;
        if (item.objectName === name) return item;
        for (const child of item.children || []) {
            const result = findVisual(child, name);
            if (result) return result;
        }
        return null;
    }
    function control(name) {
        const result = findChild(window, name) || findVisual(window.contentItem, name);
        verify(result !== null, "Missing public UI: " + name);
        return result;
    }
    function init() {
        backend = createTemporaryObject(backendComponent, null);
        window = createTemporaryObject(appComponent, null, {backend: backend, width: 1100, height: 820});
        verify(window !== null);
        window.requestActivate();
        waitForRendering(window.contentItem);
    }
    function cleanup() { if (window) window.close(); }
    function click(item) { mouseClick(item, item.width / 2, item.height / 2); }
    function lastRequest() { return backend.requests[backend.requests.length - 1]; }
    function leafEntries() {
        const result = [];
        function visit(entries, path) {
            entries.forEach((entry, index) => {
                const nextPath = path.concat(index);
                if (entry.id === "file.recent") visit([
                    {id: "file.recent.0", label: "recent.ngc"},
                    {id: "file.clear-recents", label: "清空最近打开记录"}
                ], nextPath);
                else if (entry.children) visit(entry.children, nextPath);
                else if (entry.kind !== "separator") result.push({tag: entry.id, entry: entry, path: nextPath});
            });
        }
        visit(Catalog.menus, []);
        return result;
    }
    function test_allMenuEntries_data() { return leafEntries(); }
    function test_allMenuEntries(data) {
        if (data.entry.id === "program.pause" || data.entry.id === "program.resume") backend.update({busy: true});
        const beforeFlag = control("toolpathState").flags[data.entry.id];
        const menubar = control("main-menubar");
        click(menubar.itemAt(data.path[0]));
        let menu = menubar.menuAt(data.path[0]);
        tryCompare(menu, "visible", true);
        for (let depth = 1; depth < data.path.length; depth++) {
            const index = data.path[depth];
            menu.contentItem.positionViewAtIndex(index, ListView.Contain);
            waitForRendering(window.contentItem);
            const item = menu.itemAt(index);
            verify(item !== null && item.enabled, data.entry.id);
            click(item);
            if (depth < data.path.length - 1) {
                menu = item.subMenu;
                tryCompare(menu, "visible", true);
            }
        }
        const entry = data.entry;
        const preview = control("toolpathState");
        const dialog = control("dialogHost");
        if (entry.kind === "radio" && entry.group === "mode") {
            compare(lastRequest().id, "motion.mode");
            compare(lastRequest().payload.mode, entry.value);
            compare(backend.snapshot.motionMode, "world");
        } else if (entry.kind === "radio") {
            compare(entry.group === "touch" ? control("manualState").touchTarget : preview.choices[entry.group], entry.value);
        } else if (entry.kind === "check" && entry.id in preview.flags) compare(preview.flags[entry.id], !beforeFlag);
        else if (entry.id === "view.clear") compare(preview.flags["show.live"], true);
        else if (entry.id === "file.open") { tryCompare(control("openProgramDialog"), "visible", true); control("openProgramDialog").close(); }
        else if (entry.id === "file.save") { tryCompare(control("saveProgramDialog"), "visible", true); control("saveProgramDialog").close(); }
        else if (entry.id === "file.recent.0") compare(backend.openedPath, "/tmp/recent.ngc");
        else if (entry.id === "file.quit") tryCompare(window, "visible", false);
        else if (["help.about", "help.reference", "file.properties", "file.edit", "tool.edit", "view.grid-custom", "machine.debug"].indexOf(entry.id) >= 0) {
            tryCompare(dialog, "visible", true);
            compare(dialog.actionId, entry.id);
            verify(dialog.description.indexOf("仅演示") < 0);
        } else compare(lastRequest().id, entry.id);
        compare(backend.snapshot.taskState, "ON");
    }
    function test_toolbar_data() { return Catalog.toolbar.filter(entry => !entry.id.startsWith("view.") && entry.id !== "program.optional" && entry.id !== "program.block-delete").map(entry => ({tag: entry.id, entry: entry})); }
    function test_toolbar(data) {
        if (data.entry.id === "program.pause") backend.update({busy: true});
        const preview = control("toolpathState");
        const beforeZoom = preview.zoom;
        click(control("toolbar-" + data.entry.id));
        const id = data.entry.id;
        if (id === "view.zoom-in") verify(preview.zoom > beforeZoom);
        else if (id === "view.zoom-out") verify(preview.zoom < beforeZoom);
        else if (id === "view.rotate") compare(preview.rotate, true);
        else if (id === "view.clear") compare(preview.flags["show.live"], true);
        else if (id.indexOf("view.") === 0) compare(preview.choices.view, id.slice(5));
        else if (id === "file.open") { tryCompare(control("openProgramDialog"), "visible", true); control("openProgramDialog").close(); }
        else compare(lastRequest().id, id);
    }
    function test_menuAndDialogFocus() {
        const menubar = control("main-menubar");
        const chrome = control("workspace-chrome");
        click(menubar.itemAt(2));
        tryCompare(chrome, "menuOpen", true);
        keyClick(Qt.Key_V);
        compare(control("toolpathState").choices.view, "p");
        keyClick(Qt.Key_Escape);
        tryCompare(chrome, "menuOpen", false);
        keyClick(Qt.Key_V);
        compare(control("toolpathState").choices.view, "z");
        click(control("workTouchOff"));
        keyClick(Qt.Key_V);
        compare(control("toolpathState").choices.view, "z");
        keyClick(Qt.Key_Escape);
        tryCompare(control("dialogHost"), "visible", false);
        keyClick(Qt.Key_V);
        compare(control("toolpathState").choices.view, "z2");
    }
    function test_statusPollingKeepsOpenMenuStable() {
        const menubar = control("main-menubar");
        click(menubar.itemAt(2));
        const menu = menubar.menuAt(2);
        tryCompare(menu, "opened", true);
        backend.update({actualPosition: [13, 24, 35, 0, 0, 0, 0, 0, 0], feedOverride: 0.9});
        waitForRendering(menu.contentItem);
        compare(menubar.menuAt(2), menu);
        verify(menu.visible);
    }
    function test_submenuHover() {
        const menubar = control("main-menubar");
        click(menubar.itemAt(0));
        const menu = menubar.menuAt(0);
        tryCompare(menu, "opened", true);
        waitForRendering(menu.contentItem);
        const recent = menu.itemAt(1);
        mouseMove(recent, recent.width / 2, recent.height / 2);
        tryCompare(recent, "hovered", true);
        tryCompare(recent.subMenu, "visible", true);
    }
    function test_minimumToolbarKeyboardVisibility() {
        window.width = 760; window.height = 640;
        waitForRendering(window.contentItem);
        const viewport = control("toolbar-viewport");
        const last = control("toolbar-program.step");
        last.forceActiveFocus(Qt.TabFocusReason);
        tryVerify(() => last.mapToItem(viewport, 0, 0).x + last.width <= viewport.width + 0.5);
        verify(viewport.contentWidth <= viewport.width, "Small-screen toolbar must fit without horizontal scrolling");
        const first = control("toolbar-machine.estop");
        first.forceActiveFocus(Qt.BacktabFocusReason);
        tryVerify(() => first.mapToItem(viewport, 0, 0).x >= -0.5);
        compare(viewport.contentX, 0);
    }
    function test_machineSelectionFollowsSnapshot() {
        click(control("open-settings")); click(control("settings-tab-machine"));
        waitForRendering(window.contentItem);
        const optional = control("settings-program.optional");
        compare(optional.checked, false);
        click(optional);
        compare(lastRequest().payload.enabled, true);
        compare(optional.checked, false);
        backend.update({optionalStop: true});
        tryCompare(optional, "checked", true);
    }
    function test_touchOffCompensationNotice_data() {
        return [
            {tag: "tool", button: "toolTouchOff", target: "workpiece", action: "tool.touch-off", notice: true},
            {tag: "tool-target", button: "workTouchOff", target: "tool", action: "machine.touch-off", notice: true},
            {tag: "workpiece", button: "workTouchOff", target: "workpiece", action: "machine.touch-off", notice: false}
        ];
    }
    function test_touchOffCompensationNotice(data) {
        control("manualState").touchTarget = data.target;
        const before = backend.requests.length;
        click(control(data.button));
        const dialog = control("dialogHost");
        tryCompare(dialog, "visible", true);
        waitForRendering(window.contentItem);
        const description = control("dialog-description");
        verify(description.visible);
        compare(description.text.indexOf("保存当前刀具对刀值；已有刀长补偿将从当前刀号重新加载，替换动态补偿") >= 0, data.notice);
        verify(description.mapToItem(dialog.contentItem, 0, 0).y >= 0);
        verify(description.mapToItem(dialog.contentItem, 0, description.height).y <= dialog.contentItem.height);
        compare(backend.requests.length, before);
        click(control("dialog-submit"));
        compare(lastRequest().id, data.action);
        compare(lastRequest().payload.target, data.target);
    }
    function test_programAndToolEditsSubmitActualText() {
        const dialog = control("dialogHost");
        dialog.openDialog("file.edit", "编辑程序", "X");
        tryCompare(dialog, "visible", true);
        compare(control("dialog-editor").text, backend.program.text);
        waitForRendering(window.contentItem);
        const programEditor = control("dialog-editor");
        programEditor.forceActiveFocus(); programEditor.selectAll();
        keyClick(Qt.Key_G, Qt.ShiftModifier); keyClick(Qt.Key_2); keyClick(Qt.Key_1);
        keyClick(Qt.Key_Return); keyClick(Qt.Key_M, Qt.ShiftModifier); keyClick(Qt.Key_2); keyClick(Qt.Key_Return);
        click(control("dialog-submit"));
        compare(backend.savedPath, "/tmp/test.ngc");
        compare(backend.savedText.toUpperCase(), "G21\nM2\n");
        verify(dialog.visible);
        compare(dialog.actionId, "file.edit");
        dialog.openDialog("tool.edit", "编辑刀具表", "X");
        compare(control("dialog-editor").text, backend.toolTableText);
        waitForRendering(window.contentItem);
        const toolEditor = control("dialog-editor");
        toolEditor.forceActiveFocus(); toolEditor.selectAll();
        keyClick(Qt.Key_T, Qt.ShiftModifier); keyClick(Qt.Key_1); keyClick(Qt.Key_Space);
        keyClick(Qt.Key_P, Qt.ShiftModifier); keyClick(Qt.Key_1); keyClick(Qt.Key_Return);
        click(control("dialog-submit"));
        compare(backend.savedText.toUpperCase(), "T1 P1\n");
        verify(dialog.visible);
        compare(dialog.actionId, "tool.edit");
    }
    function test_editorDraftSurvivesAsyncFailure_data() {
        return [{tag: "program", action: "file.edit"}, {tag: "tool-table", action: "tool.edit"}];
    }
    function test_editorDraftSurvivesAsyncFailure(data) {
        const dialog = control("dialogHost");
        dialog.openDialog(data.action, "编辑", "X");
        tryCompare(dialog, "visible", true);
        waitForRendering(window.contentItem);
        const editor = control("dialog-editor");
        editor.forceActiveFocus(); editor.selectAll();
        keyClick(Qt.Key_D); keyClick(Qt.Key_R); keyClick(Qt.Key_A); keyClick(Qt.Key_F); keyClick(Qt.Key_T);
        const draft = editor.text;
        click(control("dialog-submit"));
        compare(backend.savedText, draft);
        verify(dialog.visible);
        compare(dialog.actionId, data.action);
        compare(control("dialog-editor").text, draft);
        backend.errorOccurred("写入被控制器拒绝");
        compare(dialog.actionId, data.action);
        compare(control("dialog-editor").text, draft);
        const error = control("dialog-validation-error");
        verify(error.visible);
        compare(error.text, "写入被控制器拒绝");
        backend.update({connected: false, connecting: false, message: "控制服务连接已断开"});
        verify(dialog.visible);
        compare(dialog.actionId, data.action);
        compare(control("dialog-editor").text, draft);
        compare(error.text, "控制服务连接已断开");
        backend.update({connected: true, message: ""});
        const failures = control("errorDialog");
        tryCompare(failures, "opened", true);
        keyClick(Qt.Key_Escape);
        tryCompare(failures, "opened", true);
        keyClick(Qt.Key_Escape);
        tryCompare(failures, "visible", false);
        click(control("dialog-submit"));
        compare(dialog.validationError, "");
        compare(dialog.actionId, data.action);
        backend.noticeOccurred("文件写入已完成");
        compare(dialog.actionId, "controller.message");
        compare(control("dialog-description").text, "文件写入已完成");
        verify(dialog.visible);
    }

}
