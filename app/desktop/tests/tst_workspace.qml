import QtQuick
import QtTest
import "../qml" as App

TestCase {
    id: testCase
    name: "WorkspaceController"
    when: windowShown
    width: 1100
    height: 820
    property var window
    property var backend
    Component { id: appComponent; App.Main { } }
    Component { id: backendComponent; FakeBackend { } }

    function visualChild(item, name) {
        if (!item) return null;
        if (item.objectName === name) return item;
        for (const child of item.children || []) {
            const found = visualChild(child, name);
            if (found) return found;
        }
        return null;
    }
    function control(name) {
        const result = findChild(window, name) || visualChild(window.contentItem, name);
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
    function click(name) {
        const item = control(name);
        mouseClick(item, item.width / 2, item.height / 2);
        waitForRendering(window.contentItem);
    }
    function switchInterface(mode) {
        click("open-settings");
        click("settings-tab-interface");
        click("interface-" + mode);
        click("settings-back");
    }
    function lastRequest() { return backend.requests[backend.requests.length - 1]; }
    function test_initialLayoutAndRealProgram() {
        compare(control("workspace").width, 1100);
        compare(control("manualPanel").width, 304);
        compare(control("programSeparator").height, 7);
        compare(control("mdiTab").text, "手动输入 [F5]");
        compare(window.title, "test.ngc");
        verify(!control("dialogHost").visible);
        compare(control("feedOverride").value, 100);
    }
    function test_kiosk_uses_bounded_program_picker_and_disables_exit() {
        window.kioskMode = true;
        compare(control("menu-file.quit").enabled, false);
        for (const tool of ["machine.ladder", "machine.calibration", "machine.hal-config",
                           "machine.hal-meter", "machine.hal-scope", "show.pyvcp"])
            compare(control("menu-" + tool).enabled, false);
        keyClick(Qt.Key_O);
        tryCompare(control("programFilePicker"), "visible", true);
        compare(control("openProgramDialog").visible, false);
        keyClick(Qt.Key_Escape);
        tryCompare(control("programFilePicker"), "visible", false);
        keyClick(Qt.Key_S, Qt.ControlModifier);
        tryCompare(control("programFilePicker"), "visible", true);
        compare(control("programFilePicker").saveMode, true);
        compare(control("saveProgramDialog").visible, false);
        keyClick(Qt.Key_Escape);
        tryCompare(control("programFilePicker"), "visible", false);
        window.kioskMode = false;
        compare(control("menu-file.quit").enabled, true);
    }
    function test_disconnectedDisablesMachineActions() {
        backend.update({connected: false, axes: [], powered: false, message: "控制器不可用"});
        tryCompare(control("jogPlus"), "enabled", false);
        compare(control("toolbar-machine.estop").enabled, false);
        compare(control("homeAll").enabled, false);
        compare(control("mistCoolant").enabled, false);
        tryCompare(control("errorDialog"), "visible", true);
        compare(control("errorDialog").rawMessage, "控制器不可用");
        keyClick(Qt.Key_Escape);
        const before = backend.requests.length;
        keyClick(Qt.Key_R);
        compare(backend.requests.length, before);
    }
    function test_homingDisabledReasonIsVisibleWithoutEnablingTheButton() {
        backend.update({
            capabilities: {"machine.home-all": false},
            homeAllUnavailableReason: "回零未配置：XYZ 电机通道与实机轴尚未核验"
        });
        tryCompare(control("homeAll"), "enabled", false);
        tryCompare(control("homingUnavailableReason"), "visible", true);
        compare(control("homingUnavailableReason").text, backend.snapshot.homeAllUnavailableReason);
        backend.update({homeAllUnavailableReason: "回零不可用：急停未解除"});
        tryCompare(control("homingUnavailableReason"), "text", "回零不可用：急停未解除");
        backend.update({homeAllUnavailableReason: ""});
        tryCompare(control("homingUnavailableReason"), "visible", false);
    }
    function test_unknownOverrideValuesAreNotPresentedAsZero_data() {
        return [
            {tag: "feed", name: "feedOverride", value: 1, displayed: "100"},
            {tag: "rapid", name: "rapidOverride", value: 0.25, displayed: "25"},
            {tag: "spindle", name: "spindleOverride", value: 1.1, displayed: "110"},
            {tag: "maximum-velocity", name: "maxVelocity", value: 2, displayed: "120"}
        ];
    }
    function test_unknownOverrideValuesAreNotPresentedAsZero(data) {
        const field = control(data.name + ".value");
        const slider = control(data.name + ".slider");
        let values = {};
        values[data.name] = 0;
        backend.update(values);
        compare(field.text, "0");
        values[data.name] = null;
        backend.update(values);
        compare(field.text, "—");
        verify(!slider.enabled);
        values[data.name] = undefined;
        backend.update(values);
        compare(field.text, "—");
        verify(!slider.enabled);
        values[data.name] = data.value;
        values.connected = false;
        backend.update(values);
        compare(field.text, "—");
        verify(!slider.enabled);
        values.connected = true;
        backend.update(values);
        compare(field.text, data.displayed);
        verify(slider.enabled);
    }
    function test_connectingDoesNotReportFailure() {
        backend.update({connected: false, connecting: true, message: "正在连接"});
        verify(!control("errorDialog").visible);
        compare(control("jogPlus").enabled, false);
        backend.update({connecting: false, message: "socket 不可用"});
        tryCompare(control("errorDialog"), "visible", true);
        compare(control("errorDialog").rawMessage, "socket 不可用");
    }
    function test_mdiAndHistory() {
        keyClick(Qt.Key_F5);
        compare(lastRequest().id, "machine.mode");
        compare(lastRequest().payload.mode, "mdi");
        waitForRendering(control("mdiHistory"));
        click("mdiHistory1");
        compare(control("mdiCommand").text, "G0 Z10");
        click("mdiExecute");
        compare(lastRequest().id, "mdi.execute");
        compare(lastRequest().payload.text, "G0 Z10");
        verify(!control("dialogHost").visible);
    }
    function test_machineChecksWaitForSnapshot() {
        const item = control("mistCoolant");
        compare(item.checked, false);
        click("mistCoolant");
        compare(lastRequest().id, "coolant.mist");
        compare(lastRequest().payload.enabled, true);
        compare(item.checked, false);
        backend.update({mist: true});
        tryCompare(item, "checked", true);
    }
    function test_jogPressReleaseAndStateLoss() {
        click("axisY");
        const plus = control("jogPlus");
        mousePress(plus, plus.width / 2, plus.height / 2);
        compare(lastRequest().id, "jog.start");
        compare(lastRequest().payload.axis, "Y");
        compare(lastRequest().payload.direction, 1);
        compare(lastRequest().payload.velocity, control("manualState").jogVelocity / 60);
        compare(lastRequest().payload.increment, 0);
        const stops = backend.stopCount;
        mouseRelease(plus, plus.width / 2, plus.height / 2);
        verify(backend.stopCount > stops);
        mousePress(plus, plus.width / 2, plus.height / 2);
        const interrupted = backend.stopCount;
        backend.update({estop: true, powered: false});
        tryVerify(() => backend.stopCount > interrupted);
        mouseRelease(plus, plus.width / 2, plus.height / 2);
    }
    function test_acceptedJogKeepsReleaseAvailable() {
        const plus = control("jogPlus");
        mousePress(plus, plus.width / 2, plus.height / 2);
        compare(lastRequest().id, "jog.start");
        const stops = backend.stopCount;
        backend.update({busy: true, capabilities: {"jog.start": false}});
        waitForRendering(plus);
        compare(backend.stopCount, stops);
        verify(plus.down);
        verify(plus.enabled);
        mouseRelease(plus, plus.width / 2, plus.height / 2);
        verify(backend.stopCount > stops);
        verify(!plus.enabled);
    }
    function test_ownedJogStopsOnControllerModeChange() {
        const plus = control("jogPlus");
        mousePress(plus, plus.width / 2, plus.height / 2);
        backend.update({capabilities: {"jog.start": false}});
        const stops = backend.stopCount;
        backend.update({mode: "auto"});
        tryVerify(() => backend.stopCount > stops);
        verify(!plus.enabled);
        mouseRelease(plus, plus.width / 2, plus.height / 2);
    }
    function test_jogKeyboardReleaseAndFocusLoss() {
        const workspace = control("workspace");
        workspace.forceActiveFocus();
        keyPress(Qt.Key_Right);
        compare(lastRequest().id, "jog.start");
        compare(lastRequest().payload.axis, "X");
        const stops = backend.stopCount;
        keyRelease(Qt.Key_Right);
        verify(backend.stopCount > stops);
        workspace.forceActiveFocus();
        keyPress(Qt.Key_Left);
        const focusStops = backend.stopCount;
        control("manualTab").forceActiveFocus();
        tryVerify(() => backend.stopCount > focusStops);
        keyRelease(Qt.Key_Left);
    }
    function test_jogIncrementAndInterruption() {
        const increment = control("jogIncrement");
        increment.forceActiveFocus();
        keyClick(Qt.Key_Down);
        compare(control("manualState").jogIncrement, 0.1);
        const plus = control("jogPlus");
        mousePress(plus, plus.width / 2, plus.height / 2);
        compare(lastRequest().payload.increment, 0.1);
        const beforeTab = backend.stopCount;
        keyClick(Qt.Key_F5);
        tryVerify(() => backend.stopCount > beforeTab);
        mouseRelease(plus, plus.width / 2, plus.height / 2);
        keyClick(Qt.Key_F3);
        waitForRendering(window.contentItem);
        mousePress(plus, plus.width / 2, plus.height / 2);
        const beforeDialog = backend.stopCount;
        backend.noticeOccurred("操作提示");
        tryVerify(() => backend.stopCount > beforeDialog);
        verify(control("dialogHost").visible);
        mouseRelease(plus, plus.width / 2, plus.height / 2);
    }
    function test_jointJogDoesNotInferAxisMapping() {
        backend.update({motionMode: "joint", jointCount: 4, joints: [0, 1, 2, 3]});
        waitForRendering(window.contentItem);
        click("joint3");
        compare(control("manualState").selectedJoint, 3);
        const plus = control("jogPlus");
        mousePress(plus, plus.width / 2, plus.height / 2);
        compare(lastRequest().id, "jog.start");
        compare(lastRequest().payload.axis, 3);
        compare(lastRequest().payload.mode, "joint");
        mouseRelease(plus, plus.width / 2, plus.height / 2);
        verify(!control("workTouchOff").enabled);
        control("workspace").forceActiveFocus();
        keyClick(Qt.Key_Home);
        compare(lastRequest().id, "machine.home");
        compare(lastRequest().payload.joint, 3);
        keyPress(Qt.Key_Left);
        compare(lastRequest().id, "jog.start");
        compare(lastRequest().payload.axis, 3);
        keyRelease(Qt.Key_Left);
    }
    function test_offsetSubmission() {
        click("axisY");
        click("workTouchOff");
        const dialog = control("dialogHost");
        tryCompare(dialog, "opened", true);
        // The Loader and ColumnLayout publish final button positions on the next frame.
        verify(waitForRendering(dialog.contentItem));
        compare(dialog.axis, "Y");
        const field = control("touch-value");
        field.forceActiveFocus(); field.selectAll();
        keyClick(Qt.Key_1); keyClick(Qt.Key_2); keyClick(Qt.Key_Period); keyClick(Qt.Key_5);
        compare(dialog.value, "12.5");
        const before = backend.requests.length;
        click("dialog-submit");
        compare(backend.requests.length, before + 1);
        compare(lastRequest().id, "machine.touch-off");
        compare(lastRequest().payload.value, 12.5);
        compare(lastRequest().payload.axis, "Y");
        compare(lastRequest().payload.system, "G54");
        verify(!dialog.visible);
    }
    function test_overridesOnlySendUserMoves() {
        const before = backend.requests.length;
        backend.update({feedOverride: 0.8});
        tryCompare(control("feedOverride"), "value", 80);
        compare(backend.requests.length, before);
        const slider = control("feedOverride.slider");
        slider.forceActiveFocus();
        keyClick(Qt.Key_Right);
        compare(lastRequest().id, "override.feed");
        fuzzyCompare(lastRequest().payload.value, 0.81, 0.001);
        compare(backend.snapshot.feedOverride, 0.8);
        backend.update({feedOverride: 0.75});
        tryCompare(control("feedOverride"), "value", 75);
    }
    function test_splitterAndSmallWindowReachability() {
        const sash = control("programSeparator");
        const workspace = control("workspace");
        sash.forceActiveFocus(); keyClick(Qt.Key_Up);
        compare(workspace.programHeight, 194);
        window.width = 760; window.height = 640;
        tryCompare(control("manualPanel"), "width", 280);
        waitForRendering(window.contentItem);
        click("open-settings"); click("settings-tab-machine");
        const slider = control("maxVelocity.slider");
        const scroller = control("settingsScroller");
        slider.forceActiveFocus(Qt.TabFocusReason);
        tryVerify(() => slider.mapToItem(scroller, 0, 0).y >= 0);
        tryVerify(() => slider.mapToItem(scroller, 0, slider.height).y <= scroller.height);
        keyClick(Qt.Key_Left);
        compare(lastRequest().id, "velocity.max");
    }
    function test_shortcutsAreIsolatedFromEditing() {
        keyClick(Qt.Key_F5);
        const input = control("mdiCommand");
        input.forceActiveFocus();
        const before = backend.requests.length;
        keyClick(Qt.Key_R); keyClick(Qt.Key_T); keyClick(Qt.Key_P); keyClick(Qt.Key_S);
        compare(input.text.toLowerCase(), "rtps");
        compare(backend.requests.length, before);
        keyClick(Qt.Key_F1);
        compare(lastRequest().id, "machine.estop");
    }
    function test_backendErrorIsPresented() {
        backend.errorOccurred("当前状态不允许执行此指令");
        const dialog = control("errorDialog");
        tryCompare(dialog, "visible", true);
        compare(dialog.rawMessage, "当前状态不允许执行此指令");
        compare(control("error-title").text, "操作结果需要确认");
    }
    function test_errorQueueDoesNotReplayMachineActions() {
        const before = backend.requests.length;
        backend.errorOccurred("Linear move on line 18 would exceed Y's negative limit");
        backend.errorOccurred("joint 1 on limit switch error");
        backend.errorOccurred("joint 1 on limit switch error");
        const dialog = control("errorDialog");
        tryCompare(dialog, "opened", true);
        compare(dialog.notices.length, 2);
        compare(control("error-title").text, "刀路超出机床行程");
        keyClick(Qt.Key_R);
        compare(backend.requests.length, before);
        keyClick(Qt.Key_Escape);
        tryCompare(dialog, "opened", true);
        compare(dialog.rawMessage, "joint 1 on limit switch error");
        compare(dialog.notices.length, 1);
        keyClick(Qt.Key_Escape);
        tryCompare(dialog, "visible", false);
        compare(backend.requests.length, before);
        backend.errorOccurred("joint 1 on limit switch error");
        tryCompare(dialog, "visible", true);
    }
    function test_errorPresentationAtOperatorScreenSize_data() {
        return [{tag: "target", width: 1024, height: 600}, {tag: "minimum", width: 760, height: 640}];
    }
    function test_errorPresentationAtOperatorScreenSize(data) {
        window.width = data.width; window.height = data.height;
        backend.errorOccurred("自动加工不允许跳过带 / 的程序行");
        const dialog = control("errorDialog");
        tryCompare(dialog, "opened", true);
        verify(waitForRendering(dialog.contentItem));
        verify(dialog.x >= 0 && dialog.y >= 0);
        verify(dialog.x + dialog.width <= window.width);
        verify(dialog.y + dialog.height <= window.height);
        const animation = control("error-animation");
        tryCompare(animation, "status", Image.Ready);
        click("error-animation-toggle");
        compare(animation.paused, true);
        click("error-details-toggle");
        compare(control("error-details").text, "自动加工不允许跳过带 / 的程序行");
        compare(control("error-details").textFormat, TextEdit.PlainText);
    }
    function test_previewFailureHasExplanationAndDoesNotRepeatOnProgress() {
        backend.program.previewError = "Cannot do g1 with zero feed rate";
        const dialog = control("errorDialog");
        tryCompare(dialog, "opened", true);
        compare(dialog.explanation.animation, "feed-zero");
        keyClick(Qt.Key_Escape);
        tryCompare(dialog, "visible", false);
        backend.program.selectedLine = 2;
        verify(!dialog.visible);
        backend.program.previewBusy = true;
        backend.program.previewBusy = false;
        tryCompare(dialog, "visible", true);
    }

    function test_jogRejectedWithoutPermittedState_data() {
        return [
            {tag: "disconnected", state: {connected: false}},
            {tag: "power-off", state: {powered: false}},
            {tag: "estop", state: {estop: true}},
            {tag: "busy", state: {busy: true}},
            {tag: "auto-mode", state: {mode: "auto"}},
            {tag: "missing-axis", state: {axes: []}},
            {tag: "capability-denied", state: {capabilities: {"jog.start": false}}}
        ];
    }
    function test_jogRejectedWithoutPermittedState(data) {
        backend.update(data.state);
        const plus = control("jogPlus");
        tryCompare(plus, "enabled", false);
        const before = backend.requests.length;
        mouseClick(plus, plus.width / 2, plus.height / 2);
        control("workspace").forceActiveFocus();
        keyPress(Qt.Key_Right);
        keyRelease(Qt.Key_Right);
        compare(backend.requests.length, before);
    }

    function test_reconnectDoesNotReplayHeldJog() {
        const workspace = control("workspace");
        workspace.forceActiveFocus();
        keyPress(Qt.Key_Right);
        compare(lastRequest().id, "jog.start");
        const before = backend.requests.length;
        const stops = backend.stopCount;
        backend.update({connected: false});
        tryVerify(() => backend.stopCount > stops);
        verify(!control("jogPlus").enabled);
        backend.update({connected: true});
        tryCompare(control("jogPlus"), "enabled", true);
        waitForRendering(window.contentItem);
        compare(backend.requests.length, before);
        keyRelease(Qt.Key_Right);
        compare(backend.requests.length, before);
        keyPress(Qt.Key_Right);
        compare(backend.requests.length, before + 1);
        compare(lastRequest().id, "jog.start");
        keyRelease(Qt.Key_Right);
    }

    function test_offlineViewControlsRemainLocal() {
        backend.update({connected: false, powered: false, axes: []});
        const before = backend.requests.length;
        const preview = control("toolpathState");
        const zoom = preview.zoom;
        click("viewport-zoom-in");
        verify(preview.zoom > zoom);
        click("viewport-top");
        compare(preview.choices.view, "z");
        click("droTab");
        compare(preview.previewTab, "dro");
        click("previewTab");
        compare(preview.previewTab, "preview");
        compare(backend.requests.length, before);
    }

    function test_invalidTouchOffDoesNotSubmit_data() {
        return [
            {tag: "empty", text: ""},
            {tag: "whitespace", text: "   "},
            {tag: "text", text: "bad"},
            {tag: "overflow", text: "1e999"}
        ];
    }
    function test_invalidTouchOffDoesNotSubmit(data) {
        click("workTouchOff");
        const dialog = control("dialogHost");
        tryCompare(dialog, "opened", true);
        verify(waitForRendering(dialog.contentItem));
        const field = control("touch-value");
        field.forceActiveFocus();
        field.selectAll();
        keyClick(Qt.Key_Backspace);
        for (let i = 0; i < data.text.length; ++i) keyClick(data.text[i]);
        compare(field.text, data.text);
        const before = backend.requests.length;
        click("dialog-submit");
        compare(backend.requests.length, before);
        verify(dialog.visible);
        const error = control("dialog-validation-error");
        verify(error.visible);
        compare(error.text, "请输入有效的数值。");
        // A validation failure must not prevent correcting and submitting the input.
        field.forceActiveFocus();
        field.selectAll();
        keyClick(Qt.Key_5);
        click("dialog-submit");
        compare(backend.requests.length, before + 1);
        compare(lastRequest().id, "machine.touch-off");
        compare(lastRequest().payload.value, 5);
        verify(!dialog.visible);
    }

    function test_platinumLayout_data() {
        return [
            {tag: "wide", w: 1440, h: 900, columns: true},
            {tag: "desktop", w: 1280, h: 800, columns: true},
            {tag: "compact", w: 1024, h: 768, columns: false},
            {tag: "target-screen", w: 1024, h: 600, columns: false},
            {tag: "minimum", w: 760, h: 640, columns: false}
        ];
    }
    function test_platinumLayout(data) {
        window.width = data.w; window.height = data.h;
        waitForRendering(window.contentItem);
        if (data.w === 1024) compare(control("workspace-chrome").height, 52);
        const manual = control("manualPanel");
        const preview = control("toolpathPanel");
        const program = control("programPanel");
        verify(manual.x + manual.width < preview.x);
        compare(control("programSeparator").visible, true);
        compare(program.x, preview.x);
        verify(preview.y + preview.height < program.y);
        if (data.columns) verify(preview.width >= 520);
        const stop = control("toolbar-program.stop");
        const viewport = control("toolbar-viewport");
        control("toolbar-program.step").forceActiveFocus(Qt.TabFocusReason);
        waitForRendering(window.contentItem);
        verify(stop.mapToItem(window.contentItem, 0, 0).x >= viewport.mapToItem(window.contentItem, viewport.width, 0).x);
        verify(stop.visible && stop.enabled);
        verify(control("machineStatusLabel").visible);
    }
    function test_statusReflectsFeedback_data() {
        return [
            {tag: "offline", state: {connected: false}, text: "未连接"},
            {tag: "estop", state: {estop: true}, text: "急停已触发"},
            {tag: "busy", state: {busy: true}, text: "加工中"},
            {tag: "paused", state: {busy: true, paused: true}, text: "已暂停"},
            {tag: "unknown", state: {commandState: "unknown"}, text: "操作异常"}
        ];
    }
    function test_statusReflectsFeedback(data) {
        backend.update(data.state);
        compare(control("machineStatusLabel").text, data.text);
    }
    function test_switchInterfacesPreservesStateWithoutCommands() {
        keyClick(Qt.Key_F5);
        control("mdiCommand").text = "G0 X25";
        const state = control("toolpathState");
        state.setChoice("view", "x");
        state.panBy(45, -20); state.zoomBy(1.5);
        backend.program.selectedLine = 3;
        const manual = control("manualState");
        manual.jogIncrement = 0.1;
        const before = backend.requests.length;
        switchInterface("guided");
        compare(window.interfaceMode, "guided");
        compare(control("manualPanel").visible, false);
        click("stage-device");
        compare(control("mdiCommand").text, "G0 X25");
        switchInterface("professional");
        compare(window.interfaceMode, "professional");
        compare(state.choices.view, "x");
        compare(state.panX, 45); compare(state.panY, -20); compare(state.zoom, 1.5);
        compare(backend.program.selectedLine, 3);
        compare(manual.jogIncrement, 0.1);
        compare(backend.requests.length, before);
    }
    function test_guidedStagesAndHiddenJog() {
        switchInterface("guided");
        compare(control("workspaceGuide").visible, true);
        compare(control("programPanel").visible, true);
        const before = backend.requests.length;
        control("workspace").forceActiveFocus();
        keyClick(Qt.Key_Right);
        compare(backend.requests.length, before);
        click("guide-next");
        compare(window.guidedStage, "preview");
        compare(control("programPanel").visible, false);
        compare(control("toolpathPanel").visible, true);
        click("guide-next");
        compare(window.guidedStage, "device");
        compare(control("manualPanel").visible, true);
        control("workspace").forceActiveFocus();
        keyPress(Qt.Key_Right);
        compare(lastRequest().id, "jog.start");
        const stops = backend.stopCount;
        click("stage-prepare");
        verify(backend.stopCount > stops);
        keyRelease(Qt.Key_Right);
        const stopped = backend.requests.length;
        control("workspace").forceActiveFocus();
        keyClick(Qt.Key_Right);
        compare(backend.requests.length, stopped);
        keyClick(Qt.Key_F5);
        compare(window.guidedStage, "device");
        compare(control("mdiTab").selected, true);
    }
    function test_guidedActionsUseSharedPermissions() {
        switchInterface("guided");
        click("stage-preview");
        waitForRendering(window.contentItem);
        control("guide-run").forceActiveFocus(Qt.TabFocusReason);
        click("guide-run");
        compare(lastRequest().id, "program.run");
        backend.update({busy: true});
        verify(!control("guide-run").enabled);
        click("toolbar-program.pause");
        compare(lastRequest().id, "program.pause");
        backend.update({paused: true});
        compare(control("toolbar-program.pause").text, "继续");
        click("toolbar-program.pause");
        compare(lastRequest().id, "program.resume");
        click("toolbar-program.stop");
        compare(lastRequest().id, "program.stop");
        backend.update({connected: false});
        verify(!control("toolbar-machine.estop").enabled);
        verify(!control("guide-run").enabled);
        compare(control("machineStatusLabel").text, "未连接");
        backend.update({connected: true, busy: false, paused: false, capabilities: {"program.run": false}});
        verify(!control("guide-run").enabled);
        verify(!control("toolbar-program.run").enabled);
    }
    function test_guidedLayout_data() {
        const rows = [];
        for (const width of [760, 1024, 1280, 1440])
            for (const stage of ["prepare", "preview", "device"])
                rows.push({tag: width + "-" + stage, w: width, stage: stage});
        return rows;
    }
    function test_guidedLayout(data) {
        window.width = data.w; window.height = data.w === 1024 ? 600 : 640;
        switchInterface("guided");
        click("stage-" + data.stage);
        waitForRendering(window.contentItem);
        if (data.w === 1024) compare(control("workspace-chrome").height, 96);
        const panels = [control("manualPanel"), control("programPanel"), control("toolpathPanel"), control("workspaceGuide")].filter(p => p.visible);
        for (const item of panels) {
            const p = item.mapToItem(window.contentItem, 0, 0);
            verify(p.x >= 0 && p.y >= control("workspace-chrome").height);
            verify(p.x + item.width <= window.width);
            verify(p.y + item.height <= window.height - 32);
            verify(item.width > 0 && item.height > 0);
            for (const other of panels) {
                if (other === item) continue;
                const q = other.mapToItem(window.contentItem, 0, 0);
                verify(p.x + item.width <= q.x || q.x + other.width <= p.x
                    || p.y + item.height <= q.y || q.y + other.height <= p.y);
            }
        }
        for (const name of ["toolbar-machine.estop", "toolbar-program.stop", "open-settings", "stage-device"]) {
            const item = control(name);
            const p = item.mapToItem(window.contentItem, 0, 0);
            verify(item.visible && p.x >= 0 && p.x + item.width <= window.width);
        }
        if (data.stage !== "device") {
            const next = control("guide-next");
            const p = next.mapToItem(window.contentItem, 0, 0);
            verify(p.y >= control("workspace-chrome").height && p.y + next.height <= window.height - 32);
            if (data.stage === "preview") {
                const run = control("guide-run");
                const q = run.mapToItem(window.contentItem, 0, 0);
                verify(q.y + run.height <= window.height - 32);
            }
        }
    }
    function test_cameraFocusConsumesJogKeysAndTouch() {
        const canvas = control("toolpathCanvas"), state = control("toolpathState");
        const before = backend.requests.length;
        mouseClick(canvas, canvas.width / 2, canvas.height / 2);
        keyClick(Qt.Key_Right); keyClick(Qt.Key_Up); keyClick(Qt.Key_PageUp);
        compare(backend.requests.length, before);
        verify(state.panX > 0 && state.panY < 0 && state.zoom > 1);
        keyClick(Qt.Key_Home);
        compare(state.panX, 0); compare(state.zoom, 1);
        keyClick(Qt.Key_End);
        compare(backend.requests.length, before);
        let touch = touchEvent(canvas);
        touch.press(0, canvas, 100, 80).commit(); wait(20);
        touch.move(0, canvas, 150, 100).commit(); wait(20);
        touch.move(0, canvas, 190, 120).commit(); wait(20);
        touch.release(0, canvas, 190, 120).commit(); wait(20);
        compare(backend.requests.length, before);
    }
    function test_viewToolbarFocusDoesNotOperateMachine() {
        click("viewport-zoom-in");
        const before = backend.requests.length;
        keyClick(Qt.Key_Right); keyClick(Qt.Key_PageUp);
        keyClick(Qt.Key_Home); keyClick(Qt.Key_End);
        compare(backend.requests.length, before);
        verify(!control("dialogHost").visible);
    }
    function test_touchJogPendingHoldCanceledByFocusLoss() {
        const plus = control("jogPlus"), before = backend.requests.length;
        let touch = touchEvent(plus);
        touch.press(0, plus, 20, 20).commit(); wait(20);
        control("toolpathCanvas").forceActiveFocus();
        wait(350);
        compare(backend.requests.length, before);
        touch.release(0, plus, 20, 20).commit(); wait(20);
    }
    function test_touchJogTapAndSwipeDoNotStartMotion() {
        const plus = control("jogPlus"), before = backend.requests.length;
        verify(plus.width >= 44 && plus.height >= 44);
        let touch = touchEvent(plus);
        touch.press(0, plus, 20, 20).commit(); wait(20);
        touch.release(0, plus, 20, 20).commit(); wait(20);
        compare(backend.requests.length, before);
        touch.press(0, plus, 20, 20).commit(); wait(20);
        touch.move(0, plus, 20, -45).commit(); wait(20);
        wait(350);
        touch.release(0, plus, 20, -45).commit(); wait(20);
        compare(backend.requests.length, before);
    }
    function test_touchJogHoldReleaseAndDragCancel() {
        const plus = control("jogPlus"), before = backend.requests.length;
        let touch = touchEvent(plus);
        touch.press(0, plus, 20, 20).commit(); wait(20);
        compare(backend.requests.length, before);
        wait(350);
        compare(backend.requests.length, before + 1);
        compare(lastRequest().id, "jog.start");
        const stops = backend.stopCount;
        touch.release(0, plus, 20, 20).commit(); wait(20);
        verify(backend.stopCount > stops);
        touch.press(0, plus, 20, 20).commit(); wait(20);
        wait(350);
        compare(backend.requests.length, before + 2);
        const stops2 = backend.stopCount;
        touch.move(0, plus, 20, -45).commit(); wait(20);
        verify(backend.stopCount > stops2);
        touch.move(0, plus, 20, 20).commit(); wait(20);
        wait(350);
        compare(backend.requests.length, before + 2, "Canceled touch must not restart on reentry");
        touch.release(0, plus, 20, 20).commit(); wait(20);
    }

    function test_settingsFillSmallScreenAndRestoreWorkspace() {
        window.width = 1024; window.height = 600;
        const view = control("toolpathState"), manual = control("manualState");
        view.panBy(40, 25); view.zoomBy(1.5); manual.jogIncrement = 0.1;
        backend.program.selectedLine = 3;
        const before = backend.requests.length;
        click("open-settings");
        const page = control("settingsPage");
        tryCompare(page, "width", 1024); tryCompare(page, "height", 600);
        const origin = page.mapToItem(window.contentItem, 0, 0);
        compare(origin.x, 0); compare(origin.y, 0);
        verify(!control("workspace-chrome").visible);
        verify(!control("manualPanel").visible);
        verify(!control("toolpathPanel").visible);
        for (const name of ["settings-back", "settings-estop", "settings-stop", "settings-tab-machine"]) {
            const item = control(name), p = item.mapToItem(page, 0, 0);
            verify(item.visible && item.height >= 44);
            verify(p.x >= 0 && p.x + item.width <= 1024 && p.y + item.height <= 600);
        }
        click("settings-back");
        verify(!page.visible);
        verify(control("toolpathPanel").visible);
        verify(control("open-settings").activeFocus);
        compare(view.panX, 40); compare(view.panY, 25); compare(view.zoom, 1.5);
        compare(manual.jogIncrement, 0.1); compare(backend.program.selectedLine, 3);
        compare(backend.requests.length, before);
    }
    function test_settingsStopsJogAndBlocksMachineShortcuts() {
        control("workspace").forceActiveFocus();
        keyPress(Qt.Key_Right);
        compare(lastRequest().id, "jog.start");
        const stops = backend.stopCount;
        click("open-settings"); keyRelease(Qt.Key_Right);
        verify(backend.stopCount > stops);
        const before = backend.requests.length;
        for (const key of [Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End, Qt.Key_R, Qt.Key_F2, Qt.Key_F3, Qt.Key_F5]) keyClick(key);
        compare(backend.requests.length, before);
        verify(control("settingsPage").visible);
        verify(!control("dialogHost").visible);
        keyClick(Qt.Key_Escape);
        compare(lastRequest().id, "program.stop");
        keyClick(Qt.Key_F1);
        compare(lastRequest().id, "machine.estop");
        click("settings-stop"); compare(lastRequest().id, "program.stop");
        click("settings-estop"); compare(lastRequest().id, "machine.estop");
    }
    function test_settingsDisplayAndScrollStayLocalOffline() {
        window.width = 1024; window.height = 600;
        backend.update({connected: false, message: ""});
        const before = backend.requests.length, state = control("toolpathState");
        click("open-settings"); click("settings-tab-interface");
        const units = control("settings-units");
        units.forceActiveFocus(); keyClick(Qt.Key_Home); keyClick(Qt.Key_Return);
        compare(state.choices.units, "inch");
        const scroll = control("settingsScroller"), flags = JSON.stringify(state.flags);
        scroll.contentY = 0;
        waitForRendering(window.contentItem);
        let touch = touchEvent(scroll);
        touch.press(0, scroll, scroll.width - 40, 360).commit(); wait(20);
        touch.move(0, scroll, scroll.width - 40, 280).commit(); wait(20);
        touch.move(0, scroll, scroll.width - 40, 120).commit(); wait(20);
        touch.release(0, scroll, scroll.width - 40, 120).commit(); wait(20);
        tryVerify(() => scroll.contentY > 40);
        compare(JSON.stringify(state.flags), flags, "Scrolling must not toggle display settings");
        tryCompare(scroll, "moving", false);
        const flag = control("settings-show.large");
        flag.forceActiveFocus(Qt.TabFocusReason);
        const scroller = control("settingsScroller");
        tryVerify(() => flag.mapToItem(scroller, 0, 0).y >= 0 && flag.mapToItem(scroller, 0, flag.height).y <= scroller.height);
        click("settings-show.large"); compare(state.flags["show.large"], true);
        click("settings-tab-display");
        const clear = control("settings-clear-live"), revision = state.liveResetRevision;
        clear.forceActiveFocus(Qt.TabFocusReason); click("settings-clear-live");
        compare(state.liveResetRevision, revision + 1);
        compare(backend.requests.length, before);
        click("settings-tab-machine");
        verify(!control("maxVelocity").enabled);
        verify(!control("settings-program.optional").enabled);
    }

    function test_firmwareUpdatesUseIndependentServiceAndFeedback() {
        window.width = 1024; window.height = 600;
        backend.update({powered: false, busy: false});
        const before = backend.requests.length, updater = backend.firmwareUpdater;
        click("open-settings"); click("settings-tab-about");
        const update = control("settings-firmware-update");
        update.forceActiveFocus(Qt.TabFocusReason);
        waitForRendering(window.contentItem);
        const scroll = control("settingsScroller");
        tryVerify(() => update.mapToItem(scroll, 0, update.height).y <= scroll.height);
        click("settings-firmware-update");
        compare(updater.fetchCount, 1);
        verify(!update.enabled);
        compare(backend.requests.length, before);
        updater.state = {phase: "no_release", message: "当前仓库尚未发布正式 Release", progress: 0, version: ""};
        verify(update.enabled);
        compare(control("settings-firmware-status").text, "当前仓库尚未发布正式 Release");
        verify(!control("settings-firmware-install").visible);
        updater.state = {phase: "ready", message: "0.3.0 已下载并通过校验", progress: 100, version: "0.3.0"};
        const install = control("settings-firmware-install");
        verify(install.visible && install.enabled);
        backend.update({powered: true}); verify(!install.enabled);
        backend.update({powered: false, busy: true}); verify(!install.enabled);
        backend.update({busy: false});
        waitForRendering(window.contentItem);
        install.forceActiveFocus(Qt.TabFocusReason);
        click("settings-firmware-install"); compare(updater.installCount, 1);
        updater.state = {phase: "error", message: "SHA-256 校验失败", progress: 0, version: ""};
        verify(!install.visible);
        verify(update.enabled);
        compare(backend.requests.length, before);
    }
    function test_mesaCheckIsSeparateAndSourceReleaseDoesNotOfferFlashing() {
        window.width = 1024; window.height = 600;
        const before = backend.requests.length;
        click("open-settings"); click("settings-tab-about");
        const check = control("settings-mesa-check");
        check.forceActiveFocus(Qt.TabFocusReason);
        const scroll = control("settingsScroller");
        tryVerify(() => check.mapToItem(scroll, 0, check.height).y <= scroll.height);
        click("settings-mesa-check");
        compare(backend.mesaUpdate.checkCount, 1);
        verify(!check.enabled);
        compare(backend.firmwareUpdater.fetchCount, 0);
        backend.mesaUpdate.state = {phase: "source_only", available_version: "26.10.26.1", message: "无可烧录固件"};
        verify(check.enabled);
        compare(control("settings-mesa-version").text, "配套版本：26.10.26.1");
        compare(control("settings-mesa-status").text, "无可烧录固件");
        verify(!control("settings-mesa-flash").visible);
        compare(backend.mesaFlash.requestCount, 0);
        compare(backend.requests.length, before);
    }

    function test_verifiedMesaFirmwareUsesIndependentMaintenanceRequest() {
        window.width = 1024; window.height = 600;
        backend.update({connected: true, powered: true, busy: false});
        backend.mesaUpdate.state = {
            phase: "release_available", installed_app_version: "26.10.26.1",
            manifest: {compatible_app_version: "26.10.26.1", firmware: {available: true}}
        };
        click("open-settings"); click("settings-tab-about");
        const flash = control("settings-mesa-flash");
        verify(flash.visible && !flash.enabled);
        backend.update({powered: false, busy: true}); verify(!flash.enabled);
        backend.update({busy: false}); verify(flash.enabled);
        const before = backend.requests.length;
        flash.forceActiveFocus(Qt.TabFocusReason);
        const scroll = control("settingsScroller");
        tryVerify(() => flash.mapToItem(scroll, 0, flash.height).y <= scroll.height);
        click("settings-mesa-flash");
        compare(backend.mesaFlash.requestCount, 1);
        verify(!flash.enabled);
        compare(backend.requests.length, before);
        compare(backend.firmwareUpdater.installCount, 0);
    }

    function test_settingsSidebarCategories_data() {
        return [{tag: "compact", width: 760, height: 640},
                {tag: "target", width: 1024, height: 600},
                {tag: "large", width: 1440, height: 900}];
    }
    function test_settingsSidebarCategories(data) {
        window.width = data.width; window.height = data.height;
        click("open-settings");
        const page = control("settingsPage"), sidebar = control("settingsSidebar");
        const names = ["about", "interface", "display", "machine"];
        const labels = ["关于本机", "界面与显示", "刀路与视图", "加工选型"];
        for (let i = 0; i < names.length; ++i) {
            const item = control("settings-tab-" + names[i]);
            compare(item.text, labels[i]);
            const point = item.mapToItem(sidebar, 0, 0);
            verify(point.x >= 0 && point.x + item.width <= sidebar.width);
            verify(point.y >= 0 && point.y + item.height <= sidebar.height);
            item.forceActiveFocus(Qt.TabFocusReason);
            keyClick(Qt.Key_Space);
            compare(control("settingsSectionTitle").text, labels[i]);
            const heading = control("settingsSectionTitle").mapToItem(page, 0, 0);
            verify(heading.x > sidebar.width);
        }
        click("settings-tab-about");
        verify(control("settings-about-机床状态").visible);
        compare(control("settings-about-配置轴").text, backend.snapshot.axes.join(" · "));
        control("settings-tab-about").forceActiveFocus(Qt.TabFocusReason);
        keyClick(Qt.Key_Down);
        verify(control("interface-guided").visible);
        verify(control("settings-units").visible);
        verify(!control("settings-grid").visible);
        keyClick(Qt.Key_Down);
        verify(control("settings-grid").visible);
        verify(!control("settings-units").visible);
        verify(control("settings-show.program").visible);
        keyClick(Qt.Key_Down);
        verify(control("settings-program.optional").visible);
        verify(control("maxVelocity").visible);
    }

}
