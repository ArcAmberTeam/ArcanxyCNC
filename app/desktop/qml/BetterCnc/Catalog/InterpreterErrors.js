.pragma library

// Localized interpreter messages from ArcAmberCAM; see assets/cam-errors-source.json.
var entries = [
  {
    "template": "Zero-radius arc: start=(%c%.4f,%c%.4f) center=(%c%.4f,%c%.4f) end=(%c%.4f,%c%.4f) r1=%.4f r2=%.4f",
    "symbols": [],
    "title": "圆弧半径为零",
    "explanation": "起点或终点几乎落在圆心上，圆已经小到无法作为正常圆弧计算。",
    "animation": "program"
  },
  {
    "template": "Radius to end of arc differs from radius to start: start=(%c%.4f,%c%.4f) center=(%c%.4f,%c%.4f) end=(%c%.4f,%c%.4f) r1=%.4f r2=%.4f abs_err=%.4g rel_err=%.4f%%",
    "symbols": [],
    "title": "圆弧起终点半径不一致",
    "explanation": "同一个圆，起点和终点离圆心应该一样远。程序给出的两个距离不同，所以这段圆弧接不上。",
    "animation": "arc-radius"
  },
  {
    "template": "Tool radius not less than arc radius with comp",
    "symbols": [
      "NCE_TOOL_RADIUS_NOT_LESS_THAN_ARC_RADIUS_WITH_COMP"
    ],
    "title": "刀具半径不小于圆弧半径",
    "explanation": "刀太粗，钻不进程序要求的内弯。开启刀补后，刀具中心已经没有可走的正常圆弧。",
    "animation": "tool-size"
  },
  {
    "template": "Bug code not g2 or g3",
    "symbols": [
      "NCE_BUG_CODE_NOT_G2_OR_G3"
    ],
    "title": "圆弧转换指令类型异常",
    "explanation": "软件进入了处理圆弧的步骤，却收到的不是 G2 或 G3。这是指令处理状态异常。",
    "animation": "processing"
  },
  {
    "template": "Current point same as end point of arc",
    "symbols": [
      "NCE_CURRENT_POINT_SAME_AS_END_POINT_OF_ARC"
    ],
    "title": "半径格式圆弧起终点重合",
    "explanation": "这一段用半径来定义圆弧，但起点和终点在同一点，软件无法据此确定要走哪段圆。",
    "animation": "program"
  },
  {
    "template": "Arc radius too small to reach end point",
    "symbols": [
      "NCE_ARC_RADIUS_TOO_SMALL_TO_REACH_END_POINT"
    ],
    "title": "圆弧半径不足以连接端点",
    "explanation": "两个点离得太远，给的圆又太小；这个圆根本没法同时经过这两个点。",
    "animation": "small-radius"
  },
  {
    "template": "Must use g0 or g1 with g53",
    "symbols": [
      "NCE_MUST_USE_G0_OR_G1_WITH_G53"
    ],
    "title": "G53 运动方式不合法",
    "explanation": "G53 要按机器坐标移动，只能搭配 G0 快移或 G1 直线进给，不能搭配其他走法。",
    "animation": "program"
  },
  {
    "template": "Cannot use g53 incremental",
    "symbols": [
      "NCE_CANNOT_USE_G53_INCREMENTAL"
    ],
    "title": "G53 不支持增量坐标",
    "explanation": "程序一边要求按机器的固定坐标走，一边又要求从当前位置加一段距离，两种说法冲突。",
    "animation": "coordinate"
  },
  {
    "template": "Bug bad g code modal group 0",
    "symbols": [
      "NCE_BUG_BAD_G_CODE_MODAL_GROUP_0"
    ],
    "title": "非模态 G 指令分组异常",
    "explanation": "软件收到一个不属于当前处理分组的 G 指令，无法按预期解释。",
    "animation": "processing"
  },
  {
    "template": "Too many m codes on line",
    "symbols": [
      "NCE_TOO_MANY_M_CODES_ON_LINE"
    ],
    "title": "单行 M 指令数量超限",
    "explanation": "一行里塞了太多 M 指令，超过了解释器允许一次处理的数量。",
    "animation": "program"
  },
  {
    "template": "Cannot put an a in canned cycle",
    "symbols": [
      "NCE_CANNOT_PUT_AN_A_IN_CANNED_CYCLE"
    ],
    "title": "固定循环不允许 A 轴参数",
    "explanation": "这条自动钻孔等循环不接受 A 旋转轴运动，程序却给了 A。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot put a b in canned cycle",
    "symbols": [
      "NCE_CANNOT_PUT_A_B_IN_CANNED_CYCLE"
    ],
    "title": "固定循环不允许 B 轴参数",
    "explanation": "这条自动钻孔等循环不接受 B 旋转轴运动，程序却给了 B。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot put a c in canned cycle",
    "symbols": [
      "NCE_CANNOT_PUT_A_C_IN_CANNED_CYCLE"
    ],
    "title": "固定循环不允许 C 轴参数",
    "explanation": "这条自动钻孔等循环不接受 C 旋转轴运动，程序却给了 C。",
    "animation": "coordinate"
  },
  {
    "template": "D word with no G41, G41.1, G42, G42.1, G71, G71.1, G71.2 or G96 to use it",
    "symbols": [],
    "title": "D 参数没有适用的指令",
    "explanation": "这一行写了 D 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "$ (spindle selection) word with no M3, M4, M5, M19, M51, G33, G33.1, G76, G95, G96 or G97 to use it",
    "symbols": [],
    "title": "$ 参数没有适用的指令",
    "explanation": "这一行写了 $ 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "E word with no G70, G76, M66, M67 or M68 to use it",
    "symbols": [],
    "title": "E 参数没有适用的指令",
    "explanation": "这一行写了 E 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "H word with no G43 or G76 to use it",
    "symbols": [],
    "title": "H 参数没有适用的指令",
    "explanation": "这一行写了 H 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "I word with no G2, G3, G5, G5.1, G10, G33.1, G76, or G87 to use it",
    "symbols": [],
    "title": "I 参数没有适用的指令",
    "explanation": "这一行写了 I 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "J word with no G2, G3, G5, G5.1, G10, G76 or G87 to use it",
    "symbols": [],
    "title": "J 参数没有适用的指令",
    "explanation": "这一行写了 J 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "K word with no G2, G3, G33, G33.1, G76, or G87 to use it",
    "symbols": [],
    "title": "K 参数没有适用的指令",
    "explanation": "这一行写了 K 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "L word with no G10, cutter compensation, canned cycle, digital/analog input, M98 or NURBS code",
    "symbols": [],
    "title": "L 参数没有适用的指令",
    "explanation": "这一行写了 L 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "P word with no G2 G3 G4 G10 G64 G5 G5.2 G76 G82 G86 G88 G89 or M50 M51 M52 M53 M62 M63 M64 M65 M66 M98 or user M code to use it",
    "symbols": [],
    "title": "P 参数没有适用的指令",
    "explanation": "这一行写了 P 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "P value not an integer with M19 G2 or G3",
    "symbols": [],
    "title": "P 参数必须为整数",
    "explanation": "这条 M19、G2 或 G3 把 P 当作整数使用，不能填 1.5 这样的数。",
    "animation": "parameters"
  },
  {
    "template": "P value must be 0,1,or 2 with M19",
    "symbols": [],
    "title": "M19 的 P 参数取值非法",
    "explanation": "主轴定向时，P 只允许填 0、1 或 2；当前值不在这三个选项里。",
    "animation": "program"
  },
  {
    "template": "P value should be 1 or greater with G2 or G3",
    "symbols": [],
    "title": "圆弧圈数 P 小于 1",
    "explanation": "圆弧的 P 表示圈数，至少要有 1 圈，不能填零或更小的值。",
    "animation": "program"
  },
  {
    "template": "Q word with no G5, G10, G64, G73, G76, G83, M19, M66, M67, M68 or user M code that uses it",
    "symbols": [],
    "title": "Q 参数没有适用的指令",
    "explanation": "这一行写了 Q 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "R word with no g code that uses it",
    "symbols": [
      "NCE_R_WORD_WITH_NO_G_CODE_THAT_USES_IT"
    ],
    "title": "R 参数没有适用的指令",
    "explanation": "这一行写了 R 参数，但当前指令没有可使用它的功能。就像只写了一个设置值，却没有对应的操作；支持的指令列表保留在英文原文中。",
    "animation": "program"
  },
  {
    "template": "R value must be within 0..360 with M19",
    "symbols": [],
    "title": "主轴定向角 R 超出范围",
    "explanation": "M19 要求的主轴角度必须在 0 到 360 度之间，当前数值越界了。",
    "animation": "spindle-setup"
  },
  {
    "template": "S word missing with G96",
    "symbols": [
      "NCE_S_WORD_MISSING_WITH_G96"
    ],
    "title": "恒线速度模式缺少 S 参数",
    "explanation": "开启 G96 后，还没告诉软件所需的切削线速度是多少。",
    "animation": "program"
  },
  {
    "template": "K word missing with g33/g33.1",
    "symbols": [
      "NCE_K_WORD_MISSING_WITH_G33"
    ],
    "title": "螺纹同步运动缺少 K 参数",
    "explanation": "G33 或 G33.1 没写 K，软件不知道主轴每转一圈应前进多少。",
    "animation": "program"
  },
  {
    "template": "F word used with a g33/g33.1",
    "symbols": [
      "NCE_F_WORD_USED_WITH_G33"
    ],
    "title": "螺纹同步运动误用 F 参数",
    "explanation": "这类螺纹运动用 K 指定每转前进量，程序却额外给了不适用的 F。",
    "animation": "program"
  },
  {
    "template": "P word missing with G76",
    "symbols": [
      "NCE_P_WORD_MISSING_WITH_G76"
    ],
    "title": "G76 螺纹循环缺少 P 参数",
    "explanation": "没有提供螺纹的螺距，软件不知道相邻牙之间隔多远。",
    "animation": "program"
  },
  {
    "template": "I J or K words missing with G76",
    "symbols": [
      "NCE_I_J_OR_K_WORDS_MISSING_WITH_G76"
    ],
    "title": "G76 螺纹循环参数不完整",
    "explanation": "I、J、K 中至少缺了一个，螺纹的进刀位置或切深信息不够。",
    "animation": "program"
  },
  {
    "template": "Dwell time missing with g4",
    "symbols": [
      "NCE_DWELL_TIME_MISSING_WITH_G4"
    ],
    "title": "G4 暂停缺少时间",
    "explanation": "程序要求停一下，却没写需要停多久。",
    "animation": "program"
  },
  {
    "template": "G4 not allowed with G2 or G3 because they both use P",
    "symbols": [],
    "title": "G4 与圆弧指令争用 P 参数",
    "explanation": "同一行既要暂停又要走圆弧，两者都用 P，软件无法判断这个 P 是给谁的。",
    "animation": "program"
  },
  {
    "template": "Line with G10 does not have L0, L1, L10, L11, L2, or L20",
    "symbols": [],
    "title": "G10 缺少合法的 L 操作类型",
    "explanation": "程序要求写入刀具或坐标数据，却没用合法的 L 值说明到底要改哪类数据。",
    "animation": "program"
  },
  {
    "template": "P value not an integer with G10",
    "symbols": [],
    "title": "G10 的 P 参数不是整数",
    "explanation": "这里的 P 用来选编号，必须是完整整数，不能带小数。",
    "animation": "parameters"
  },
  {
    "template": "P value out of range (0-9) with G10 L%d",
    "symbols": [],
    "title": "G10 坐标选择 P 超出 0–9",
    "explanation": "程序选了一个超出允许范围的坐标编号，软件不知道该把数据写到哪里。",
    "animation": "coordinate"
  },
  {
    "template": "P value out of range with G10 L%d",
    "symbols": [],
    "title": "G10 刀具选择编号 P 小于 1",
    "explanation": "使用 G10 L1、L10 或 L11 修改刀具数据时，P 必须至少为 1；当前编号不满足要求。",
    "animation": "tool-setup"
  },
  {
    "template": "Between G5.2 and G5.3 codes, only additional G5.2 codes are allowed.",
    "symbols": [],
    "title": "NURBS 定义期间混入其他指令",
    "explanation": "G5.2 开始的曲线还没用 G5.3 收尾，中间却插入了不允许的其他指令。",
    "animation": "program"
  },
  {
    "template": "BUG: Invalid plane in comp_get_programmed",
    "symbols": [],
    "title": "刀补编程位置的平面状态异常",
    "explanation": "软件读取刀补前的目标位置时，发现当前加工平面不合法，无法继续换算。",
    "animation": "tool-setup"
  },
  {
    "template": "Cannot change axis offsets with cutter radius comp",
    "symbols": [
      "NCE_CANNOT_CHANGE_AXIS_OFFSETS_WITH_CUTTER_RADIUS_COMP"
    ],
    "title": "刀补开启时修改轴偏移",
    "explanation": "软件正在替刀具宽度挪动路线，你又要改坐标零点，原来的路线关系会被打乱。",
    "animation": "tool-setup"
  },
  {
    "template": "Invalid absolute position %5.2f for wrapped rotary axis %c",
    "symbols": [],
    "title": "循环旋转轴的绝对角度非法",
    "explanation": "这个旋转轴按一圈内的角度表示位置，程序给的绝对角度不符合该轴的表示规则。",
    "animation": "coordinate"
  },
  {
    "template": "BUG: Invalid plane in comp_set_programmed",
    "symbols": [],
    "title": "刀补编程位置写入平面异常",
    "explanation": "软件保存刀补前的位置时，当前平面状态不合法，无法确定坐标怎么放。",
    "animation": "tool-setup"
  },
  {
    "template": "Bug code not in g52 or g92 series",
    "symbols": [
      "NCE_BUG_CODE_NOT_IN_G52_G92_SERIES"
    ],
    "title": "坐标偏移指令类型异常",
    "explanation": "软件进入了处理 G52/G92 偏移的步骤，却收到了其他指令。",
    "animation": "coordinate"
  },
  {
    "template": "Named parameter not terminated",
    "symbols": [
      "NCE_NAMED_PARAMETER_NOT_TERMINATED"
    ],
    "title": "命名参数名称未闭合",
    "explanation": "类似 #<名字> 的参数少了结尾的 >，软件不知道名字在哪里结束。",
    "animation": "program"
  },
  {
    "template": "You must specify both X and Y coordinates for Control Points",
    "symbols": [],
    "title": "曲线控制点缺少 X 或 Y",
    "explanation": "一个曲线控制点需要完整的 X、Y 位置，当前只给了一部分。",
    "animation": "program"
  },
  {
    "template": "Can specify P without X and Y only for the first control point",
    "symbols": [],
    "title": "控制点 P 参数缺少对应位置",
    "explanation": "只有第一个控制点能单独给 P；后续点还必须给出 X、Y 位置。",
    "animation": "program"
  },
  {
    "template": "Must specify positive weight P for every Control Point",
    "symbols": [],
    "title": "曲线控制点权重 P 无效",
    "explanation": "每个控制点都要给一个大于零的权重，当前没给或给成了零、负数。",
    "animation": "program"
  },
  {
    "template": "Cannot make a NURBS with 0 feedrate",
    "symbols": [],
    "title": "NURBS 曲线进给速度为零",
    "explanation": "程序要求沿曲线切削，却把前进速度设成了零，刀具没法往前走。",
    "animation": "feed-zero"
  },
  {
    "template": "Cannot change control mode with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时切换路径控制模式",
    "explanation": "刀具路线正在做补偿，不能在这时切换精确停靠或连续走刀方式。",
    "animation": "tool-setup"
  },
  {
    "template": "Bug code not g61 g61.1 or g64",
    "symbols": [
      "NCE_BUG_CODE_NOT_G61_G61_1_OR_G64"
    ],
    "title": "路径控制模式指令异常",
    "explanation": "软件准备处理 G61、G61.1 或 G64，却收到不属于这些模式的指令。",
    "animation": "processing"
  },
  {
    "template": "Cannot change coordinate systems with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时切换工件坐标系",
    "explanation": "正在补偿刀具宽度时，又从一个工件零点切换到另一个，软件不允许这样接着走。",
    "animation": "tool-setup"
  },
  {
    "template": "Bug code not in range g54 to g593",
    "symbols": [
      "NCE_BUG_CODE_NOT_IN_RANGE_G54_TO_G593"
    ],
    "title": "工件坐标系指令超出内部预期",
    "explanation": "软件进入了选择 G54 到 G59.3 的流程，却收到不在其中的指令。",
    "animation": "coordinate"
  },
  {
    "template": "BUG: Code not G40, G41, G41.1, G42, G42.1",
    "symbols": [],
    "title": "刀具半径补偿指令类型异常",
    "explanation": "当前处理步骤只接受 G40、G41、G41.1、G42、G42.1，却收到了别的指令。",
    "animation": "tool-setup"
  },
  {
    "template": "Cannot use G5.3 without G5.2 first",
    "symbols": [],
    "title": "NURBS 结束前未开始定义",
    "explanation": "程序用 G5.3 结束一条曲线，但前面没有用 G5.2 开始它。",
    "animation": "program"
  },
  {
    "template": "You must specify a number of control points at least equal to the order L = %d",
    "symbols": [],
    "title": "NURBS 控制点数量不足",
    "explanation": "曲线要求的阶数较高，但给的控制点太少，凑不出这条曲线。",
    "animation": "program"
  },
  {
    "template": "Cutter radius compensation allowed only in XY, XZ planes",
    "symbols": [
      "NCE_RADIUS_COMP_ONLY_IN_XY_OR_XZ"
    ],
    "title": "刀具半径补偿平面不支持",
    "explanation": "当前刀补只支持 XY 或 XZ 平面，程序选了其他平面。",
    "animation": "tool-setup"
  },
  {
    "template": "Cannot turn cutter radius comp on when on",
    "symbols": [
      "NCE_CANNOT_TURN_CUTTER_RADIUS_COMP_ON_WHEN_ON"
    ],
    "title": "刀补已开启却再次开启",
    "explanation": "刀具半径补偿还没关掉，程序又发了一次开启指令。",
    "animation": "tool-setup"
  },
  {
    "template": "G%d.1 with no D word",
    "symbols": [],
    "title": "动态刀补缺少 D 参数",
    "explanation": "程序开启直接指定刀具尺寸的补偿，却没用 D 告诉软件刀具尺寸。",
    "animation": "tool-setup"
  },
  {
    "template": "G%d.1 with L word, but plane is not G18",
    "symbols": [],
    "title": "刀补方向参数 L 用错平面",
    "explanation": "这个 L 参数用于 XZ 平面的车削刀具方向，当前却不是 G18 平面。",
    "animation": "tool-setup"
  },
  {
    "template": "G%d requires D word to be a whole number",
    "symbols": [],
    "title": "刀补索引 D 不是整数",
    "explanation": "这里的 D 是刀具表编号，不是直接填刀具尺寸，所以不能用小数。",
    "animation": "tool-setup"
  },
  {
    "template": "Negative d word tool radius index used",
    "symbols": [
      "NCE_NEGATIVE_D_WORD_TOOL_RADIUS_INDEX_USED"
    ],
    "title": "刀补索引 D 为负数",
    "explanation": "刀具表编号不能是负数，当前 D 无法对应有效的刀具数据。",
    "animation": "tool-setup"
  },
  {
    "template": "G%d with lathe tool, but plane is not G18",
    "symbols": [],
    "title": "车刀补偿使用了错误平面",
    "explanation": "选择了车刀类型的补偿，但没有在要求的 XZ 平面 G18 中加工。",
    "animation": "tool-setup"
  },
  {
    "template": "Bug code not g90 or g91",
    "symbols": [
      "NCE_BUG_CODE_NOT_G90_OR_G91"
    ],
    "title": "绝对／增量坐标模式异常",
    "explanation": "软件需要判断 G90 或 G91，却收到其他模式，无法解释后面的坐标。",
    "animation": "coordinate"
  },
  {
    "template": "BUG: Code not G7 or G8",
    "symbols": [],
    "title": "车床直径／半径模式异常",
    "explanation": "软件要处理 G7 或 G8 的尺寸表示方式，却收到了不相符的指令。",
    "animation": "processing"
  },
  {
    "template": "Cannot convert spline with cutter radius compensation",
    "symbols": [],
    "title": "样条曲线不支持当前刀补",
    "explanation": "这段平滑曲线不能在刀具半径补偿开启时直接转换成运动。",
    "animation": "tool-setup"
  },
  {
    "template": "BUG: Code not G93, G94, or G95",
    "symbols": [],
    "title": "进给单位模式异常",
    "explanation": "软件需要 G93、G94 或 G95 中的一种进给模式，当前状态不在这三种里。",
    "animation": "processing"
  },
  {
    "template": "Cannot make arc with zero feed rate",
    "symbols": [
      "NCE_CANNOT_MAKE_ARC_WITH_ZERO_FEED_RATE"
    ],
    "title": "圆弧进给速度为零",
    "explanation": "要求刀具走圆弧，却没有设置大于零的进给速度。",
    "animation": "feed-zero"
  },
  {
    "template": "F word missing with inverse time arc move",
    "symbols": [
      "NCE_F_WORD_MISSING_WITH_INVERSE_TIME_ARC_MOVE"
    ],
    "title": "逆时间圆弧缺少 F 参数",
    "explanation": "G93 模式下，每段圆弧都要单独给 F，说明这段要用多长时间走完。",
    "animation": "program"
  },
  {
    "template": "Splines must be in the XY plane",
    "symbols": [],
    "title": "样条曲线平面不支持",
    "explanation": "当前样条实现只支持 XY 平面，程序却放到了其他平面。",
    "animation": "coordinate"
  },
  {
    "template": "Splines may not have motion in Z, A, B, or C",
    "symbols": [],
    "title": "样条曲线混入其他轴运动",
    "explanation": "这段样条只允许 XY 运动，程序还要求 Z 或旋转轴一起动。",
    "animation": "coordinate"
  },
  {
    "template": "Must specify both I and J with G5.1",
    "symbols": [],
    "title": "G5.1 缺少完整的 I、J 参数",
    "explanation": "这条曲线需要 I 和 J 一起描述控制点，当前至少缺了一个。",
    "animation": "program"
  },
  {
    "template": "Cannot set reference point with cutter compensation in effect",
    "symbols": [],
    "title": "刀补开启时设置参考点",
    "explanation": "刀具位置正在受补偿影响，软件不允许这时把它保存为参考位置。",
    "animation": "tool-setup"
  },
  {
    "template": "BUG: Code not G28.1 or G38.1",
    "symbols": [],
    "title": "参考点设置指令类型异常",
    "explanation": "软件进入保存参考点的流程，却没有收到它预期的指令类型。",
    "animation": "processing"
  },
  {
    "template": "Cannot use g28 or g30 with cutter radius comp",
    "symbols": [
      "NCE_CANNOT_USE_G28_OR_G30_WITH_CUTTER_RADIUS_COMP"
    ],
    "title": "刀补开启时执行 G28／G30",
    "explanation": "刀补没关闭，程序就要求返回保存的参考位置，软件拒绝这组操作。",
    "animation": "tool-setup"
  },
  {
    "template": "Must specify both I and J, or neither",
    "symbols": [],
    "title": "样条的 I、J 参数不成对",
    "explanation": "I、J 要么同时写，要么都省略；只写一个会让曲线定义不完整。",
    "animation": "program"
  },
  {
    "template": "Bug code not g28 or g30",
    "symbols": [
      "NCE_BUG_CODE_NOT_G28_OR_G30"
    ],
    "title": "返回参考点指令类型异常",
    "explanation": "当前步骤应该处理 G28 或 G30，却收到了别的指令。",
    "animation": "processing"
  },
  {
    "template": "Must specify both P and Q with G5",
    "symbols": [],
    "title": "G5 缺少完整的 P、Q 参数",
    "explanation": "三次样条需要 P 和 Q 一起描述末端控制点，当前至少缺一个。",
    "animation": "program"
  },
  {
    "template": "Bug code not g20 or g21",
    "symbols": [
      "NCE_BUG_CODE_NOT_G20_OR_G21"
    ],
    "title": "长度单位指令类型异常",
    "explanation": "软件切换单位时应该收到 G20 英寸或 G21 毫米，当前指令不符合要求。",
    "animation": "processing"
  },
  {
    "template": "gen_restore G20/G21 failed: '%s'",
    "symbols": [],
    "title": "恢复长度单位失败",
    "explanation": "软件想恢复之前保存的毫米／英寸设置，但执行恢复指令失败了。",
    "animation": "program"
  },
  {
    "template": "BUG: cannot restore from a lower call level (%d) to a higher call level (%d)",
    "symbols": [],
    "title": "解释器调用层级恢复方向异常",
    "explanation": "软件试图把外层状态恢复到更深的调用层，保存和恢复的层级对不上。",
    "animation": "processing"
  },
  {
    "template": "BUG: restore from level %d !?",
    "symbols": [],
    "title": "解释器恢复来源层级异常",
    "explanation": "软件找不到合法的状态来源，不能恢复之前的加工设置。",
    "animation": "processing"
  },
  {
    "template": "BUG: restore to level %d !?",
    "symbols": [],
    "title": "解释器恢复目标层级异常",
    "explanation": "软件准备把状态恢复到一个不合法的调用层，内部记录对不上。",
    "animation": "processing"
  },
  {
    "template": "M7x: restore_settings G20/G21 failed: '%s'",
    "symbols": [],
    "title": "M7x 恢复长度单位失败",
    "explanation": "恢复保存的加工设置时，毫米或英寸模式没能恢复成功。",
    "animation": "program"
  },
  {
    "template": "M7x: restore_settings failed executing: '%s': %s",
    "symbols": [],
    "title": "M7x 恢复加工设置失败",
    "explanation": "软件执行一条恢复指令时失败，原文会指出是哪条指令以及原因。",
    "animation": "program"
  },
  {
    "template": "Failed to restore interp state on abort '%s': %s",
    "symbols": [],
    "title": "中止后恢复解释器状态失败",
    "explanation": "程序已经中止，但软件没能恢复之前保存的设置；需要查看附带的具体原因。",
    "animation": "program"
  },
  {
    "template": "Cannot set motion output with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时设置运动输出",
    "explanation": "当前输出操作与刀补流程不兼容，不能一边补偿路线一边执行它。",
    "animation": "tool-setup"
  },
  {
    "template": "No valid P word with M62",
    "symbols": [],
    "title": "M62 缺少有效输出编号 P",
    "explanation": "程序要设置一个数字输出，却没有指出一个合法的输出口编号。",
    "animation": "program"
  },
  {
    "template": "Cannot set motion digital output with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时设置同步数字输出",
    "explanation": "这条跟随运动生效的数字输出指令，不能在刀补开启时执行。",
    "animation": "tool-setup"
  },
  {
    "template": "No valid P word with M63",
    "symbols": [],
    "title": "M63 缺少有效输出编号 P",
    "explanation": "程序要清除一个数字输出，却没有给出有效的输出口编号。",
    "animation": "program"
  },
  {
    "template": "Cannot set auxiliary digital output with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时设置辅助数字输出",
    "explanation": "程序想立即改变数字输出，但当前刀补状态不允许这项操作。",
    "animation": "tool-setup"
  },
  {
    "template": "No valid P word with M64",
    "symbols": [],
    "title": "M64 缺少有效输出编号 P",
    "explanation": "程序要立即打开数字输出，却没给出合法的输出口编号。",
    "animation": "program"
  },
  {
    "template": "No valid P word with M65",
    "symbols": [],
    "title": "M65 缺少有效输出编号 P",
    "explanation": "程序要立即关闭数字输出，却没给出合法的输出口编号。",
    "animation": "program"
  },
  {
    "template": "Invalid to select both a digital and an analog input with M66",
    "symbols": [
      "NCE_BOTH_DIGITAL_AND_ANALOG_INPUT_SELECTED"
    ],
    "title": "M66 同时选择了两类输入",
    "explanation": "程序一边选开关量输入，一边选数值型输入；一次只能读其中一种。",
    "animation": "program"
  },
  {
    "template": "Zero timeout with wait type != immediate return",
    "symbols": [
      "NCE_ZERO_TIMEOUT_WITH_WAIT_NOT_IMMEDIATE"
    ],
    "title": "等待输入的超时时间为零",
    "explanation": "程序要求等待信号变化，却把允许等待的时间设成了零。",
    "animation": "program"
  },
  {
    "template": "Can't select analog input with wait type != immediate return",
    "symbols": [
      "NCE_ANALOG_INPUT_WITH_WAIT_NOT_IMMEDIATE"
    ],
    "title": "模拟量输入不支持这种等待方式",
    "explanation": "这个数值型输入只能立即读取，不能使用当前选择的等待触发方式。",
    "animation": "program"
  },
  {
    "template": "Need to have either a valid P or a valid E word with M66",
    "symbols": [
      "NCE_INVALID_OR_MISSING_P_AND_E_WORDS_FOR_WAIT_INPUT"
    ],
    "title": "M66 缺少有效输入选择",
    "explanation": "程序想读输入，却没有用合法的 P 或 E 指明读哪一个口。",
    "animation": "program"
  },
  {
    "template": "invalid P-word with M66",
    "symbols": [],
    "title": "M66 的 P 输入编号无效",
    "explanation": "给出的数字输入口编号不符合当前指令要求。",
    "animation": "program"
  },
  {
    "template": "Cannot wait for digital input with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时等待数字输入",
    "explanation": "程序在刀补进行中要求停下来等一个开关信号，这种组合不被允许。",
    "animation": "tool-setup"
  },
  {
    "template": "Digital input selected out of bounds",
    "symbols": [
      "NCE_DIGITAL_INPUT_INVALID_ON_M66"
    ],
    "title": "数字输入口编号越界",
    "explanation": "程序要读的输入口编号，超过了机床配置里实际可用的范围。",
    "animation": "parameters"
  },
  {
    "template": "Cannot wait for analog input with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时等待模拟输入",
    "explanation": "程序在刀补进行中要求等待一个数值型输入，这种组合不被允许。",
    "animation": "tool-setup"
  },
  {
    "template": "Analog input selected out of bounds",
    "symbols": [
      "NCE_ANALOG_INPUT_INVALID_ON_M66"
    ],
    "title": "模拟输入口编号越界",
    "explanation": "程序要读的模拟输入口编号，不在已配置的可用范围内。",
    "animation": "program"
  },
  {
    "template": "Cannot set motion analog output with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时设置同步模拟输出",
    "explanation": "当前刀补状态不允许执行这条随运动生效的数值输出指令。",
    "animation": "tool-setup"
  },
  {
    "template": "Invalid analog index with M67",
    "symbols": [],
    "title": "M67 模拟输出口编号无效",
    "explanation": "程序要写入数值的模拟输出口不存在，或编号格式不合法。",
    "animation": "program"
  },
  {
    "template": "Cannot set auxiliary analog output with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时设置辅助模拟输出",
    "explanation": "程序想立即改变模拟输出，但当前刀补状态不允许这项操作。",
    "animation": "tool-setup"
  },
  {
    "template": "Invalid analog index with M68",
    "symbols": [],
    "title": "M68 模拟输出口编号无效",
    "explanation": "程序要立即写入数值的输出口编号不合法。",
    "animation": "program"
  },
  {
    "template": "Need non-negative Q-word to specify tool number with M61",
    "symbols": [],
    "title": "M61 缺少合法刀号 Q",
    "explanation": "要登记当前装上的刀具，必须给一个不小于零的刀号，当前 Q 不符合要求。",
    "animation": "program"
  },
  {
    "template": "Spindle ($) number out of range in M3 Command\nnum_spindles =%i. $=%d\n",
    "symbols": [],
    "title": "M3 主轴编号越界",
    "explanation": "程序要启动的那根主轴不在配置里。原文会给出可用主轴数和你选的编号。",
    "animation": "spindle-setup"
  },
  {
    "template": "Spindle ($) number out of range in M4 Command\nnum_spindles =%i. $=%d\n",
    "symbols": [],
    "title": "M4 主轴编号越界",
    "explanation": "程序要反转的那根主轴不在配置里，选中的编号超过了可用范围。",
    "animation": "spindle-setup"
  },
  {
    "template": "Spindle ($) number out of range in M5 Command\nnum_spindles =%i. $=%d\n",
    "symbols": [],
    "title": "M5 主轴编号越界",
    "explanation": "程序要停止的那根主轴不在配置里，软件找不到对应对象。",
    "animation": "spindle-setup"
  },
  {
    "template": "Spindle ($) number out of range in M19 Command",
    "symbols": [],
    "title": "M19 主轴定向编号越界",
    "explanation": "程序要给一根不存在的主轴做角度定位。",
    "animation": "spindle-setup"
  },
  {
    "template": "Q word with M19 requires a value > 0",
    "symbols": [],
    "title": "M19 的 Q 参数必须大于零",
    "explanation": "主轴定向使用的 Q 等待时间无效，不能填零或负数。",
    "animation": "program"
  },
  {
    "template": "Cannot restore context from invalid stack frame - missing M70/M73?",
    "symbols": [],
    "title": "缺少可恢复的加工状态",
    "explanation": "软件准备恢复之前的设置，却没有找到有效的保存记录，可能没有先执行 M70 或 M73。",
    "animation": "program"
  },
  {
    "template": "Cannot enable overrides with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时启用倍率控制",
    "explanation": "刀补还在进行，不能在这时打开当前这种进给或主轴倍率控制。",
    "animation": "tool-setup"
  },
  {
    "template": "Cannot disable overrides with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时禁用倍率控制",
    "explanation": "刀补还在进行，不能在这时关闭当前这种倍率控制。",
    "animation": "tool-setup"
  },
  {
    "template": "Invalid spindle ($) number in M51 command",
    "symbols": [],
    "title": "M51 主轴编号无效",
    "explanation": "程序要修改某根主轴的倍率开关，但选择的主轴编号不存在。",
    "animation": "spindle-setup"
  },
  {
    "template": "Unknown m code used: M%d",
    "symbols": [
      "NCE_UNKNOWN_M_CODE_USED"
    ],
    "title": "未知 M 指令",
    "explanation": "软件不认识这个 M 编号，或没有配置它对应的自定义功能。",
    "animation": "program"
  },
  {
    "template": "G10 L0 not allowed with loaded tool <%d>\n",
    "symbols": [],
    "title": "装刀状态下禁止 G10 L0",
    "explanation": "当前有刀具处于装载状态，不能执行这项刀具表操作。",
    "animation": "program"
  },
  {
    "template": "Bug code not g4 g10 g28 g30 g52 g53 or g92 series",
    "symbols": [
      "NCE_BUG_CODE_NOT_G4_G10_G28_G30_G52_G53_OR_G92_SERIES"
    ],
    "title": "非运动指令转换类型异常",
    "explanation": "软件进入了处理暂停、设偏移或参考点的步骤，却收到其他类型的指令。",
    "animation": "processing"
  },
  {
    "template": "Indexing axis %c can only be moved with G0",
    "symbols": [],
    "title": "分度轴只允许 G0 运动",
    "explanation": "这个轴被配置成定位分度轴，只能快速定位，不能按普通切削进给方式走。",
    "animation": "coordinate"
  },
  {
    "template": "Indexing axis %c can only be moved alone",
    "symbols": [],
    "title": "分度轴必须单独运动",
    "explanation": "程序让分度轴和其他轴同时移动，但该轴的配置要求它单独完成定位。",
    "animation": "coordinate"
  },
  {
    "template": "The move just after exiting cutter compensation mode must be straight, not an arc",
    "symbols": [],
    "title": "退出刀补后的首段必须是直线",
    "explanation": "刚关掉刀补就接一段圆弧，软件接不上这条路线；这里需要合适的直线退出段。",
    "animation": "tool-setup"
  },
  {
    "template": "Bug unknown motion code",
    "symbols": [
      "NCE_BUG_UNKNOWN_MOTION_CODE"
    ],
    "title": "未知运动指令类型",
    "explanation": "软件没有找到当前运动指令对应的处理方式。",
    "animation": "program"
  },
  {
    "template": "Cannot do an arc in planes G17.1, G18.1, or G19.1",
    "symbols": [],
    "title": "辅助坐标平面不支持圆弧",
    "explanation": "当前选了 UV、UW 或 VW 这类辅助平面，而这里的圆弧实现不支持它。",
    "animation": "coordinate"
  },
  {
    "template": "R i j k words all missing for arc",
    "symbols": [
      "NCE_R_I_J_K_WORDS_ALL_MISSING_FOR_ARC"
    ],
    "title": "圆弧缺少圆心或半径信息",
    "explanation": "程序只给了圆弧终点，却没有 R 半径，也没有足够的 I、J、K 圆心信息。",
    "animation": "program"
  },
  {
    "template": "Cannot probe with cutter radius comp on",
    "symbols": [
      "NCE_CANNOT_PROBE_WITH_CUTTER_RADIUS_COMP_ON"
    ],
    "title": "刀补开启时执行探测",
    "explanation": "刀补没关掉就开始测量接触点，软件不允许把这两种动作混用。",
    "animation": "tool-setup"
  },
  {
    "template": "Cannot probe with zero feed rate",
    "symbols": [
      "NCE_CANNOT_PROBE_WITH_ZERO_FEED_RATE"
    ],
    "title": "探测进给速度为零",
    "explanation": "程序要求探针移动测量，但没有设置有效的前进速度。",
    "animation": "feed-zero"
  },
  {
    "template": "Cannot probe with feed per rev mode",
    "symbols": [],
    "title": "探测不支持每转进给模式",
    "explanation": "探测动作不能按主轴每转一圈前进多少来计速，需要适用的进给模式。",
    "animation": "program"
  },
  {
    "template": "Start point too close to probe point",
    "symbols": [
      "NCE_START_POINT_TOO_CLOSE_TO_PROBE_POINT"
    ],
    "title": "探测起终点距离过小",
    "explanation": "探针要去的位置与当前位置几乎相同，没有足够距离执行探测。",
    "animation": "program"
  },
  {
    "template": "Mixed radius ijk format for arc",
    "symbols": [
      "NCE_MIXED_RADIUS_IJK_FORMAT_FOR_ARC"
    ],
    "title": "圆弧同时使用 R 和 IJK 定义",
    "explanation": "一段圆弧用了两套定义方式：既给半径，又给圆心偏移，软件不允许混写。",
    "animation": "program"
  },
  {
    "template": "Cannot change retract mode with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时切换退刀模式",
    "explanation": "刀补还在进行，程序就改变固定循环回到哪个高度的规则，当前组合不允许。",
    "animation": "tool-setup"
  },
  {
    "template": "Bug code not g98 or g99",
    "symbols": [
      "NCE_BUG_CODE_NOT_G98_OR_G99"
    ],
    "title": "固定循环退刀模式异常",
    "explanation": "软件预期 G98 或 G99 的退刀模式，却收到其他指令。",
    "animation": "processing"
  },
  {
    "template": "G10 L1 without offsets has no effect",
    "symbols": [],
    "title": "G10 L1 没有实际修改内容",
    "explanation": "程序要求修改刀具表，但没有提供任何需要修改的偏移数据。",
    "animation": "program"
  },
  {
    "template": "Cannot feed with zero spindle speed in feed per rev mode",
    "symbols": [],
    "title": "每转进给模式下主轴转速为零",
    "explanation": "进给量按主轴转数计算，但主轴速度是零，软件没法算出刀具该怎么前进。",
    "animation": "spindle-stop"
  },
  {
    "template": "K word given for arc in xy plane",
    "symbols": [
      "NCE_K_WORD_GIVEN_FOR_ARC_IN_XY_PLANE"
    ],
    "title": "XY 圆弧误用了 K 参数",
    "explanation": "XY 平面的圆心应由 I、J 描述，K 属于另一个方向，不能用在这里。",
    "animation": "program"
  },
  {
    "template": "Q number in G10 is not an integer",
    "symbols": [],
    "title": "G10 的 Q 参数不是整数",
    "explanation": "这里的 Q 用来选刀具方向，必须是整数编号，不能带小数。",
    "animation": "parameters"
  },
  {
    "template": "Invalid tool orientation",
    "symbols": [],
    "title": "刀具方向编号无效",
    "explanation": "给出的刀尖方向不在允许的编号里，软件无法判断刀具朝哪边。",
    "animation": "tool-setup"
  },
  {
    "template": "%c word missing in absolute center arc",
    "symbols": [],
    "title": "绝对圆心圆弧缺少坐标",
    "explanation": "当前用固定坐标表示圆心，但少了报错里指出的那个圆心坐标参数。",
    "animation": "coordinate"
  },
  {
    "template": "I J words not allowed with G10 L2",
    "symbols": [],
    "title": "G10 L2 不接受 I、J 参数",
    "explanation": "程序要设置工件坐标，却给了这项操作不使用的 I、J 参数。",
    "animation": "program"
  },
  {
    "template": "I word given for arc in yz plane",
    "symbols": [
      "NCE_I_WORD_GIVEN_FOR_ARC_IN_YZ_PLANE"
    ],
    "title": "YZ 圆弧误用了 I 参数",
    "explanation": "YZ 平面圆弧应使用 J、K 定义圆心，不能带 I。",
    "animation": "program"
  },
  {
    "template": "Cannot change the active coordinate system with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时修改当前工件坐标系",
    "explanation": "正在按当前零点做刀补，又要修改这个零点，软件无法保持原来的路径关系。",
    "animation": "tool-setup"
  },
  {
    "template": "R not allowed in G10 L20",
    "symbols": [],
    "title": "G10 L20 不允许 R 参数",
    "explanation": "这条根据当前位置设置零点的指令不接受 R，程序多给了一个不适用的参数。",
    "animation": "program"
  },
  {
    "template": "J word given for arc in xz plane",
    "symbols": [
      "NCE_J_WORD_GIVEN_FOR_ARC_IN_XZ_PLANE"
    ],
    "title": "XZ 圆弧误用了 J 参数",
    "explanation": "XZ 平面圆弧应使用 I、K 定义圆心，不能带 J。",
    "animation": "program"
  },
  {
    "template": "Cannot change planes with cutter radius compensation on",
    "symbols": [
      "NCE_CANNOT_CHANGE_PLANES_WITH_CUTTER_RADIUS_COMP_ON"
    ],
    "title": "刀补开启时切换加工平面",
    "explanation": "刀补还没结束，就从一个平面切换到另一个，软件不允许这样衔接。",
    "animation": "tool-setup"
  },
  {
    "template": "Bug code not g17 g18 or g19",
    "symbols": [
      "NCE_BUG_CODE_NOT_G17_G18_OR_G19"
    ],
    "title": "加工平面选择指令异常",
    "explanation": "软件要处理 G17、G18 或 G19，却收到其他类型的指令。",
    "animation": "coordinate"
  },
  {
    "template": "Bug plane not xy yz or xz",
    "symbols": [
      "NCE_BUG_PLANE_NOT_XY_YZ_OR_XZ"
    ],
    "title": "加工平面内部状态异常",
    "explanation": "软件当前记录的平面不是合法的 XY、YZ 或 XZ，无法继续计算。",
    "animation": "coordinate"
  },
  {
    "template": "X and y words missing for arc in xy plane",
    "symbols": [
      "NCE_X_AND_Y_WORDS_MISSING_FOR_ARC_IN_XY_PLANE"
    ],
    "title": "XY 圆弧缺少终点坐标",
    "explanation": "程序要在 XY 平面画弧，却没有给出这条指令所需的 X 或 Y 终点信息。",
    "animation": "coordinate"
  },
  {
    "template": "Bug:  Reached convert_stop() from M99 as subprogram return",
    "symbols": [],
    "title": "子程序返回被误送入停止流程",
    "explanation": "M99 本该返回上层程序，却走进了停止指令的处理分支，属于内部流程异常。",
    "animation": "program"
  },
  {
    "template": "Y and z words missing for arc in yz plane",
    "symbols": [
      "NCE_Y_AND_Z_WORDS_MISSING_FOR_ARC_IN_YZ_PLANE"
    ],
    "title": "YZ 圆弧缺少终点坐标",
    "explanation": "程序要在 YZ 平面画弧，却没给出所需的 Y 或 Z 终点信息。",
    "animation": "coordinate"
  },
  {
    "template": "X and z words missing for arc in xz plane",
    "symbols": [
      "NCE_X_AND_Z_WORDS_MISSING_FOR_ARC_IN_XZ_PLANE"
    ],
    "title": "XZ 圆弧缺少终点坐标",
    "explanation": "程序要在 XZ 平面画弧，却没给出所需的 X 或 Z 终点信息。",
    "animation": "coordinate"
  },
  {
    "template": "Bug code not m0 m1 m2 m30 m60 m99",
    "symbols": [
      "NCE_BUG_CODE_NOT_M0_M1_M2_M30_M60_M99"
    ],
    "title": "停止／结束指令类型异常",
    "explanation": "软件进入了暂停或结束程序的流程，却收到不在支持列表内的指令。",
    "animation": "processing"
  },
  {
    "template": "Cannot do g1 with zero feed rate",
    "symbols": [
      "NCE_CANNOT_DO_G1_WITH_ZERO_FEED_RATE"
    ],
    "title": "直线切削进给速度为零",
    "explanation": "程序要求 G1 切削移动，但没有给出大于零的进给速度。",
    "animation": "feed-zero"
  },
  {
    "template": "F word missing with inverse time g1 move",
    "symbols": [
      "NCE_F_WORD_MISSING_WITH_INVERSE_TIME_G1_MOVE"
    ],
    "title": "逆时间直线运动缺少 F 参数",
    "explanation": "G93 模式下每段直线都要给 F，说明这段需要多长时间完成。",
    "animation": "program"
  },
  {
    "template": "Cannot use g53 with cutter radius comp",
    "symbols": [
      "NCE_CANNOT_USE_G53_WITH_CUTTER_RADIUS_COMP"
    ],
    "title": "刀补开启时使用 G53",
    "explanation": "当前路线按刀具半径做了偏移，程序又要求直接走机器坐标，这种组合不允许。",
    "animation": "tool-setup"
  },
  {
    "template": "BUG: Invalid plane for cutter compensation",
    "symbols": [],
    "title": "刀补加工平面无效",
    "explanation": "软件当前记录的平面不能用于这一步刀补计算。",
    "animation": "tool-setup"
  },
  {
    "template": "Invalid spindle ($) number in G33 move",
    "symbols": [],
    "title": "G33 选择的主轴编号无效",
    "explanation": "这条螺纹同步运动选中了不存在的主轴，无法获取对应的旋转同步关系。",
    "animation": "spindle-setup"
  },
  {
    "template": "Spindle not turning in G33",
    "symbols": [],
    "title": "G33 执行时主轴未转动",
    "explanation": "螺纹运动需要跟着主轴转动前进，但主轴当前没有转。",
    "animation": "spindle-stop"
  },
  {
    "template": "Invalid spindle ($) number in G33.1 move",
    "symbols": [],
    "title": "G33.1 选择的主轴编号无效",
    "explanation": "刚性攻丝选中了无效的主轴编号，无法建立旋转同步。",
    "animation": "spindle-setup"
  },
  {
    "template": "Spindle not turning in G33.1",
    "symbols": [],
    "title": "G33.1 执行时主轴未转动",
    "explanation": "刚性攻丝要跟随主轴旋转，但主轴还没有启动。",
    "animation": "spindle-stop"
  },
  {
    "template": "Invalid D-number in G76 cycle",
    "symbols": [],
    "title": "G76 的主轴选择编号无效",
    "explanation": "原文写 D-number，但这处代码实际检查的是 $ 主轴编号。选中的主轴不存在，不是让你去改 D 切深参数。",
    "animation": "spindle-setup"
  },
  {
    "template": "Chosen spindle (%i) not turning in G76",
    "symbols": [],
    "title": "G76 所选主轴未转动",
    "explanation": "螺纹循环已经准备开始，但它选中的那根主轴没有转动。",
    "animation": "spindle-stop"
  },
  {
    "template": "Cannot move rotary axes with G76",
    "symbols": [
      "NCE_CANNOT_MOVE_ROTARY_AXES_WITH_G76"
    ],
    "title": "G76 不允许旋转轴运动",
    "explanation": "这条螺纹循环里混入了旋转轴移动，当前实现不接受这种组合。",
    "animation": "coordinate"
  },
  {
    "template": "Bug code not g0 or g1",
    "symbols": [
      "NCE_BUG_CODE_NOT_G0_OR_G1"
    ],
    "title": "直线运动转换指令异常",
    "explanation": "软件进入了 G0/G1 的处理步骤，却收到其他类型的指令。",
    "animation": "processing"
  },
  {
    "template": "BUG: An axis incorrectly moved along with an indexer",
    "symbols": [],
    "title": "分度时其他轴发生了非预期运动",
    "explanation": "内部计算让本应独立定位的分度轴带着其他轴一起动，违反了分度约束。",
    "animation": "coordinate"
  },
  {
    "template": "BUG: trying to index incorrect axis",
    "symbols": [],
    "title": "内部选择了错误的分度轴",
    "explanation": "软件正在给一个不该执行分度的轴安排分度动作。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot use G76 threading cycle with cutter radius compensation on",
    "symbols": [],
    "title": "G76 螺纹循环不允许刀补",
    "explanation": "螺纹循环开始时半径补偿仍然开着，这种组合无法执行。",
    "animation": "tool-setup"
  },
  {
    "template": "In G76, I must not be 0",
    "symbols": [],
    "title": "G76 的 I 参数不能为零",
    "explanation": "螺纹循环需要一个非零的起刀偏移，当前填零无法确定所需的切削关系。",
    "animation": "program"
  },
  {
    "template": "In G76, J must be greater than 0",
    "symbols": [],
    "title": "G76 的 J 参数必须大于零",
    "explanation": "螺纹第一刀的切深必须是正数，不能不切或反向给一个负值。",
    "animation": "program"
  },
  {
    "template": "In G76, K must be greater than J",
    "symbols": [],
    "title": "G76 的 K 参数必须大于 J",
    "explanation": "螺纹总切深要大于第一刀切深，当前参数把两者的大小关系写反或写成相等了。",
    "animation": "program"
  },
  {
    "template": "Bug side not right or left",
    "symbols": [
      "NCE_BUG_SIDE_NOT_RIGHT_OR_LEFT"
    ],
    "title": "刀补左右方向内部状态异常",
    "explanation": "软件需要明确往轮廓左边还是右边偏移，但当前记录既不是左也不是右。",
    "animation": "tool-setup"
  },
  {
    "template": "Length of cutter compensation entry move is not greater than the tool radius",
    "symbols": [],
    "title": "刀补引入直线长度不足",
    "explanation": "开始刀补时，需要一段足够长的直线让刀具挪到补偿位置。当前这段不比刀具半径长，挪不过去。",
    "animation": "entry-length"
  },
  {
    "template": "Zero degree inside corner is invalid for cutter compensation",
    "symbols": [],
    "title": "刀补轮廓出现零度内角",
    "explanation": "轮廓在内角处几乎原路折返，刀具没有空间完成这个转弯。",
    "animation": "tool-setup"
  },
  {
    "template": "Arc to straight motion makes a corner the compensated tool can't fit in without gouging",
    "symbols": [],
    "title": "圆弧接直线的刀补路径发生干涉",
    "explanation": "从圆弧转到直线时，拐角太挤，按当前刀具尺寸走会多切到不该切掉的材料。",
    "animation": "tool-setup"
  },
  {
    "template": "Need tool prepared -Txx- for toolchange",
    "symbols": [
      "NCE_TXX_MISSING_FOR_M6"
    ],
    "title": "换刀前未准备刀号",
    "explanation": "程序发了换刀指令，却还没有先用 T 指定要换哪把刀。",
    "animation": "tool-setup"
  },
  {
    "template": "Cannot change tools with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时换刀",
    "explanation": "旧刀的半径补偿还没结束，程序就要换另一把刀，软件不允许这样衔接。",
    "animation": "tool-setup"
  },
  {
    "template": "Cannot change tool offset with cutter radius compensation on",
    "symbols": [],
    "title": "刀补开启时修改刀具偏移",
    "explanation": "软件正按当前刀具尺寸计算路线，这时又改刀具偏移，会让补偿关系失效。",
    "animation": "tool-setup"
  },
  {
    "template": "G43.2: Can not have both H and axis words",
    "symbols": [],
    "title": "G43.2 的补偿来源冲突",
    "explanation": "程序同时给了 H 刀具表编号和轴偏移数值，但这次操作只能选择一种来源。",
    "animation": "program"
  },
  {
    "template": "G43.2: No axes specified and H word missing",
    "symbols": [],
    "title": "G43.2 缺少补偿来源",
    "explanation": "程序要求叠加刀长偏移，却既没给 H 编号，也没给任何轴的偏移量。",
    "animation": "program"
  },
  {
    "template": "BUG: Code not G43, G43.1, G43.2, or G49",
    "symbols": [],
    "title": "刀长补偿指令类型异常",
    "explanation": "软件进入刀长偏移处理流程，却收到不属于 G43、G43.1、G43.2、G49 的指令。",
    "animation": "tool-setup"
  },
  {
    "template": "Radius of cutter compensation entry arc is not greater than the tool radius",
    "symbols": [],
    "title": "刀补引入圆弧半径不足",
    "explanation": "开始刀补的圆弧比刀具还紧，刀具中心无法沿它完成进入动作。",
    "animation": "tool-size"
  },
  {
    "template": "BUG: Invalid plane in comp_get_current",
    "symbols": [],
    "title": "刀补当前位置读取平面异常",
    "explanation": "软件读取补偿后的位置时，发现当前加工平面不受支持。",
    "animation": "tool-setup"
  },
  {
    "template": "Bug in tool radius comp",
    "symbols": [
      "NCE_BUG_IN_TOOL_RADIUS_COMP"
    ],
    "title": "刀具半径补偿内部异常",
    "explanation": "软件在刀补计算中遇到了不符合内部预期的状态，不能只根据这句话判断是哪个加工参数错了。",
    "animation": "tool-setup"
  },
  {
    "template": "BUG: Invalid plane in comp_set_current",
    "symbols": [],
    "title": "刀补当前位置写入平面异常",
    "explanation": "软件更新补偿后的位置时，当前平面状态不合法。",
    "animation": "tool-setup"
  },
  {
    "template": "Arc move in concave corner cannot be reached by the tool without gouging",
    "symbols": [],
    "title": "凹角圆弧刀补发生过切风险",
    "explanation": "这个向内凹的弯太小，刀具按补偿路线转过去时会切进应该保留的材料。",
    "animation": "tool-setup"
  },
  {
    "template": "Arc to arc motion is invalid because the arcs have the same center",
    "symbols": [],
    "title": "同圆心圆弧的刀补衔接无效",
    "explanation": "前后两段圆弧共用一个圆心，当前刀补衔接算法不能按这组条件建立连接。",
    "animation": "tool-setup"
  },
  {
    "template": "Arc to arc motion makes a corner the compensated tool can't fit in without gouging",
    "symbols": [],
    "title": "圆弧接圆弧的刀补路径发生干涉",
    "explanation": "两段圆弧接头处的空间不够，刀具挤进去会多切材料。",
    "animation": "tool-setup"
  },
  {
    "template": "Q word missing with g83",
    "symbols": [
      "NCE_Q_WORD_MISSING_WITH_G83"
    ],
    "title": "G83 深孔循环缺少 Q 参数",
    "explanation": "没有告诉软件每次往下钻多深再退刀，无法安排分次钻孔。",
    "animation": "program"
  },
  {
    "template": "Invalid spindle ($) number in G74/G84 cycle",
    "symbols": [],
    "title": "G74／G84 的主轴编号无效",
    "explanation": "攻丝循环选中的主轴编号不在机床配置里。",
    "animation": "spindle-setup"
  },
  {
    "template": "Dwell time p word missing with g86",
    "symbols": [
      "NCE_DWELL_TIME_P_WORD_MISSING_WITH_G86"
    ],
    "title": "G86 循环缺少停留时间 P",
    "explanation": "这条镗孔循环需要孔底停留时间，但程序没有给。",
    "animation": "program"
  },
  {
    "template": "I word missing with g87",
    "symbols": [
      "NCE_I_WORD_MISSING_WITH_G87"
    ],
    "title": "G87 循环缺少 I 偏移",
    "explanation": "背镗循环缺少 I 方向的偏移量，无法完整确定避让和切削路线。",
    "animation": "program"
  },
  {
    "template": "J word missing with g87",
    "symbols": [
      "NCE_J_WORD_MISSING_WITH_G87"
    ],
    "title": "G87 循环缺少 J 偏移",
    "explanation": "背镗循环缺少 J 方向的偏移量，路线信息不完整。",
    "animation": "program"
  },
  {
    "template": "K word missing with g87",
    "symbols": [
      "NCE_K_WORD_MISSING_WITH_G87"
    ],
    "title": "G87 循环缺少 K 偏移",
    "explanation": "背镗循环缺少 K 方向的偏移量，软件无法安排完整动作。",
    "animation": "program"
  },
  {
    "template": "Dwell time p word missing with g88",
    "symbols": [
      "NCE_DWELL_TIME_P_WORD_MISSING_WITH_G88"
    ],
    "title": "G88 循环缺少停留时间 P",
    "explanation": "这条镗孔循环需要在孔底停留，但没有写停留多久。",
    "animation": "program"
  },
  {
    "template": "Dwell time p word missing with g89",
    "symbols": [
      "NCE_DWELL_TIME_P_WORD_MISSING_WITH_G89"
    ],
    "title": "G89 循环缺少停留时间 P",
    "explanation": "这条镗孔循环要求孔底停留时间，当前参数里没有。",
    "animation": "program"
  },
  {
    "template": "Bug function should not have been called",
    "symbols": [
      "NCE_BUG_FUNCTION_SHOULD_NOT_HAVE_BEEN_CALLED"
    ],
    "title": "解释器调用了不应执行的函数",
    "explanation": "软件走到了正常情况下不该到达的处理分支，属于内部执行流程异常。",
    "animation": "parameters"
  },
  {
    "template": "W value unspecified in UV plane canned cycle",
    "symbols": [
      "NCE_W_VALUE_UNSPECIFIED_IN_UV_PLANE_CANNED_CYCLE"
    ],
    "title": "UV 平面固定循环缺少 W 目标位置",
    "explanation": "这套钻孔等循环沿 W 轴进刀，却没拿到该轴的目标位置，软件不知道要加工到哪里。",
    "animation": "coordinate"
  },
  {
    "template": "G17.1 canned cycle is not possible on a machine without W axis",
    "symbols": [],
    "title": "G17.1 固定循环需要 W 轴",
    "explanation": "当前机床配置没有 W 轴，但选中的 UV 平面循环需要沿它进刀，无法执行。",
    "animation": "coordinate"
  },
  {
    "template": "Bug distance mode not g90 or g91",
    "symbols": [
      "NCE_BUG_DISTANCE_MODE_NOT_G90_OR_G91"
    ],
    "title": "固定循环坐标模式异常",
    "explanation": "软件在计算循环位置时，既没得到合法的绝对模式，也没得到合法的增量模式。",
    "animation": "coordinate"
  },
  {
    "template": "R less than W in cycle in UV plane",
    "symbols": [
      "NCE_R_LESS_THAN_W_IN_CYCLE_IN_UV_PLANE"
    ],
    "title": "UV 平面循环的 R 平面低于 W 终点",
    "explanation": "R 指定的退刀／接近位置，比 W 轴的加工终点还小，颠倒了这类循环要求的位置关系。",
    "animation": "r-plane"
  },
  {
    "template": "Dwell time p word missing with g82",
    "symbols": [
      "NCE_DWELL_TIME_P_WORD_MISSING_WITH_G82"
    ],
    "title": "G82 循环缺少停留时间 P",
    "explanation": "程序要求钻到孔底后停一下，但没有给停留时间。",
    "animation": "program"
  },
  {
    "template": "Q word missing with g73",
    "symbols": [
      "NCE_Q_WORD_MISSING_WITH_G73"
    ],
    "title": "G73 排屑循环缺少 Q 参数",
    "explanation": "程序没有给每一小段钻进的深度，无法安排分次进刀排屑。",
    "animation": "program"
  },
  {
    "template": "X value unspecified in yz plane canned cycle",
    "symbols": [
      "NCE_X_VALUE_UNSPECIFIED_IN_YZ_PLANE_CANNED_CYCLE"
    ],
    "title": "YZ 平面固定循环缺少 X 目标位置",
    "explanation": "这套钻孔等循环沿 X 轴进刀，却没拿到该轴的目标位置，软件不知道要加工到哪里。",
    "animation": "coordinate"
  },
  {
    "template": "G19 canned cycle is not possible on a machine without X axis",
    "symbols": [],
    "title": "G19 固定循环需要 X 轴",
    "explanation": "当前机床配置没有 X 轴，但选中的 YZ 平面循环需要沿它进刀，无法执行。",
    "animation": "coordinate"
  },
  {
    "template": "R less than x in cycle in yz plane",
    "symbols": [
      "NCE_R_LESS_THAN_X_IN_CYCLE_IN_YZ_PLANE"
    ],
    "title": "YZ 平面循环的 R 平面低于 X 终点",
    "explanation": "R 指定的退刀／接近位置，比 X 轴的加工终点还小，颠倒了这类循环要求的位置关系。",
    "animation": "r-plane"
  },
  {
    "template": "Negative or zero q value used",
    "symbols": [
      "NCE_NEGATIVE_OR_ZERO_Q_VALUE_USED"
    ],
    "title": "分次进刀量 Q 非正数",
    "explanation": "每次钻进的深度必须大于零，当前给零或负数，无法往目标深度推进。",
    "animation": "program"
  },
  {
    "template": "U value unspecified in VW plane canned cycle",
    "symbols": [
      "NCE_U_VALUE_UNSPECIFIED_IN_VW_PLANE_CANNED_CYCLE"
    ],
    "title": "VW 平面固定循环缺少 U 目标位置",
    "explanation": "这套钻孔等循环沿 U 轴进刀，却没拿到该轴的目标位置，软件不知道要加工到哪里。",
    "animation": "coordinate"
  },
  {
    "template": "G19.1 canned cycle is not possible on a machine without U axis",
    "symbols": [],
    "title": "G19.1 固定循环需要 U 轴",
    "explanation": "当前机床配置没有 U 轴，但选中的 VW 平面循环需要沿它进刀，无法执行。",
    "animation": "coordinate"
  },
  {
    "template": "R less than U in cycle in VW plane",
    "symbols": [
      "NCE_R_LESS_THAN_U_IN_CYCLE_IN_VW_PLANE"
    ],
    "title": "VW 平面循环的 R 平面低于 U 终点",
    "explanation": "R 指定的退刀／接近位置，比 U 轴的加工终点还小，颠倒了这类循环要求的位置关系。",
    "animation": "r-plane"
  },
  {
    "template": "Y value unspecified in xz plane canned cycle",
    "symbols": [
      "NCE_Y_VALUE_UNSPECIFIED_IN_XZ_PLANE_CANNED_CYCLE"
    ],
    "title": "XZ 平面固定循环缺少 Y 目标位置",
    "explanation": "这套钻孔等循环沿 Y 轴进刀，却没拿到该轴的目标位置，软件不知道要加工到哪里。",
    "animation": "coordinate"
  },
  {
    "template": "G18 canned cycle is not possible on a machine without Y axis",
    "symbols": [],
    "title": "G18 固定循环需要 Y 轴",
    "explanation": "当前机床配置没有 Y 轴，但选中的 XZ 平面循环需要沿它进刀，无法执行。",
    "animation": "coordinate"
  },
  {
    "template": "R less than y in cycle in xz plane",
    "symbols": [
      "NCE_R_LESS_THAN_Y_IN_CYCLE_IN_XZ_PLANE"
    ],
    "title": "XZ 平面循环的 R 平面低于 Y 终点",
    "explanation": "R 指定的退刀／接近位置，比 Y 轴的加工终点还小，颠倒了这类循环要求的位置关系。",
    "animation": "r-plane"
  },
  {
    "template": "Invalid E-number in G74/G84 cycle",
    "symbols": [],
    "title": "攻丝循环的主轴选择编号无效",
    "explanation": "原文写 E-number，但这处代码实际检查的是 $ 主轴编号。它选中了不存在的主轴，不是让你去改 E 参数。",
    "animation": "spindle-setup"
  },
  {
    "template": "V value unspecified in UW plane canned cycle",
    "symbols": [
      "NCE_V_VALUE_UNSPECIFIED_IN_UW_PLANE_CANNED_CYCLE"
    ],
    "title": "UW 平面固定循环缺少 V 目标位置",
    "explanation": "这套钻孔等循环沿 V 轴进刀，却没拿到该轴的目标位置，软件不知道要加工到哪里。",
    "animation": "coordinate"
  },
  {
    "template": "G18.1 canned cycle is not possible on a machine without V axis",
    "symbols": [],
    "title": "G18.1 固定循环需要 V 轴",
    "explanation": "当前机床配置没有 V 轴，但选中的 UW 平面循环需要沿它进刀，无法执行。",
    "animation": "coordinate"
  },
  {
    "template": "R less than V in cycle in UW plane",
    "symbols": [
      "NCE_R_LESS_THAN_V_IN_CYCLE_IN_UW_PLANE"
    ],
    "title": "UW 平面循环的 R 平面低于 V 终点",
    "explanation": "R 指定的退刀／接近位置，比 V 轴的加工终点还小，颠倒了这类循环要求的位置关系。",
    "animation": "r-plane"
  },
  {
    "template": "Spindle not turning in %s",
    "symbols": [],
    "title": "当前循环要求的主轴未转动",
    "explanation": "程序已经准备执行需要旋转的循环，但选中的主轴没有在转。",
    "animation": "spindle-stop"
  },
  {
    "template": "Spindle turning clockwise in G74",
    "symbols": [],
    "title": "G74 左旋攻丝的主轴方向错误",
    "explanation": "该循环要求的转向与当前相反：程序需要左旋攻丝，主轴却在顺时针转。",
    "animation": "spindle-setup"
  },
  {
    "template": "Spindle turning counterclockwise in G84",
    "symbols": [],
    "title": "G84 右旋攻丝的主轴方向错误",
    "explanation": "该循环要求的转向与当前相反：程序需要右旋攻丝，主轴却在逆时针转。",
    "animation": "spindle-setup"
  },
  {
    "template": "Spindle state unknown for %s",
    "symbols": [],
    "title": "主轴旋转状态未知",
    "explanation": "软件无法确定主轴是正转、反转还是停止，不能据此继续当前循环。",
    "animation": "spindle-setup"
  },
  {
    "template": "%s for plane %s not implemented",
    "symbols": [],
    "title": "当前平面下的循环尚未实现",
    "explanation": "软件认识这条循环指令，但还不支持在你选的这个平面里执行。",
    "animation": "coordinate"
  },
  {
    "template": "Spindle not turning in g86",
    "symbols": [
      "NCE_SPINDLE_NOT_TURNING_IN_G86"
    ],
    "title": "G86 镗孔时主轴未转动",
    "explanation": "这条镗孔动作需要主轴先转起来，当前没有满足。",
    "animation": "spindle-stop"
  },
  {
    "template": "Spindle not turning in g87",
    "symbols": [
      "NCE_SPINDLE_NOT_TURNING_IN_G87"
    ],
    "title": "G87 背镗时主轴未转动",
    "explanation": "背镗循环需要刀具旋转，但主轴当前没转。",
    "animation": "spindle-stop"
  },
  {
    "template": "Spindle not turning in g88",
    "symbols": [
      "NCE_SPINDLE_NOT_TURNING_IN_G88"
    ],
    "title": "G88 镗孔时主轴未转动",
    "explanation": "程序要开始镗孔，可主轴还处于停止状态。",
    "animation": "spindle-stop"
  },
  {
    "template": "Cannot feed with zero feed rate",
    "symbols": [],
    "title": "切削进给速度为零",
    "explanation": "刀具被要求切削前进，但速度设成了零或没有有效设定。",
    "animation": "feed-zero"
  },
  {
    "template": "Cannot use inverse time feed with canned cycles",
    "symbols": [],
    "title": "固定循环不支持逆时间进给",
    "explanation": "自动钻孔等循环不能使用当前这种“按每段完成时间计速”的 G93 模式。",
    "animation": "program"
  },
  {
    "template": "Cannot use canned cycles with cutter compensation on",
    "symbols": [],
    "title": "固定循环不允许刀具半径补偿",
    "explanation": "刀补还开着就启动固定循环，软件不支持这种组合。",
    "animation": "tool-setup"
  },
  {
    "template": "R clearance plane unspecified in cycle",
    "symbols": [
      "NCE_R_CLEARANCE_PLANE_UNSPECIFIED_IN_CYCLE"
    ],
    "title": "固定循环缺少 R 退刀平面",
    "explanation": "程序没说明刀具钻孔前后应回到哪个准备高度，无法安排进退刀。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot do zero repeats of cycle",
    "symbols": [
      "NCE_CANNOT_DO_ZERO_REPEATS_OF_CYCLE"
    ],
    "title": "固定循环重复次数为零",
    "explanation": "程序让循环重复零次，这不是一个可执行的循环请求。",
    "animation": "program"
  },
  {
    "template": "Cannot put a U in a canned cycle in the %s plane",
    "symbols": [],
    "title": "当前平面固定循环不允许 U 参数",
    "explanation": "这套循环在选定平面中有自己的进刀轴和定位轴，不能再塞入这里的 U 轴参数。具体平面会填在原文的 %s 位置。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot put a V in a canned cycle in the %s plane",
    "symbols": [],
    "title": "当前平面固定循环不允许 V 参数",
    "explanation": "这套循环在选定平面中有自己的进刀轴和定位轴，不能再塞入这里的 V 轴参数。具体平面会填在原文的 %s 位置。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot put a W in a canned cycle in the %s plane",
    "symbols": [],
    "title": "当前平面固定循环不允许 W 参数",
    "explanation": "这套循环在选定平面中有自己的进刀轴和定位轴，不能再塞入这里的 W 轴参数。具体平面会填在原文的 %s 位置。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot put an X in a canned cycle in the %s plane",
    "symbols": [],
    "title": "当前平面固定循环不允许 X 参数",
    "explanation": "这套循环在选定平面中有自己的进刀轴和定位轴，不能再塞入这里的 X 轴参数。具体平面会填在原文的 %s 位置。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot put a Y in a canned cycle in the %s plane",
    "symbols": [],
    "title": "当前平面固定循环不允许 Y 参数",
    "explanation": "这套循环在选定平面中有自己的进刀轴和定位轴，不能再塞入这里的 Y 轴参数。具体平面会填在原文的 %s 位置。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot put a Z in a canned cycle in the %s plane",
    "symbols": [],
    "title": "当前平面固定循环不允许 Z 参数",
    "explanation": "这套循环在选定平面中有自己的进刀轴和定位轴，不能再塞入这里的 Z 轴参数。具体平面会填在原文的 %s 位置。",
    "animation": "coordinate"
  },
  {
    "template": "Z value unspecified in xy plane canned cycle",
    "symbols": [
      "NCE_Z_VALUE_UNSPECIFIED_IN_XY_PLANE_CANNED_CYCLE"
    ],
    "title": "XY 平面固定循环缺少 Z 目标位置",
    "explanation": "这套钻孔等循环沿 Z 轴进刀，却没拿到该轴的目标位置，软件不知道要加工到哪里。",
    "animation": "coordinate"
  },
  {
    "template": "G17 canned cycle is not possible on a machine without Z axis",
    "symbols": [],
    "title": "G17 固定循环需要 Z 轴",
    "explanation": "当前机床配置没有 Z 轴，但选中的 XY 平面循环需要沿它进刀，无法执行。",
    "animation": "coordinate"
  },
  {
    "template": "R less than z in cycle in xy plane",
    "symbols": [
      "NCE_R_LESS_THAN_Z_IN_CYCLE_IN_XY_PLANE"
    ],
    "title": "XY 平面循环的 R 平面低于 Z 终点",
    "explanation": "R 指定的退刀／接近位置，比 Z 轴的加工终点还小，颠倒了这类循环要求的位置关系。",
    "animation": "r-plane"
  },
  {
    "template": "Bug unknown operation",
    "symbols": [
      "NCE_BUG_UNKNOWN_OPERATION"
    ],
    "title": "表达式运算类型内部异常",
    "explanation": "软件遇到一个不在预期列表里的运算类型，无法继续求值。",
    "animation": "parameters"
  },
  {
    "template": "Invalid spindle ($) number in Spindle Mode command",
    "symbols": [],
    "title": "主轴模式设置的主轴编号无效",
    "explanation": "程序要改变某根主轴的工作模式，但这个主轴编号不存在。",
    "animation": "spindle-setup"
  },
  {
    "template": "Invalid spindle ($) number in Spindle Feed command",
    "symbols": [],
    "title": "主轴进给设置的主轴编号无效",
    "explanation": "程序要按某根主轴计算进给，但选中的主轴不在配置里。",
    "animation": "spindle-setup"
  },
  {
    "template": "Invalid spindle ($) number in Spindle speed command",
    "symbols": [],
    "title": "主轴转速设置的主轴编号无效",
    "explanation": "程序给一根不存在的主轴设置转速，软件找不到对应主轴。",
    "animation": "spindle-setup"
  },
  {
    "template": "Argument to acos out of range",
    "symbols": [
      "NCE_ARGUMENT_TO_ACOS_OUT_OF_RANGE"
    ],
    "title": "ACOS 函数输入超出定义域",
    "explanation": "反余弦只能接受 -1 到 1 之间的数，当前参数超出这个范围。",
    "animation": "parameters"
  },
  {
    "template": "Argument to asin out of range",
    "symbols": [
      "NCE_ARGUMENT_TO_ASIN_OUT_OF_RANGE"
    ],
    "title": "ASIN 函数输入超出定义域",
    "explanation": "反正弦只能接受 -1 到 1 之间的数，当前参数超出了。",
    "animation": "parameters"
  },
  {
    "template": "Zero or negative argument to ln",
    "symbols": [
      "NCE_ZERO_OR_NEGATIVE_ARGUMENT_TO_LN"
    ],
    "title": "LN 函数输入不是正数",
    "explanation": "自然对数在这里要求输入大于零，不能拿零或负数来算。",
    "animation": "parameters"
  },
  {
    "template": "Negative argument to sqrt",
    "symbols": [
      "NCE_NEGATIVE_ARGUMENT_TO_SQRT"
    ],
    "title": "SQRT 函数输入为负数",
    "explanation": "程序要求对负数开平方，这个实数计算器算不出来。",
    "animation": "parameters"
  },
  {
    "template": "Attempt to divide by zero",
    "symbols": [
      "NCE_ATTEMPT_TO_DIVIDE_BY_ZERO"
    ],
    "title": "表达式除数为零",
    "explanation": "公式里出现了除以零，例如 10/0，这个结果没有合法的有限数值。",
    "animation": "parameters"
  },
  {
    "template": "Attempt to raise negative to non integer power",
    "symbols": [
      "NCE_ATTEMPT_TO_RAISE_NEGATIVE_TO_NON_INTEGER_POWER"
    ],
    "title": "负数被计算非整数次幂",
    "explanation": "程序把负数拿去做小数次方，例如负数开平方，这里无法得到支持的实数结果。",
    "animation": "parameters"
  },
  {
    "template": "Cannot use polar coordinates with G53",
    "symbols": [],
    "title": "G53 不支持极坐标",
    "explanation": "机器坐标移动不能用这套“距离加角度”的极坐标写法。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot specify X or Y words with polar coordinate",
    "symbols": [],
    "title": "极坐标与 X／Y 坐标混用",
    "explanation": "一条运动既用距离、角度指定位置，又直接写 X 或 Y，两套写法冲突。",
    "animation": "coordinate"
  },
  {
    "template": "Must specify angle in polar coordinate if at the origin",
    "symbols": [],
    "title": "极坐标原点处缺少角度",
    "explanation": "当前位置就在圆心，光说往外多远还不够，还必须告诉软件朝哪个方向走。",
    "animation": "coordinate"
  },
  {
    "template": "Incremental motion with polar coordinates is indeterminate when at the origin",
    "symbols": [],
    "title": "原点处的极坐标增量运动不确定",
    "explanation": "刀具正好在极坐标中心，没有可延续的方向，软件无法判断增量应该往哪边加。",
    "animation": "coordinate"
  },
  {
    "template": "G91 motion with polar coordinates is indeterminate when at the origin",
    "symbols": [],
    "title": "G91 极坐标运动在原点不确定",
    "explanation": "当前位置半径为零，使用增量极坐标时缺少确定方向，目标位置算不出来。",
    "animation": "coordinate"
  },
  {
    "template": "Requested tool %d not found in the tool table",
    "symbols": [],
    "title": "刀具表中找不到指定刀号",
    "explanation": "程序要求使用这把刀，但当前刀具表里没有它的记录。",
    "animation": "tool-setup"
  },
  {
    "template": "G7x.x  requires a Q word",
    "symbols": [],
    "title": "G7x 车削循环缺少轮廓编号 Q",
    "explanation": "程序要自动车削一段轮廓，却没有指出去哪个子程序读取轮廓。",
    "animation": "program"
  },
  {
    "template": "G%d.%d cannot be used with cutter compensation enabled",
    "symbols": [],
    "title": "当前车削循环不允许刀补",
    "explanation": "程序进入 G7x 轮廓循环时，刀具半径补偿还开着，这种组合不被支持。",
    "animation": "tool-setup"
  },
  {
    "template": "G%d.%d can only be used in XZ plane (G18)",
    "symbols": [],
    "title": "当前车削循环必须使用 G18 平面",
    "explanation": "这组车削动作只在 XZ 平面里实现，程序却选了其他平面。",
    "animation": "coordinate"
  },
  {
    "template": "G7x error: Cannot use U in incremental mode (G91)",
    "symbols": [],
    "title": "G91 模式下车削循环不允许 U",
    "explanation": "当前已使用增量坐标，又用了这套循环专用的 U 写法，软件不允许两者混用。",
    "animation": "program"
  },
  {
    "template": "G7x error: Cannot use U and X in the same block",
    "symbols": [],
    "title": "车削轮廓同时指定 U 和 X",
    "explanation": "同一段轮廓把同一方向的位置写了两遍：一份用 U，一份用 X，软件无法按这组参数处理。",
    "animation": "program"
  },
  {
    "template": "G7X error: Corner finish failed at {position}",
    "symbols": [],
    "title": "车削轮廓拐角修整失败",
    "explanation": "软件无法按当前轮廓和拐角参数算出连接，原文会指出出问题的位置。",
    "animation": "program"
  },
  {
    "template": "G7x error: Cannot use W in incremental mode (G91)",
    "symbols": [],
    "title": "G91 模式下车削循环不允许 W",
    "explanation": "当前已用增量坐标，又给了该循环不允许同时使用的 W 参数。",
    "animation": "program"
  },
  {
    "template": "G7x error: Cannot use W and Z in the same block",
    "symbols": [],
    "title": "车削轮廓同时指定 W 和 Z",
    "explanation": "同一方向的位置同时用 W 和 Z 描述，当前循环不接受这两套写法一起出现。",
    "animation": "program"
  },
  {
    "template": "G7X error: both R and I or K flag used for arc",
    "symbols": [],
    "title": "车削圆弧定义方式冲突",
    "explanation": "这段车削轮廓圆弧既给了 R，又给了 I 或 K；半径法和圆心法不能混用。",
    "animation": "program"
  },
  {
    "template": "G7X error: either I or K must be present for arc",
    "symbols": [],
    "title": "车削圆弧缺少 I／K 圆心参数",
    "explanation": "程序没用半径方式定义圆弧，也没有提供需要的 I 或 K，圆弧位置不够明确。",
    "animation": "program"
  },
  {
    "template": "G7X error: Both A and C parameters on a corner",
    "symbols": [],
    "title": "车削拐角同时指定 A 和 C",
    "explanation": "同一个轮廓角点给了两种互斥的拐角处理参数，软件不能同时采用。",
    "animation": "program"
  },
  {
    "template": "G7X error: I must be greater than zero.",
    "symbols": [],
    "title": "车削循环 I 参数必须大于零",
    "explanation": "这里的进刀量必须是正数；零或负数不能形成有效的切削步进。",
    "animation": "program"
  },
  {
    "template": "G7X error: %s",
    "symbols": [],
    "title": "车削轮廓计算失败",
    "explanation": "这是车削错误的外层提示，冒号后面的实际文字才说明哪里没算出来。",
    "animation": "program"
  },
  {
    "template": "G7X error: How did we get here?",
    "symbols": [],
    "title": "车削路径处理进入非预期分支",
    "explanation": "软件走到了设计上不该出现的路径处理分支，需要结合轮廓和源码排查。",
    "animation": "program"
  },
  {
    "template": "G7X error: x too large in straight dive",
    "symbols": [],
    "title": "车削直线切入位置无法求交",
    "explanation": "给定的 X 位置与待切轮廓找不到所需交点，软件无法算出直线切入终点。",
    "animation": "program"
  },
  {
    "template": "G7X error: Cannot intersect parallel lines",
    "symbols": [],
    "title": "车削轮廓平行线无法求交",
    "explanation": "两条线互相平行，软件却需要它们的交点来连接轮廓，因此算不下去。",
    "animation": "program"
  },
  {
    "template": "G7X error: This can't happen",
    "symbols": [],
    "title": "车削轮廓内部变换状态异常",
    "explanation": "轮廓的翻转或坐标变换状态不在软件预期范围内，不能继续生成路径。",
    "animation": "processing"
  },
  {
    "template": "G7X error: Not monotonic",
    "symbols": [],
    "title": "车削轮廓不满足单调性",
    "explanation": "当前循环要求轮廓沿检查方向持续前进，但轮廓中有一段折回去了。",
    "animation": "not-monotonic"
  },
  {
    "template": "Unclosed comment found",
    "symbols": [
      "NCE_UNCLOSED_COMMENT_FOUND"
    ],
    "title": "注释括号未闭合",
    "explanation": "程序用左圆括号开始了注释，却没有对应的右圆括号结束它。",
    "animation": "program"
  },
  {
    "template": "Cannot use polar coordinate on a machine lacking X or Y axes",
    "symbols": [],
    "title": "机床缺少极坐标所需的 X／Y 轴",
    "explanation": "这台机床没配置完整的 X、Y 轴，无法执行当前极坐标写法。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot use polar coordinate except in G17 plane",
    "symbols": [],
    "title": "极坐标只能用于 G17 平面",
    "explanation": "当前极坐标实现只支持 XY 平面，不能放到其他平面里解释。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot specify both polar coordinate and X word",
    "symbols": [],
    "title": "极坐标与 X 参数冲突",
    "explanation": "这一行已经用距离和角度确定位置，又直接写 X，两套目标描述冲突。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot specify both polar coordinate and Y word",
    "symbols": [],
    "title": "极坐标与 Y 参数冲突",
    "explanation": "这一行已经用极坐标确定位置，又额外写了 Y，目标描述重复了。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot use axis values with g80",
    "symbols": [
      "NCE_CANNOT_USE_AXIS_VALUES_WITH_G80"
    ],
    "title": "G80 取消循环时仍带轴移动参数",
    "explanation": "程序正在取消固定循环，却还写了轴坐标；这条指令本身不负责移动到这些坐标。",
    "animation": "coordinate"
  },
  {
    "template": "Polar coordinates can only be used for motion",
    "symbols": [],
    "title": "非运动指令使用极坐标",
    "explanation": "极坐标是用来说明怎么移动的，当前指令不执行相应运动，却带了极坐标参数。",
    "animation": "coordinate"
  },
  {
    "template": "All axes missing with g52 or g92",
    "symbols": [
      "NCE_ALL_AXES_MISSING_WITH_G52_OR_G92"
    ],
    "title": "G52／G92 缺少轴偏移参数",
    "explanation": "程序要求设置坐标偏移，却没有给任何轴需要设成什么值。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot use two g codes that both use axis values",
    "symbols": [
      "NCE_CANNOT_USE_TWO_G_CODES_THAT_BOTH_USE_AXIS_VALUES"
    ],
    "title": "同一行两条 G 指令争用轴坐标",
    "explanation": "这一行有两个都要使用 X、Y 等坐标的 G 指令，软件无法把同一组坐标同时分给它们。",
    "animation": "coordinate"
  },
  {
    "template": "All axes missing with motion code",
    "symbols": [
      "NCE_ALL_AXES_MISSING_WITH_MOTION_CODE"
    ],
    "title": "运动指令缺少全部轴坐标",
    "explanation": "程序要求移动，却没告诉软件哪个轴要去哪里。",
    "animation": "coordinate"
  },
  {
    "template": "Cannot use axis values without a g code that uses them",
    "symbols": [
      "NCE_CANNOT_USE_AXIS_VALUES_WITHOUT_A_G_CODE_THAT_USES_THEM"
    ],
    "title": "轴坐标没有对应的运动指令",
    "explanation": "这一行写了位置，但当前没有能使用这些坐标的有效指令。",
    "animation": "coordinate"
  },
  {
    "template": "Nested comment found",
    "symbols": [
      "NCE_NESTED_COMMENT_FOUND"
    ],
    "title": "注释发生嵌套",
    "explanation": "一个注释还没结束，又出现另一个左圆括号，软件不接受这种套娃注释。",
    "animation": "program"
  },
  {
    "template": "Null missing after newline",
    "symbols": [
      "NCE_NULL_MISSING_AFTER_NEWLINE"
    ],
    "title": "程序行内部字符串终止异常",
    "explanation": "软件读取一行程序时发现内部文本结束标记不符合预期，不是要求你手工往程序里加特殊字符。",
    "animation": "processing"
  },
  {
    "template": "Named parameter #<%s> not defined",
    "symbols": [],
    "title": "命名参数尚未定义",
    "explanation": "程序读取了一个名字，但前面或配置里没有为这个名字提供可用的值。",
    "animation": "program"
  },
  {
    "template": "can't open INI file '%s'",
    "symbols": [],
    "title": "INI 配置文件无法打开",
    "explanation": "软件需要读取机床配置文件，但找不到它或无法访问。",
    "animation": "file-access"
  },
  {
    "template": "Named INI parameter #<%s> not found in INI file '%s': error=0x%x",
    "symbols": [],
    "title": "INI 命名参数不存在或读取失败",
    "explanation": "程序引用了配置文件中的一个值，但对应项目没有找到或读取时出了问题。",
    "animation": "program"
  },
  {
    "template": "fetch_hal_param: hal_init(%s): %d",
    "symbols": [],
    "title": "HAL 参数访问初始化失败",
    "explanation": "解释器准备向 HAL 读取数据时，连接初始化没成功；原文末尾给出底层返回值。",
    "animation": "program"
  },
  {
    "template": "fetch_hal_param: hal_ready(): %d",
    "symbols": [],
    "title": "HAL 参数访问就绪失败",
    "explanation": "解释器的 HAL 访问没有成功进入可用状态，因此拿不到所需参数。",
    "animation": "program"
  },
  {
    "template": "%s: trailing garbage after closing bracket",
    "symbols": [],
    "title": "参数右括号后有多余内容",
    "explanation": "一个参数名字已经结束，后面却紧跟着不该出现的字符，软件无法解析。",
    "animation": "program"
  },
  {
    "template": "Named hal parameter #<%s> not found",
    "symbols": [],
    "title": "HAL 命名参数不存在",
    "explanation": "程序引用的 HAL 参数或信号名找不到，可能名称或当前配置不匹配。",
    "animation": "program"
  },
  {
    "template": "named param - pycall(%s):\n%s",
    "symbols": [],
    "title": "Python 命名参数求值失败",
    "explanation": "这个参数需要调用 Python 算出来，但调用失败；后面的异常文字才是具体原因。",
    "animation": "processing"
  },
  {
    "template": "Python namedparams.%s returns no value",
    "symbols": [],
    "title": "Python 命名参数未返回数值",
    "explanation": "负责计算这个参数的函数执行完了，却什么值也没返回，程序没法继续使用它。",
    "animation": "parameters"
  },
  {
    "template": "%s",
    "symbols": [],
    "title": "下层错误文本透传",
    "explanation": "这里的 %s 只是占位符。真正报错时会被另一层传来的原因替换，单看这个模板无法判断故障。",
    "animation": "program"
  },
  {
    "template": "Python call %s.%s returned '%s' - expected double, int or string, got %s",
    "symbols": [],
    "title": "Python 参数返回类型不符合要求",
    "explanation": "软件需要数字或可处理的字符串，但 Python 函数返回了别的类型。",
    "animation": "processing"
  },
  {
    "template": "Internal error: Could not assign #<%s>",
    "symbols": [],
    "title": "命名参数内部赋值失败",
    "explanation": "软件想把值存入这个参数，却没有成功，需要查看该参数的定义和赋值流程。",
    "animation": "processing"
  },
  {
    "template": "BUG: variable '%s' marked global, but assigned at level %d",
    "symbols": [],
    "title": "全局变量的赋值层级异常",
    "explanation": "变量被标记为全局可见，但软件却在不符合规则的调用层给它赋值。",
    "animation": "processing"
  },
  {
    "template": "Cannot assign to read-only parameter #<%s>",
    "symbols": [],
    "title": "试图修改只读命名参数",
    "explanation": "这个参数只能查看，程序却想给它写一个新值。",
    "animation": "program"
  },
  {
    "template": "adding r/o '%s'",
    "symbols": [],
    "title": "只读参数创建失败",
    "explanation": "软件想添加一个只读参数，但参数管理流程拒绝了这次添加。",
    "animation": "program"
  },
  {
    "template": "storing r/o '%s' %f",
    "symbols": [],
    "title": "只读参数写入失败",
    "explanation": "软件试图写入一个不允许修改的参数，所以这次赋值被拒绝。",
    "animation": "program"
  },
  {
    "template": "BUG: lookup_named_param(%s): unhandled index=%fn",
    "symbols": [],
    "title": "命名参数索引内部异常",
    "explanation": "软件查找参数时遇到了无法处理的内部编号，不能从这条提示直接推断工件设置有错。",
    "animation": "processing"
  },
  {
    "template": "%d: undefined O-word label: '%s'",
    "symbols": [],
    "title": "O 标签未定义",
    "explanation": "程序要跳转或关联某个 O 标签，但软件没有找到它的定义。",
    "animation": "program"
  },
  {
    "template": "%d: no matching 'if' label: '%s' (found '%s' in line %d)",
    "symbols": [],
    "title": "IF 分支标签不匹配",
    "explanation": "这段条件分支的标签，与前面对应的 IF 标签对不上。",
    "animation": "program"
  },
  {
    "template": "File:%s line:%d sub: o|%s| found in illegal location",
    "symbols": [],
    "title": "子程序定义位置非法",
    "explanation": "子程序出现在当前语法或调用状态不允许的位置，程序结构需要核对。",
    "animation": "program"
  },
  {
    "template": "File:%s line:%d redefining sub: o|%s| already defined in file:%s",
    "symbols": [],
    "title": "子程序被重复定义",
    "explanation": "同名子程序已经在其他位置定义过，当前又定义了一遍，软件无法确定采用哪一份。",
    "animation": "program"
  },
  {
    "template": "%d: no matching label: '%s' (found '%s' in line %d): '%s'",
    "symbols": [],
    "title": "流程控制标签配对失败",
    "explanation": "循环或分支的开始、结束标签对不上，原文会指出相关行号和标签。",
    "animation": "program"
  },
  {
    "template": "%d: no matching while/do label: '%s' (found '%s' in line %d)",
    "symbols": [],
    "title": "WHILE／DO 循环标签不匹配",
    "explanation": "循环尾部找不到与它同名的循环开头，循环结构不完整或名字写错。",
    "animation": "program"
  },
  {
    "template": "%d: no matching label: '%s' (found '%s' in line %d)",
    "symbols": [],
    "title": "O 流程控制缺少匹配标签",
    "explanation": "这一条流程控制指令没有找到对应的另一半，无法确定跳到哪里。",
    "animation": "program"
  },
  {
    "template": "Unknown oword number",
    "symbols": [
      "NCE_UNKNOWN_OWORD_NUMBER"
    ],
    "title": "未知 O 指令编号",
    "explanation": "软件遇到了一个没有识别或没有记录的 O 控制编号。",
    "animation": "program"
  },
  {
    "template": "BUG:  execute_call():  arrived with call_type=CT_NONE",
    "symbols": [],
    "title": "子程序调用类型未设置",
    "explanation": "软件进入调用子程序的流程时，内部却没有记录这是哪一类调用。",
    "animation": "program"
  },
  {
    "template": "Unable to open file <%s>",
    "symbols": [
      "NCE_UNABLE_TO_OPEN_FILE"
    ],
    "title": "程序文件无法打开",
    "explanation": "要读取的程序文件找不到、不可访问，或无法作为正常文件打开。",
    "animation": "file-access"
  },
  {
    "template": "pycall(%s.%s) failed",
    "symbols": [],
    "title": "Python 子程序调用失败",
    "explanation": "指定的 Python 函数没有成功完成调用，需要看对应函数和附带异常。",
    "animation": "processing"
  },
  {
    "template": "%s (remapped) uses Python functions, but the Python plugin is not available",
    "symbols": [],
    "title": "重映射指令缺少 Python 支持",
    "explanation": "这条自定义指令依赖 Python，但当前解释器没有可用的 Python 插件。",
    "animation": "processing"
  },
  {
    "template": "File not open",
    "symbols": [
      "NCE_FILE_NOT_OPEN"
    ],
    "title": "程序文件尚未打开",
    "explanation": "软件准备从文件读程序，但当前没有打开任何程序文件。",
    "animation": "file-access"
  },
  {
    "template": "cannot reopen file %s - removed or renamed? (%s)",
    "symbols": [
      "NCE_CANNOT_REOPEN_FILE"
    ],
    "title": "程序文件无法重新打开",
    "explanation": "软件需要再次读取同一文件，但文件可能被移动、改名、删除或变得不可访问了。",
    "animation": "file-access"
  },
  {
    "template": "Not in subroutine definition",
    "symbols": [
      "NCE_NOT_IN_SUBROUTINE_DEFN"
    ],
    "title": "当前不在子程序定义中",
    "explanation": "程序出现了只能放在子程序里面的操作，但当前位置不是子程序内部。",
    "animation": "program"
  },
  {
    "template": "handler_returned: %s returned double: %f - invalid",
    "symbols": [],
    "title": "子程序返回了非法的小数状态",
    "explanation": "这里需要整数形式的执行结果，但子程序却返回了一个小数。",
    "animation": "parameters"
  },
  {
    "template": "Too many subroutine levels",
    "symbols": [
      "NCE_TOO_MANY_SUBROUTINE_LEVELS"
    ],
    "title": "子程序嵌套层数超限",
    "explanation": "子程序一层调用一层，已经超过软件允许的深度；也可能是互相调用形成了循环。",
    "animation": "program"
  },
  {
    "template": "Bug: call stack underrun",
    "symbols": [
      "NCE_CALL_STACK_UNDERRUN"
    ],
    "title": "子程序返回栈下溢",
    "explanation": "软件想返回上一层，却发现已经没有上一层记录了，调用和返回不成对。",
    "animation": "program"
  },
  {
    "template": "Fanuc 'O....' subroutine must be called with 'M98'",
    "symbols": [],
    "title": "Fanuc 风格子程序调用方式错误",
    "explanation": "这个 O 子程序采用 Fanuc 风格，必须用对应的 M98 调用方式。",
    "animation": "program"
  },
  {
    "template": "'O.... sub' subroutine must be called with 'O.... call'",
    "symbols": [],
    "title": "LinuxCNC 风格子程序调用方式错误",
    "explanation": "这个子程序用 O…sub 定义，应该用 O…call 调用，不能混用另一种语法。",
    "animation": "program"
  },
  {
    "template": "Nested subroutine definition",
    "symbols": [
      "NCE_NESTED_SUBROUTINE_DEFN"
    ],
    "title": "子程序定义发生嵌套",
    "explanation": "一个子程序还没定义完，里面又开始定义另一个子程序，软件不允许这样写。",
    "animation": "program"
  },
  {
    "template": "Bug:  Reached convert_control_functions() from M99 in main program",
    "symbols": [],
    "title": "主程序 M99 被送入错误流程",
    "explanation": "主程序中的 M99 进入了不符合预期的控制处理分支，属于内部流程异常。",
    "animation": "program"
  },
  {
    "template": "%d: not in a subroutine definition: '%s'",
    "symbols": [],
    "title": "子程序结束语句缺少对应定义",
    "explanation": "出现了子程序结束或返回语句，但前面没有匹配的子程序开始位置。",
    "animation": "program"
  },
  {
    "template": "Fanuc 'O....' subroutine definition must end with 'M99'",
    "symbols": [],
    "title": "Fanuc 子程序缺少 M99 结束",
    "explanation": "这种风格的子程序必须用 M99 返回，当前没有按它的规则收尾。",
    "animation": "program"
  },
  {
    "template": "'O.... endsub' or 'O.... return' must follow 'O.... sub' subroutine definition",
    "symbols": [],
    "title": "O 子程序结束／返回缺少开头",
    "explanation": "O…endsub 或 O…return 前面没有对应的 O…sub，结构不完整。",
    "animation": "program"
  },
  {
    "template": "%d: duplicate O-word label: '%s' - defined in line %d",
    "symbols": [],
    "title": "O 标签重复定义",
    "explanation": "同一个 O 标签被定义了不止一次，软件无法唯一确定跳转目标。",
    "animation": "program"
  },
  {
    "template": "%d: duplicate O-word label - already defined in line %d: '%s'",
    "symbols": [],
    "title": "O 标签与已有标签重复",
    "explanation": "当前 O 标签早已使用过，原文会指出第一次定义的位置。",
    "animation": "program"
  },
  {
    "template": "pycall(%s): Python plugin not initialized",
    "symbols": [],
    "title": "Python 调用插件未初始化",
    "explanation": "程序要执行 Python 函数，但解释器里的 Python 环境还没有准备好。",
    "animation": "processing"
  },
  {
    "template": "run_string(%s):\n%s",
    "symbols": [],
    "title": "Python 代码执行失败",
    "explanation": "解释器运行一段 Python 代码时出错，后面的异常说明才是具体问题。",
    "animation": "processing"
  },
  {
    "template": "exception during generator call: %s",
    "symbols": [],
    "title": "Python 生成器执行异常",
    "explanation": "一个分步骤返回动作的 Python 函数在继续执行时出错了。",
    "animation": "processing"
  },
  {
    "template": "pycall(%s):\n%s",
    "symbols": [],
    "title": "Python 函数调用异常",
    "explanation": "解释器调用 Python 函数失败，原文后半段会显示异常内容。",
    "animation": "parameters"
  },
  {
    "template": "Python call %s.%s returned '%s' - expected generator, int, or float value, got %s",
    "symbols": [],
    "title": "Python 指令返回类型不合法",
    "explanation": "这次调用只接受生成器、整数或小数，函数却返回了其他类型。",
    "animation": "processing"
  },
  {
    "template": "Python internal function '%s' expected tuple or int return value, got '%s' (%s)",
    "symbols": [],
    "title": "Python 内部函数返回类型错误",
    "explanation": "软件需要元组或整数结果，函数却返回了别的东西，双方接口约定不一致。",
    "animation": "parameters"
  },
  {
    "template": "pycall: %s.%s:\n%s",
    "symbols": [],
    "title": "Python 模块／函数调用失败",
    "explanation": "指定模块里的函数执行失败，需要查看原文中的模块名、函数名和异常内容。",
    "animation": "parameters"
  },
  {
    "template": "py_execute(%s): Python plugin not initialized",
    "symbols": [],
    "title": "Python 执行环境未初始化",
    "explanation": "程序要执行 Python 代码，但当前插件还没有进入可用状态。",
    "animation": "processing"
  },
  {
    "template": "py_execute(%s)%s:\n%s",
    "symbols": [],
    "title": "Python 代码片段执行异常",
    "explanation": "这段嵌入的 Python 代码没能成功运行，后面的异常说明会指出原因。",
    "animation": "processing"
  },
  {
    "template": "py_reload:\n%s",
    "symbols": [],
    "title": "Python 插件重载失败",
    "explanation": "软件重新加载 Python 扩展时出了错，旧功能不一定已经成功换成新版本。",
    "animation": "processing"
  },
  {
    "template": "BUG: cutter compensation has generated an invalid arc with mismatched radii r1 %f r2 %f\n",
    "symbols": [],
    "title": "刀补生成的圆弧半径不一致",
    "explanation": "这是软件做完刀补后生成的圆弧接不上圆，起终点到圆心的距离不一样。",
    "animation": "arc-radius"
  },
  {
    "template": "BUG: Unsupported plane in cutter compensation",
    "symbols": [],
    "title": "刀补运动队列的平面不受支持",
    "explanation": "软件准备安排补偿后的动作，但当前平面不属于它支持的范围。",
    "animation": "tool-setup"
  },
  {
    "template": "Straight traverse in concave corner cannot be reached by the tool without gouging",
    "symbols": [],
    "title": "凹角快移刀补发生干涉",
    "explanation": "补偿后的快速移动会穿进凹角里的保留材料，刀具没有足够空间按这条路线通过。",
    "animation": "tool-setup"
  },
  {
    "template": "BUG: Unsupported plane [%d] in cutter compensation",
    "symbols": [],
    "title": "刀补运动队列平面编号无效",
    "explanation": "运动队列收到一个无法用于刀补的平面编号，内部状态不一致。",
    "animation": "tool-setup"
  },
  {
    "template": "Straight feed in concave corner cannot be reached by the tool without gouging",
    "symbols": [],
    "title": "凹角直线进给刀补发生干涉",
    "explanation": "刀具按补偿后的直线切进凹角时会多切材料，当前路径和刀具尺寸配不上。",
    "animation": "tool-setup"
  },
  {
    "template": "Multiple l words on one line",
    "symbols": [
      "NCE_MULTIPLE_L_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 L 参数",
    "explanation": "这一行出现了不止一个 L，软件无法把它们当成一个明确的次数或循环参数。",
    "animation": "program"
  },
  {
    "template": "Negative l word used",
    "symbols": [
      "NCE_NEGATIVE_L_WORD_USED"
    ],
    "title": "L 参数为负数",
    "explanation": "L 通常表示重复次数等数量，这里不接受负数。",
    "animation": "parameters"
  },
  {
    "template": "Negative m code used",
    "symbols": [
      "NCE_NEGATIVE_M_CODE_USED"
    ],
    "title": "M 指令编号为负数",
    "explanation": "M 后面的编号不能是负数，例如 M-3 不是有效指令。",
    "animation": "parameters"
  },
  {
    "template": "BUG: M remapping: modal group < 0",
    "symbols": [],
    "title": "M 指令重映射组编号小于零",
    "explanation": "扩展 M 指令被分到了不存在的指令组。这是扩展定义或软件内部状态异常。",
    "animation": "processing"
  },
  {
    "template": "BUG: M remapping: modal group > 10",
    "symbols": [],
    "title": "M 指令重映射组编号超出上限",
    "explanation": "扩展 M 指令的分组编号超出了解释器支持的范围，需要检查扩展定义。",
    "animation": "processing"
  },
  {
    "template": "Two m codes used from same modal group",
    "symbols": [
      "NCE_TWO_M_CODES_USED_FROM_SAME_MODAL_GROUP"
    ],
    "title": "同一行出现互斥的 M 指令",
    "explanation": "这一行写了同一组里不能同时生效的 M 指令。例如同时要求主轴正转和反转，软件不能替你决定选哪个。",
    "animation": "program"
  },
  {
    "template": "M-code greater than 199: M%d",
    "symbols": [
      "NCE_M_CODE_GREATER_THAN_199"
    ],
    "title": "M 指令编号超出支持范围",
    "explanation": "这个 M 编号大于此处允许的 199，解释器不接受它。",
    "animation": "program"
  },
  {
    "template": "Bad character '\\%03o' used",
    "symbols": [],
    "title": "程序含有不支持的字符编码",
    "explanation": "程序里混入了不能识别的字符。原文中的八进制数字表示那个字符的编码，不是机床坐标。",
    "animation": "program"
  },
  {
    "template": "Bad character '%c' used",
    "symbols": [],
    "title": "程序含有不支持的字符",
    "explanation": "报错指出的字符不能出现在这里，可能是多打了符号，或混进了中文标点。",
    "animation": "program"
  },
  {
    "template": "Unknown operation name starting with a",
    "symbols": [
      "NCE_UNKNOWN_OPERATION_NAME_STARTING_WITH_A"
    ],
    "title": "以 A 开头的运算符无法识别",
    "explanation": "计算式里有一个以 A 开头的运算词，但它不是软件支持的完整拼写，软件不知道要进行什么运算。",
    "animation": "parameters"
  },
  {
    "template": "Unknown operation name starting with m",
    "symbols": [
      "NCE_UNKNOWN_OPERATION_NAME_STARTING_WITH_M"
    ],
    "title": "以 M 开头的运算符无法识别",
    "explanation": "计算式里有一个以 M 开头的运算词，但它不是软件支持的完整拼写，软件不知道要进行什么运算。",
    "animation": "parameters"
  },
  {
    "template": "Unknown operation name starting with o",
    "symbols": [
      "NCE_UNKNOWN_OPERATION_NAME_STARTING_WITH_O"
    ],
    "title": "以 O 开头的运算符无法识别",
    "explanation": "计算式里有一个以 O 开头的运算词，但它不是软件支持的完整拼写，软件不知道要进行什么运算。",
    "animation": "parameters"
  },
  {
    "template": "Unknown operation name starting with x",
    "symbols": [
      "NCE_UNKNOWN_OPERATION_NAME_STARTING_WITH_X"
    ],
    "title": "以 X 开头的运算符无法识别",
    "explanation": "计算式里有一个以 X 开头的运算词，但它不是软件支持的完整拼写，软件不知道要进行什么运算。",
    "animation": "parameters"
  },
  {
    "template": "Unknown operation name starting with e",
    "symbols": [
      "NCE_UNKNOWN_OPERATION_NAME_STARTING_WITH_E"
    ],
    "title": "以 E 开头的运算符无法识别",
    "explanation": "计算式里有一个以 E 开头的运算词，但它不是软件支持的完整拼写，软件不知道要进行什么运算。",
    "animation": "parameters"
  },
  {
    "template": "Unknown operation name starting with n",
    "symbols": [
      "NCE_UNKNOWN_OPERATION_NAME_STARTING_WITH_N"
    ],
    "title": "以 N 开头的运算符无法识别",
    "explanation": "计算式里有一个以 N 开头的运算词，但它不是软件支持的完整拼写，软件不知道要进行什么运算。",
    "animation": "parameters"
  },
  {
    "template": "Unknown operation name starting with g",
    "symbols": [
      "NCE_UNKNOWN_OPERATION_NAME_STARTING_WITH_G"
    ],
    "title": "以 G 开头的运算符无法识别",
    "explanation": "计算式里有一个以 G 开头的运算词，但它不是软件支持的完整拼写，软件不知道要进行什么运算。",
    "animation": "parameters"
  },
  {
    "template": "Slash missing after first atan argument",
    "symbols": [
      "NCE_SLASH_MISSING_AFTER_FIRST_ATAN_ARGUMENT"
    ],
    "title": "ATAN 双参数表达式缺少分隔符",
    "explanation": "这里的 ATAN 需要把两个参数用 / 分开；第一个参数之后没找到这个斜杠。",
    "animation": "parameters"
  },
  {
    "template": "Unknown operation name starting with l",
    "symbols": [
      "NCE_UNKNOWN_OPERATION_NAME_STARTING_WITH_L"
    ],
    "title": "以 L 开头的运算符无法识别",
    "explanation": "计算式里有一个以 L 开头的运算词，但它不是软件支持的完整拼写，软件不知道要进行什么运算。",
    "animation": "parameters"
  },
  {
    "template": "Unclosed expression",
    "symbols": [
      "NCE_UNCLOSED_EXPRESSION"
    ],
    "title": "表达式缺少结束方括号",
    "explanation": "用 [ 开始了一段计算，却没有用 ] 把它关上，软件不知道计算到哪里结束。",
    "animation": "parameters"
  },
  {
    "template": "Unknown operation",
    "symbols": [
      "NCE_UNKNOWN_OPERATION"
    ],
    "title": "表达式运算符无法识别",
    "explanation": "两个数或表达式之间的运算写法不在支持列表里，软件不知道你要做加减还是别的计算。",
    "animation": "parameters"
  },
  {
    "template": "Left bracket missing after slash with atan",
    "symbols": [
      "NCE_LEFT_BRACKET_MISSING_AFTER_SLASH_WITH_ATAN"
    ],
    "title": "ATAN 第二参数缺少左方括号",
    "explanation": "ATAN 的 / 后面应该用 [ 开始第二个参数，这里没有找到。",
    "animation": "program"
  },
  {
    "template": "Unknown word starting with a",
    "symbols": [
      "NCE_UNKNOWN_WORD_STARTING_WITH_A"
    ],
    "title": "以 A 开头的函数名无法识别",
    "explanation": "这里应当是数学函数名称，但以 A 开头的这段文字不在支持的函数里，可能是拼写不完整或写错。",
    "animation": "parameters"
  },
  {
    "template": "Unknown word starting with c",
    "symbols": [
      "NCE_UNKNOWN_WORD_STARTING_WITH_C"
    ],
    "title": "以 C 开头的函数名无法识别",
    "explanation": "这里应当是数学函数名称，但以 C 开头的这段文字不在支持的函数里，可能是拼写不完整或写错。",
    "animation": "parameters"
  },
  {
    "template": "Unknown word starting with e",
    "symbols": [
      "NCE_UNKNOWN_WORD_STARTING_WITH_E"
    ],
    "title": "以 E 开头的函数名无法识别",
    "explanation": "这里应当是数学函数名称，但以 E 开头的这段文字不在支持的函数里，可能是拼写不完整或写错。",
    "animation": "parameters"
  },
  {
    "template": "Unknown word starting with f",
    "symbols": [
      "NCE_UNKNOWN_WORD_STARTING_WITH_F"
    ],
    "title": "以 F 开头的函数名无法识别",
    "explanation": "这里应当是数学函数名称，但以 F 开头的这段文字不在支持的函数里，可能是拼写不完整或写错。",
    "animation": "parameters"
  },
  {
    "template": "Unknown word starting with l",
    "symbols": [
      "NCE_UNKNOWN_WORD_STARTING_WITH_L"
    ],
    "title": "以 L 开头的函数名无法识别",
    "explanation": "这里应当是数学函数名称，但以 L 开头的这段文字不在支持的函数里，可能是拼写不完整或写错。",
    "animation": "parameters"
  },
  {
    "template": "Unknown word starting with r",
    "symbols": [
      "NCE_UNKNOWN_WORD_STARTING_WITH_R"
    ],
    "title": "以 R 开头的函数名无法识别",
    "explanation": "这里应当是数学函数名称，但以 R 开头的这段文字不在支持的函数里，可能是拼写不完整或写错。",
    "animation": "parameters"
  },
  {
    "template": "Unknown word starting with s",
    "symbols": [
      "NCE_UNKNOWN_WORD_STARTING_WITH_S"
    ],
    "title": "以 S 开头的函数名无法识别",
    "explanation": "这里应当是数学函数名称，但以 S 开头的这段文字不在支持的函数里，可能是拼写不完整或写错。",
    "animation": "parameters"
  },
  {
    "template": "Unknown word starting with t",
    "symbols": [
      "NCE_UNKNOWN_WORD_STARTING_WITH_T"
    ],
    "title": "以 T 开头的函数名无法识别",
    "explanation": "这里应当是数学函数名称，但以 T 开头的这段文字不在支持的函数里，可能是拼写不完整或写错。",
    "animation": "parameters"
  },
  {
    "template": "Unknown word where unary operation could be",
    "symbols": [
      "NCE_UNKNOWN_WORD_WHERE_UNARY_OPERATION_COULD_BE"
    ],
    "title": "单参数函数名称无法识别",
    "explanation": "这里应是 SIN、COS、SQRT 等受支持的函数名，实际文字无法识别。",
    "animation": "parameters"
  },
  {
    "template": "DISABLE_FANUC_STYLE_SUB set in INI file, but found m98",
    "symbols": [],
    "title": "FANUC 风格子程序已禁用，不能使用 M98",
    "explanation": "配置明确关闭了这种子程序调用方式，但程序仍在用 M98 调用它。",
    "animation": "program"
  },
  {
    "template": "Found 'm98' code with no P-word",
    "symbols": [],
    "title": "M98 缺少子程序编号 P",
    "explanation": "程序说要调用一个子程序，却没通过 P 指明要调用哪一个。",
    "animation": "program"
  },
  {
    "template": "Non integer value for integer",
    "symbols": [
      "NCE_NON_INTEGER_VALUE_FOR_INTEGER"
    ],
    "title": "要求整数的参数出现小数",
    "explanation": "这个位置只能写整数，但读到的数带有不允许的小数部分。",
    "animation": "parameters"
  },
  {
    "template": "DISABLE_FANUC_STYLE_SUB set in INI file, but found m99",
    "symbols": [],
    "title": "FANUC 风格子程序已禁用，不能使用 M99",
    "explanation": "配置不允许使用这套子程序方式，程序却用了对应的 M99 返回指令。",
    "animation": "program"
  },
  {
    "template": "Found 'M99' instead of 'O endsub' after 'O sub'",
    "symbols": [],
    "title": "子程序结束语法混用",
    "explanation": "子程序用 O…SUB 开头，却用另一套语法的 M99 结束；开头和结尾没有配成一套。",
    "animation": "program"
  },
  {
    "template": "%d: Bug:  Non-m98/m99 M-code passed to read_o(): '%s'",
    "symbols": [],
    "title": "子程序读取器收到错误类型的 M 指令",
    "explanation": "软件把一个不属于 M98/M99 的指令交给了专门处理子程序的代码，属于内部调用异常。",
    "animation": "program"
  },
  {
    "template": "DISABLE_FANUC_STYLE_SUB disabled in INI file, but found bare O-word",
    "symbols": [],
    "title": "FANUC 风格子程序已禁用，不能使用独立 O 编号",
    "explanation": "配置关闭了 FANUC 风格子程序，但程序仍用了单独一行 O 编号作为子程序标记。原文的 disabled 容易误导；这里按源码实际判断解释。",
    "animation": "program"
  },
  {
    "template": "Too many subroutine parameters",
    "symbols": [
      "NCE_TOO_MANY_SUBROUTINE_PARAMETERS"
    ],
    "title": "子程序调用参数过多",
    "explanation": "传给子程序的参数数量超过了解释器能接收的上限。",
    "animation": "program"
  },
  {
    "template": "Left bracket missing after 'while'",
    "symbols": [],
    "title": "WHILE 条件缺少左方括号",
    "explanation": "WHILE 后面的循环条件没有用 [ 开始，软件无法按条件表达式读取。",
    "animation": "program"
  },
  {
    "template": "Left bracket missing after 'repeat'",
    "symbols": [],
    "title": "REPEAT 次数缺少左方括号",
    "explanation": "REPEAT 后面的重复次数表达式没有用 [ 开始。",
    "animation": "program"
  },
  {
    "template": "Left bracket missing after 'if'",
    "symbols": [],
    "title": "IF 条件缺少左方括号",
    "explanation": "IF 后面的判断条件没有用 [ 开始。",
    "animation": "program"
  },
  {
    "template": "Left bracket missing after 'elseif'",
    "symbols": [],
    "title": "ELSEIF 条件缺少左方括号",
    "explanation": "ELSEIF 后面的判断条件没有用 [ 开始。",
    "animation": "program"
  },
  {
    "template": "Unknown control command in o word",
    "symbols": [
      "NCE_UNKNOWN_COMMAND_IN_O_LINE"
    ],
    "title": "O 语句中的流程命令无法识别",
    "explanation": "O 标签后面的文字不是可识别的 IF、WHILE、CALL 等流程命令。",
    "animation": "program"
  },
  {
    "template": "Multiple b words on one line",
    "symbols": [
      "NCE_MULTIPLE_B_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 B 参数",
    "explanation": "这一行把B 旋转轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple p words on one line",
    "symbols": [
      "NCE_MULTIPLE_P_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 P 参数",
    "explanation": "这一行把P 参数写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Parameter number out of range",
    "symbols": [
      "NCE_PARAMETER_NUMBER_OUT_OF_RANGE"
    ],
    "title": "编号参数超出允许范围",
    "explanation": "访问的 # 参数编号不在软件允许的范围内，相当于查了一个不存在的储物格。",
    "animation": "program"
  },
  {
    "template": "Cannot read current position with cutter radius compensation on",
    "symbols": [],
    "title": "启用刀具半径补偿时不能读取此类当前位置参数",
    "explanation": "刀补开着时，程序路径和刀具中心位置并不相同；这里不允许用这种参数读取当前位置，以免拿错坐标。",
    "animation": "tool-setup"
  },
  {
    "template": "Expected # reading parameter",
    "symbols": [],
    "title": "参数引用缺少井号",
    "explanation": "软件正在读取参数，但当前位置没有找到用于开头的 #。",
    "animation": "program"
  },
  {
    "template": "Expected ] reading bracketed parameter",
    "symbols": [],
    "title": "参数索引表达式缺少右方括号",
    "explanation": "用方括号计算参数编号时，没有用 ] 结束这个编号表达式。",
    "animation": "parameters"
  },
  {
    "template": "Equal sign missing in parameter setting",
    "symbols": [
      "NCE_EQUAL_SIGN_MISSING_IN_PARAMETER_SETTING"
    ],
    "title": "参数赋值缺少等号",
    "explanation": "程序写出了要设置的参数，却没有用 = 连接后面的值。",
    "animation": "program"
  },
  {
    "template": "Out of memory",
    "symbols": [
      "NCE_OUT_OF_MEMORY"
    ],
    "title": "解释器内存分配失败",
    "explanation": "软件没有申请到需要的内存，无法继续保存或处理这些数据。",
    "animation": "file-access"
  },
  {
    "template": "Parameter is readonly",
    "symbols": [
      "NCE_PARAMETER_NUMBER_READONLY"
    ],
    "title": "禁止写入只读参数",
    "explanation": "这个参数只能查看，程序却试图给它重新赋值。",
    "animation": "program"
  },
  {
    "template": "Multiple q words on one line",
    "symbols": [
      "NCE_MULTIPLE_Q_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 Q 参数",
    "explanation": "这一行把Q 参数写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple r words on one line",
    "symbols": [
      "NCE_MULTIPLE_R_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 R 参数",
    "explanation": "这一行把R 参数写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple c words on one line",
    "symbols": [
      "NCE_MULTIPLE_C_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 C 参数",
    "explanation": "这一行把C 旋转轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "bad number format (conversion failed) parsing '%s'",
    "symbols": [],
    "title": "数字内容无法转换",
    "explanation": "本来应该是一个数字的位置，出现了无法转换成数字的文字或格式。",
    "animation": "parameters"
  },
  {
    "template": "bad number format (trailing characters) parsing '%s'",
    "symbols": [],
    "title": "数字后面带有多余字符",
    "explanation": "开头能读成数字，但后面还粘着不应该出现的字符，整个值因此不合法。",
    "animation": "parameters"
  },
  {
    "template": "No characters found in reading real value",
    "symbols": [
      "NCE_NO_CHARACTERS_FOUND_IN_READING_REAL_VALUE"
    ],
    "title": "数字位置没有可读取内容",
    "explanation": "软件准备读一个数，却发现那里是空的，连有效数字的开头都没有。",
    "animation": "parameters"
  },
  {
    "template": "Calculation resulted in 'not a number'",
    "symbols": [],
    "title": "表达式计算结果不是有效数值",
    "explanation": "这次计算得到 NaN，表示结果不是一个可用的数，不能当作坐标、速度或参数继续使用。",
    "animation": "parameters"
  },
  {
    "template": "Calculation resulted in 'infinity'",
    "symbols": [],
    "title": "表达式计算结果为无穷大",
    "explanation": "计算结果超出了有限数值范围，不能用这个结果控制机床。",
    "animation": "parameters"
  },
  {
    "template": "Multiple s words on one line",
    "symbols": [
      "NCE_MULTIPLE_S_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 S 参数",
    "explanation": "这一行把主轴速度写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Negative spindle speed used",
    "symbols": [
      "NCE_NEGATIVE_SPINDLE_SPEED_USED"
    ],
    "title": "主轴转速为负数",
    "explanation": "S 指定的转速不能是负值；旋转方向由相应指令表示，不靠负转速表示。",
    "animation": "spindle-setup"
  },
  {
    "template": "Multiple t words on one line",
    "symbols": [
      "NCE_MULTIPLE_T_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 T 参数",
    "explanation": "这一行把刀具编号写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Negative tool id (tool not found)",
    "symbols": [
      "NCE_NEGATIVE_TOOL_ID_USED"
    ],
    "title": "刀具编号为负数或未找到刀具",
    "explanation": "这里得到的刀具编号无效，软件不能据此选出刀具；需结合原文和刀具表判断具体编号。",
    "animation": "tool-setup"
  },
  {
    "template": "EOF in file:%s seeking o-word: o<%s> from line: %d",
    "symbols": [],
    "title": "寻找 O 标签时提前到达文件结尾",
    "explanation": "软件一直找到文件末尾，也没找到所需的 O 标签。原文会给出文件、标签和开始寻找的行号。",
    "animation": "file-access"
  },
  {
    "template": "File ended with no percent sign (%%)",
    "symbols": [
      "NCE_FILE_ENDED_WITH_NO_PERCENT_SIGN"
    ],
    "title": "程序缺少结尾百分号",
    "explanation": "这个文件需要配对的 % 结束标记，但读到文件末尾仍没找到。",
    "animation": "program"
  },
  {
    "template": "File ended with no percent sign (%%) or program end (M2)",
    "symbols": [
      "NCE_FILE_ENDED_WITH_NO_PERCENT_SIGN_OR_PROGRAM_END"
    ],
    "title": "程序没有有效结束标记",
    "explanation": "文件已经读完，却没有找到所需的 % 或程序结束指令 M2。",
    "animation": "program"
  },
  {
    "template": "Command too long",
    "symbols": [
      "NCE_COMMAND_TOO_LONG"
    ],
    "title": "单条程序命令过长",
    "explanation": "这一行的内容超过了解释器可接收的长度，不是整个加工程序太大。",
    "animation": "program"
  },
  {
    "template": "Left bracket missing after unary operation name",
    "symbols": [
      "NCE_LEFT_BRACKET_MISSING_AFTER_UNARY_OPERATION_NAME"
    ],
    "title": "函数参数缺少左方括号",
    "explanation": "函数名后面应当用 [ 开始参数，例如 SIN[...]；这里没有找到这个括号。",
    "animation": "parameters"
  },
  {
    "template": "Multiple U words on one line",
    "symbols": [],
    "title": "同一程序行重复指定 U 参数",
    "explanation": "这一行把U 轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple V words on one line",
    "symbols": [],
    "title": "同一程序行重复指定 V 参数",
    "explanation": "这一行把V 轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple W words on one line",
    "symbols": [],
    "title": "同一程序行重复指定 W 参数",
    "explanation": "这一行把W 轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple x words on one line",
    "symbols": [
      "NCE_MULTIPLE_X_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 X 参数",
    "explanation": "这一行把X 轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple y words on one line",
    "symbols": [
      "NCE_MULTIPLE_Y_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 Y 参数",
    "explanation": "这一行把Y 轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple z words on one line",
    "symbols": [
      "NCE_MULTIPLE_Z_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 Z 参数",
    "explanation": "这一行把Z 轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple d words on one line",
    "symbols": [
      "NCE_MULTIPLE_D_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 D 参数",
    "explanation": "这一行把D 参数写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple spindle choice ($) words on one line",
    "symbols": [
      "NCE_MULTIPLE_$_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 $ 参数",
    "explanation": "这一行把主轴选择编号写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple e words on one line",
    "symbols": [
      "NCE_MULTIPLE_E_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 E 参数",
    "explanation": "这一行把E 参数写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple f words on one line",
    "symbols": [
      "NCE_MULTIPLE_F_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 F 参数",
    "explanation": "这一行把进给速度写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Negative f word used",
    "symbols": [
      "NCE_NEGATIVE_F_WORD_USED"
    ],
    "title": "进给速度为负数",
    "explanation": "F 指定的进给速度不能是负值；运动方向由目标坐标决定。",
    "animation": "parameters"
  },
  {
    "template": "G-code out of range",
    "symbols": [
      "NCE_G_CODE_OUT_OF_RANGE"
    ],
    "title": "G 指令编号超出允许范围",
    "explanation": "G 后面的数超出了这段解析代码允许的范围，不能识别成有效指令。",
    "animation": "program"
  },
  {
    "template": "Negative g code used",
    "symbols": [
      "NCE_NEGATIVE_G_CODE_USED"
    ],
    "title": "G 指令编号为负数",
    "explanation": "G 后面不能跟负数，例如 G-1 不是有效指令。",
    "animation": "parameters"
  },
  {
    "template": "BUG: G remapping: modal group < 0",
    "symbols": [],
    "title": "G 指令重映射组编号小于零",
    "explanation": "扩展 G 指令使用了不存在的负数分组，属于扩展配置或内部状态异常。",
    "animation": "processing"
  },
  {
    "template": "Two g codes used from same modal group",
    "symbols": [
      "NCE_TWO_G_CODES_USED_FROM_SAME_MODAL_GROUP"
    ],
    "title": "同一行出现互斥的 G 指令",
    "explanation": "这一行要求同一组里的多个模式同时生效，例如既指定直线又指定圆弧运动，软件无法同时执行。",
    "animation": "program"
  },
  {
    "template": "Unknown g code used",
    "symbols": [
      "NCE_UNKNOWN_G_CODE_USED"
    ],
    "title": "G 指令无法识别",
    "explanation": "这个 G 编号在当前解释器中没有对应功能，也没有可用的扩展定义。",
    "animation": "program"
  },
  {
    "template": "Multiple h words on one line",
    "symbols": [
      "NCE_MULTIPLE_H_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 H 参数",
    "explanation": "这一行把长度补偿编号写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Negative h word used",
    "symbols": [
      "NCE_NEGATIVE_H_WORD_USED"
    ],
    "title": "刀具长度补偿编号 H 为负数",
    "explanation": "H 用来选择刀具长度补偿项，这里不允许负数编号。",
    "animation": "tool-setup"
  },
  {
    "template": "Multiple i words on one line",
    "symbols": [
      "NCE_MULTIPLE_I_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 I 参数",
    "explanation": "这一行把I 参数写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Bad format unsigned integer",
    "symbols": [
      "NCE_BAD_FORMAT_UNSIGNED_INTEGER"
    ],
    "title": "无符号整数格式错误",
    "explanation": "这里需要不带负号的整数，实际内容不符合这种数字格式。",
    "animation": "parameters"
  },
  {
    "template": "Sscanf failed",
    "symbols": [
      "NCE_SSCANF_FAILED"
    ],
    "title": "底层文本解析失败",
    "explanation": "软件调用数值读取函数时没读出预期内容，属于输入格式或内部解析异常，需查看出错位置。",
    "animation": "program"
  },
  {
    "template": "Multiple a words on one line",
    "symbols": [
      "NCE_MULTIPLE_A_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 A 参数",
    "explanation": "这一行把A 旋转轴位置写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Unexpected character after O-word",
    "symbols": [],
    "title": "O 标签后出现多余字符",
    "explanation": "O 编号或名称结束后跟了不允许的内容，软件无法确定这条流程语句的含义。",
    "animation": "program"
  },
  {
    "template": "Multiple j words on one line",
    "symbols": [
      "NCE_MULTIPLE_J_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 J 参数",
    "explanation": "这一行把J 参数写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "Multiple k words on one line",
    "symbols": [
      "NCE_MULTIPLE_K_WORDS_ON_ONE_LINE"
    ],
    "title": "同一程序行重复指定 K 参数",
    "explanation": "这一行把K 参数写了不止一次。解释器不允许这样重复指定，不能猜哪个值才是你想用的。",
    "animation": "program"
  },
  {
    "template": "convert_remapped_code: initial read returned %s",
    "symbols": [],
    "title": "重映射指令初始化读取失败",
    "explanation": "软件准备执行自定义 G/M 指令时，第一步读取就没有成功；后面的返回信息说明具体原因。",
    "animation": "processing"
  },
  {
    "template": "BUG: add_parameters: remap_frame: executing_remap == NULL ",
    "symbols": [],
    "title": "重映射参数处理缺少活动指令",
    "explanation": "软件准备给扩展指令传参数，却发现没有正在执行的扩展指令，属于内部状态异常。",
    "animation": "processing"
  },
  {
    "template": "BUG: add_parameters: argspec = NULL",
    "symbols": [],
    "title": "重映射指令缺少参数规则",
    "explanation": "扩展指令没有提供应有的参数定义，软件不知道该收哪些参数。",
    "animation": "processing"
  },
  {
    "template": "add_parameters: can't add '%s' to args",
    "symbols": [],
    "title": "重映射参数加入失败",
    "explanation": "报错指出的参数没能加入扩展指令的参数列表，扩展调用因此不能继续。",
    "animation": "processing"
  },
  {
    "template": "user-defined %s:%s",
    "symbols": [],
    "title": "自定义指令报告错误",
    "explanation": "这是扩展指令自己返回的报错。占位符会换成实际内容，真正原因要看运行时展开后的那句话。",
    "animation": "program"
  },
  {
    "template": "BUG: convert_remapped_code: no remapping",
    "symbols": [],
    "title": "重映射执行入口缺少映射定义",
    "explanation": "进入了扩展指令的执行代码，却找不到对应的扩展定义，属于配置或内部状态异常。",
    "animation": "processing"
  },
  {
    "template": "exception adding Python predefined named parameter: %s",
    "symbols": [],
    "title": "Python 预定义命名参数添加失败",
    "explanation": "软件把 Python 扩展提供的参数接入解释器时出了异常，后面的异常文字说明具体失败原因。",
    "animation": "processing"
  },
  {
    "template": "A file is already open",
    "symbols": [
      "NCE_A_FILE_IS_ALREADY_OPEN"
    ],
    "title": "已有程序文件处于打开状态",
    "explanation": "软件还开着一个程序文件，又收到不允许在此时执行的打开请求。",
    "animation": "file-access"
  },
  {
    "template": "File name too long",
    "symbols": [
      "NCE_FILE_NAME_TOO_LONG"
    ],
    "title": "程序文件名或路径过长",
    "explanation": "传入的文件名或完整路径超过了这处代码支持的长度。",
    "animation": "file-access"
  },
  {
    "template": "Queue is not empty after probing",
    "symbols": [
      "NCE_QUEUE_IS_NOT_EMPTY_AFTER_PROBING"
    ],
    "title": "探测完成后执行队列仍未清空",
    "explanation": "探针动作之后本应完成的队列同步没有完成，软件还留着待处理动作，不能继续假定位置已经确定。",
    "animation": "processing"
  },
  {
    "template": "Queue is not empty after tool change",
    "symbols": [],
    "title": "换刀完成后执行队列仍未清空",
    "explanation": "换刀之后本应完成的队列同步没有完成，软件仍留有待处理动作，执行状态没有衔接好。",
    "animation": "tool-setup"
  },
  {
    "template": "Queue is not empty after external input",
    "symbols": [
      "NCE_QUEUE_IS_NOT_EMPTY_AFTER_INPUT"
    ],
    "title": "等待外部输入后执行队列仍未清空",
    "explanation": "读取外部信号之后，执行队列没有按要求清空，软件还不能继续往后解释。",
    "animation": "processing"
  },
  {
    "template": "Failed to find sub 'O%s' before EOF",
    "symbols": [],
    "title": "文件中找不到指定子程序",
    "explanation": "一直读到文件末尾，仍没有找到要调用的那个 O 子程序。",
    "animation": "file-access"
  },
  {
    "template": "Unable to open parameter file: '%s'",
    "symbols": [],
    "title": "无法打开参数存储文件",
    "explanation": "软件无法读取或访问用于保存参数的文件；实际路径会显示在原文中，可能是路径、权限或文件本身的问题。",
    "animation": "file-access"
  },
  {
    "template": "Parameter file out of order",
    "symbols": [
      "NCE_PARAMETER_FILE_OUT_OF_ORDER"
    ],
    "title": "参数存储文件的编号顺序错误",
    "explanation": "保存参数的文件没有按要求排列编号，软件无法按规定顺序装载它。",
    "animation": "file-access"
  },
  {
    "template": "Cannot open variable file",
    "symbols": [
      "NCE_CANNOT_OPEN_VARIABLE_FILE"
    ],
    "title": "无法打开变量文件",
    "explanation": "软件要读取或写入保存变量的文件，但文件没有成功打开。",
    "animation": "file-access"
  },
  {
    "template": "Parameter file name is missing",
    "symbols": [],
    "title": "没有配置参数文件名",
    "explanation": "软件需要一个用于保存参数的文件位置，但没有拿到文件名。",
    "animation": "file-access"
  },
  {
    "template": "maximum nesting of remapped blocks exceeded",
    "symbols": [],
    "title": "重映射指令嵌套过深",
    "explanation": "自定义指令一层调用另一层，层数超过了软件允许的上限。",
    "animation": "processing"
  },
  {
    "template": "BUG: remap_level < 0 : %d",
    "symbols": [],
    "title": "重映射嵌套层数变成负数",
    "explanation": "软件记录的调用层数不可能小于零，说明内部调用与退出过程出现了不一致。",
    "animation": "parameters"
  },
  {
    "template": "recursive remapping for %s detected",
    "symbols": [],
    "title": "检测到递归重映射调用",
    "explanation": "自定义指令直接或间接又调用了自己，软件检测到这种循环调用并停止继续展开。",
    "animation": "processing"
  },
  {
    "template": "BUG: execute_block: got %d - not in remappings() !! (next_remap=%d)",
    "symbols": [],
    "title": "程序块执行收到未登记的重映射编号",
    "explanation": "软件要执行一个扩展步骤，但这个步骤不在当前记录的扩展列表里，属于内部状态异常。",
    "animation": "processing"
  },
  {
    "template": "remap_finished: got %d - not in cblock.remappings!",
    "symbols": [],
    "title": "完成的重映射不在当前程序块列表中",
    "explanation": "一个扩展步骤报告完成，但当前程序块并没有登记它，软件的执行记录对不上。",
    "animation": "processing"
  },
  {
    "template": "BUG - remappings not empty",
    "symbols": [],
    "title": "重映射结束后仍有未处理项",
    "explanation": "本应清空的扩展执行列表仍有内容，说明扩展指令的处理过程没有正确收尾。",
    "animation": "processing"
  },
  {
    "template": "BUG - check find_remappings()!! status=%d nesting=%d",
    "symbols": [],
    "title": "重映射查找状态异常",
    "explanation": "软件查找自定义指令时，返回状态或嵌套层数不符合预期，需要检查扩展定义和解释器逻辑。",
    "animation": "processing"
  },
  {
    "template": "BUG: remap_finished(): phase=%d nesting=%d",
    "symbols": [],
    "title": "重映射结束阶段与嵌套状态异常",
    "explanation": "扩展指令结束时，软件记录的执行阶段或调用层数不正确，属于内部状态异常。",
    "animation": "processing"
  },
  {
    "template": "Negative p word used",
    "symbols": [
      "NCE_NEGATIVE_P_WORD_USED"
    ],
    "title": "P 参数为负数",
    "explanation": "当前用途不接受负 P 值；具体 P 的含义要看它所在的指令。",
    "animation": "parameters"
  },
  {
    "template": "Spindle not turning clockwise in g84",
    "symbols": [
      "NCE_SPINDLE_NOT_TURNING_CLOCKWISE_IN_G84"
    ],
    "title": "G84 攻丝循环要求主轴正转",
    "explanation": "进入 G84 时主轴没有按要求正转；",
    "animation": "spindle-stop"
  },
  {
    "template": "Pocket max too large",
    "symbols": [
      "NCE_POCKET_MAX_TOO_LARGE"
    ],
    "title": "刀库容量配置超过允许范围",
    "explanation": "刀库的最大刀位数设置过大；",
    "animation": "program"
  },
  {
    "template": "Zero radius arc",
    "symbols": [
      "NCE_ZERO_RADIUS_ARC"
    ],
    "title": "圆弧半径为零",
    "explanation": "圆心和用于确定半径的点重合了，画不出有大小的圆弧。",
    "animation": "program"
  },
  {
    "template": "Too many oword labels",
    "symbols": [
      "NCE_TOO_MANY_OWORD_LABELS"
    ],
    "title": "O 标签数量超过容量",
    "explanation": "子程序或流程标签太多，超过了可存储数量；",
    "animation": "program"
  },
  {
    "template": "Bad number format",
    "symbols": [
      "NCE_BAD_NUMBER_FORMAT"
    ],
    "title": "数字格式不合法",
    "explanation": "写在数字位置的内容不符合数字写法。",
    "animation": "parameters"
  },
  {
    "template": "Cannot create backup file",
    "symbols": [
      "NCE_CANNOT_CREATE_BACKUP_FILE"
    ],
    "title": "无法创建参数备份文件",
    "explanation": "软件想新建一个备份文件，但创建失败了；具体可能涉及路径、权限或存储空间。",
    "animation": "file-access"
  },
  {
    "template": "Cannot open backup file",
    "symbols": [
      "NCE_CANNOT_OPEN_BACKUP_FILE"
    ],
    "title": "无法打开参数备份文件",
    "explanation": "软件想打开备份文件，但没有成功；具体原因要看文件路径及系统返回。",
    "animation": "file-access"
  }
];
