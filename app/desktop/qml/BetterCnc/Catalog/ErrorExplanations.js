.pragma library
.import "InterpreterErrors.js" as Interpreter

//--------//
// BEGIN: Operator error explanations
var animations = ["r-plane", "coordinate", "spindle-stop", "not-monotonic", "connection",
    "unreachable", "collision", "tool-size", "axis-limit", "arc-radius", "feed-zero",
    "small-radius", "processing", "spindle-setup", "unknown", "entry-length",
    "file-access", "parameters", "program", "tool-setup"];

function entry(title, explanation, animation) {
    return {title: title, explanation: explanation, animation: animation};
}

var unknown = entry("操作结果需要确认",
    "暂时无法准确解释这条错误。请查看下方原始信息，并确认机床当前状态；关闭提示不代表故障解除，也不会重新执行操作。", "unknown");
var connection = entry("机床通信异常",
    "界面没有收到有效的控制器状态。请检查本机控制服务和连接；通信中断不代表正在运行的程序已经停止。", "connection");
var rules = [
    [/would exceed .* limit|超出.*行程|超出.*软限位/i, entry("刀路超出机床行程",
        "程序要求移动到允许范围以外。请核对原始信息中的轴和程序行，再检查工件零点、刀具补偿及刀路范围；不要通过放宽限位来强行运行。", "axis-limit")],
    [/on limit switch|硬限位|禁止限位覆盖/i, entry("限位开关已触发或限位条件不满足",
        "某个轴的限位输入已触发，或限位覆盖状态不符合操作要求。若发生在回零过程中，需要核对该关节的电机、开关和回零配置；关节编号不能直接当作物理轴名称。", "axis-limit")],
    [/following error|跟随误差/i, entry("电机位置跟随误差超限",
        "控制器要求的位置与反馈位置相差过大。请检查驱动、反馈、传动和运动参数，确认原因后再操作。", "coordinate")],
    [/回零未配置|回零配置无效|HOME_SEQUENCE|NO_FORCE_HOMING/i, entry("机床回零配置未就绪",
        "回零方向、开关、轴对应关系或行程尚未通过配置检查，暂时不能开始回零。", "coordinate")],
    [/必须先完成全部.*回零|要求全部.*已回零|世界坐标点动要求回零|not homed/i, entry("机床尚未完成回零",
        "控制器还没有确认各轴的机器基准位置。请先完成规定的回零流程；回零本身不会确定工件装夹在哪里。", "coordinate")],
    [/跳过带 \/|标记行设置|disableBlockDelete/, entry("程序标记行设置不匹配",
        "开启跳过标记行后，带 / 的程序行不会执行。当前加工请求不允许这样运行，请核对程序并将跳过标记行设置与请求保持一致。", "program")],
    [/未收到命令回执|未能确认命令结果|未生成可确认的序号|命令发送结果未知|超时|timeout/i,
        entry("操作结果尚未确认", "没有及时收到可靠的完成回执，不能据此判断操作没有执行或已经停止。请先查询原任务及机床状态，不要重复启动。", "unknown")],
    [/急停|开启机床电源|not enabled|in estop/i, entry("机床处于急停或未使能状态",
        "机床还没有进入允许这项操作的状态。请先查看急停、使能及现场情况。", "spindle-setup")],
    [/机床必须空闲|上一条命令尚未|已有 CAM 作业|运行时不能|请先停止程序|正在执行/,
        entry("机床正在处理其他操作", "上一项操作尚未结束，当前状态不允许执行这项操作。请确认原任务的状态。", "processing")],
    [/联锁|其他命令写入|停止或联锁请求/, entry("加工联锁条件发生变化",
        "机床状态或控制权发生变化，后续步骤被阻止。请先确认机床当前状态和原任务结果。", "processing")],
    [/回零路径无干涉|必须确认工件坐标/, entry("加工准备尚未确认",
        "还没有完成本次操作所需的回零路径、工件坐标或刀具确认。", "coordinate")],
    [/文件.*回执不一致|摘要.*不一致|回执无效|匹配.*回执/, entry("加工文件校验不一致",
        "收到的文件与请求中的校验信息对不上，不能确认这是要加工的那份程序。请重新核对文件及传输结果。", "file-access")],
    [/主轴尚未启动|spindle.*not turning/i, entry("主轴尚未转动",
        "这次操作需要主轴转动，但当前控制器没有确认主轴已启动。", "spindle-stop")],
    [/主轴已停止|主轴旋转时|主轴转速|主轴命令/, entry("主轴状态不符合操作要求",
        "当前主轴的转速、转动或停止状态与这次操作的要求不一致。", "spindle-setup")],
    [/刀具表|必须先装载刀具|对刀目标|对刀仅支持/, entry("刀具或对刀设置不完整",
        "刀具记录、当前装刀状态或对刀目标不符合要求，软件无法正确确定刀具位置。", "tool-setup")],
    [/轴不存在|joint.*轴|轴.*joint|明确指定.*轴|未知运动模式|真实运动模式/i,
        entry("机床轴与运动模式不匹配", "选中的轴不存在，或轴、电机和当前运动模式的对应关系不明确，不能据此移动。", "coordinate")],
    [/INI.*不一致|INI does not match/i, entry("机床运行配置不一致",
        "控制服务使用的配置与实际运行的 LinuxCNC 配置对不上，不能按这一套参数继续操作。", "coordinate")],
    [/尚未打开加工程序|程序尚未由控制器加载/, entry("加工程序尚未加载就绪",
        "界面中的文件尚未被控制器确认加载，暂时没有可以启动的加工内容。", "file-access")],
    [/程序没有暂停|程序没有运行/, entry("程序状态不符合操作要求",
        "本次操作要求程序正在运行或已暂停，但当前程序不是要求的状态。", "processing")],
    [/G54.*无效|零点.*不一致|工件坐标.*无效|零点.*变化/, entry("工件零点需要核对",
        "工件坐标缺失、已改变或与程序不一致。请核对真实装夹位置、工件零点与刀具补偿。", "coordinate")],
    [/文件|目录|路径|Permission denied|No such file|No space left|read.only/i,
        entry("文件读取或写入未完成", "文件可能不存在、位置不符合要求，或当前权限和可用空间不允许操作。请根据原始信息检查；编辑中的内容应先保留。", "file-access")],
    [/UUID|必须是.*整数|必须为.*整数|有限数值|允许范围|必须是布尔值|必须为布尔值|无效.*模式|无效坐标系|未知.*单位|参数.*无效/,
        entry("操作参数不合法", "请求中的编号、数值、单位或模式不符合要求，请根据原始信息检查相应设置。", "parameters")],
    [/先连接|未连接|连接已断开|连接失败|控制器不可用|socket|ECONN|not initialized|status is incomplete/i, connection]
];

