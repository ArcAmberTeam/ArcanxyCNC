import QtQml

// Explicit test fixture: records requested actions without operating a controller.
QtObject {
    property QtObject axisProfiles: QtObject {
        property bool available: true
        property bool busy: false
        property string message: ""
        property var state: ({
            profiles: [
                {axis_count: 3, axes: "XYZ", available: true, reason: ""},
                {axis_count: 4, axes: "XYZC", available: true, reason: ""},
                {axis_count: 5, axes: "XYZAC", available: true, reason: ""}
            ],
            configured_axis_count: 3, operation: null
        })
        property var requests: []
        function request(count) {
            requests = requests.concat([count]);
            state = Object.assign({}, state, {operation: {phase: "scheduled", axis_count: count}});
            return true;
        }
    }
    property QtObject mesaFlash: QtObject {
        property bool available: true
        property var state: ({phase: "not_checked", message: ""})
        property int requestCount: 0
        function request() {
            requestCount++;
            state = {phase: "scheduled", message: "烧录维护请求已提交"};
        }
    }
    property QtObject mesaUpdate: QtObject {
        property bool available: true
        property var state: ({phase: "not_checked", message: "尚未检查 Mesa 配套更新"})
        property int checkCount: 0
        function check() {
            checkCount++;
            state = {phase: "checking", message: "正在检查 Mesa 配套更新…"};
        }
    }
    property QtObject firmwareUpdater: QtObject {
        property bool available: true
        property var state: ({phase: "idle", message: "", progress: 0, version: ""})
        property int fetchCount: 0
        property int installCount: 0
        function fetch() {
            fetchCount++;
            state = {phase: "checking", message: "正在检查最新 Release…", progress: 0, version: ""};
        }
        function install() { installCount++; }
    }
    property var snapshot: ({
        connected: true, message: "", taskState: "ON", powered: true, estop: false,
        mode: "manual", motionMode: "world", busy: false, axes: ["X", "Y", "Z"], jointCount: 3, joints: [0, 1, 2],
        homed: [true, true, true], actualPosition: [12, 23, 34, 0, 0, 0, 0, 0, 0],
        commandedPosition: [12, 23, 34, 0, 0, 0, 0, 0, 0],
        g5xOffset: [0, 0, 0, 0, 0, 0, 0, 0, 0], g92Offset: [0, 0, 0, 0, 0, 0, 0, 0, 0],
        toolOffset: [0, 0, 0, 0, 0, 0, 0, 0, 0], dtg: [0, 0, 0, 0, 0, 0, 0, 0, 0],
        rotationXY: 0, linearUnits: 1, velocity: 0, maxVelocity: 50,
        jogMaxVelocity: 50, maxVelocityLimit: 100,
        feedOverride: 1, rapidOverride: 1, spindleOverride: 1,
        spindleSpeed: 0, spindleDirection: 0, spindleBrake: false,
        flood: false, mist: false, optionalStop: false, blockDelete: false, limitOverride: false,
        file: "/tmp/test.ngc", currentLine: 0, tool: 1, activeCodes: "G17 G21 G54 G90\nM5 M9",
        commandState: "idle", commandMessage: "", capabilities: {}, errors: []
    })
    property QtObject program: QtObject {
        property var lines: ["G21 G90", "G0 X0 Y0", "G1 X10 F100", "M2"]
        property string text: lines.join("\n")
        property string fileName: "test.ngc"
        property string filePath: "/tmp/test.ngc"
        property var segments: []
        property var bounds: ({min: [0, 0, 0], max: [10, 10, 0]})
        property bool previewBusy: false
        property string previewError: ""
        property int selectedLine: 1
    }
    property var history: ["G0 X0 Y0", "G0 Z10", "G54"]
    property var recentFiles: ["/tmp/recent.ngc"]
    property string toolTableText: "T1 P1 X0 Y0 Z0 D6 ; test tool\n"
    property var requests: []
    property int stopCount: 0
    property string openedPath: ""
    property string savedPath: ""
    property string savedText: ""
    signal errorOccurred(string message)
    signal noticeOccurred(string message)
    function dispatch(actionId, payload) {
        requests = requests.concat([{id: actionId, payload: payload}]);
    }
    function stopJog() { stopCount++; }
    function openProgram(path) { openedPath = String(path); return true; }
    function reloadProgram() { dispatch("file.reload", {}); return true; }
    function saveProgram(path, text) { savedPath = String(path); savedText = text; return true; }
    function saveToolTableText(text) { savedText = text; return true; }
    function update(values) { snapshot = Object.assign({}, snapshot, values); }
}