// Match literal template fragments in order, without backtracking over native text.
var templates = Interpreter.entries.map(function(item) {
    const placeholder = /%(?:[-+ #0]*\d*(?:\.\d+)?(?:hh|ll|[hljztL])?[diuoxXfFeEgGaAcsp]|%)/g;
    const fragments = [];
    let current = "", cursor = 0, match;
    while ((match = placeholder.exec(item.template)) !== null) {
        current += item.template.slice(cursor, match.index);
        if (match[0] === "%%") current += "%";
        else { fragments.push(current.toLowerCase()); current = ""; }
        cursor = match.index + match[0].length;
    }
    fragments.push((current + item.template.slice(cursor)).toLowerCase());
    return {item: item, fragments: fragments,
        length: fragments.reduce(function(sum, part) { return sum + part.length; }, 0)};
}).filter(function(item) { return item.length >= 12; })
  .sort(function(a, b) { return b.length - a.length; });

function matches(text, fragments) {
    let cursor = 0;
    for (let i = 0; i < fragments.length; ++i) {
        const position = text.indexOf(fragments[i], cursor);
        if (position < 0) return false;
        cursor = position + fragments[i].length;
    }
    return true;
}

function explain(raw, context) {
    const text = String(raw || "").slice(0, 8192);
    const lowered = text.toLowerCase();
    for (let i = 0; i < templates.length; ++i) {
        if (matches(lowered, templates[i].fragments)) {
            const item = templates[i].item;
            return entry(item.title, item.explanation, item.animation);
        }
    }
    for (let i = 0; i < rules.length; ++i) {
        if (rules[i][0].test(text)) return rules[i][1];
    }
    if (context === "connection") return connection;
    if (context === "preview") return entry("刀路预览未能完成",
        "解释器没有生成可用的完整刀路，请根据原始错误检查程序。预览失败不能当作加工验证通过。", "program");
    return unknown;
}
// END: Operator error explanations
//--------//
