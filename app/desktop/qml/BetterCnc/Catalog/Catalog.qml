pragma Singleton
import QtQml
import "ErrorExplanations.js" as ErrorCopy

QtObject {
    function explainError(raw, context) { return ErrorCopy.explain(raw, context); }
    function errorIllustration(animation, poster) {
        const name = ErrorCopy.animations.indexOf(animation) >= 0 ? animation : "unknown";
        return Qt.resolvedUrl("assets/error-" + name + (poster ? ".png" : ".gif"));
    }
    readonly property var axes: [
      "X",
      "Y",
      "Z"
    ]
    readonly property var coordinateSystems: [
      "G54",
      "G55",
      "G56",
      "G57",
      "G58",
      "G59",
      "G59.1",
      "G59.2",
      "G59.3"
    ]
    readonly property var menus: [
      {
        "id": "file",
        "label": "文件",
        "children": [
          {
            "id": "file.open",
            "label": "打开程序…",
            "shortcut": "O"
          },
          {
            "id": "file.recent",
            "label": "最近打开",
            "children": [
              {
                "id": "file.open-sample",
                "label": "axis.ngc"
              },
              {
                "id": "file.recent-s1",
                "label": "",
                "kind": "separator"
              },
              {
                "id": "file.clear-recents",
                "label": "清空最近打开记录"
              }
            ]
          },
          {
            "id": "file.edit",
            "label": "编辑程序…"
          },
          {
            "id": "file.reload",
            "label": "重新加载",
            "shortcut": "Ctrl+R"
          },
          {
            "id": "file.save",
            "label": "程序另存为…",
            "shortcut": "Ctrl+S"
          },
          {
            "id": "file.properties",
            "label": "程序属性…"
          },
          {
            "id": "file.s1",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "tool.edit",
            "label": "编辑刀具表…"
          },
          {
            "id": "tool.reload",
            "label": "重新加载刀具表"
          },
          {
            "id": "file.s2",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "machine.ladder",
            "label": "梯形图编辑器…"
          },
          {
            "id": "file.s3",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "file.quit",
            "label": "退出"
          }
        ]
      },
      {
        "id": "machine",
        "label": "机床",
        "children": [
          {
            "id": "machine.estop",
            "label": "切换急停状态",
            "shortcut": "F1"
          },
          {
            "id": "machine.power",
            "label": "机床使能／关闭",
            "shortcut": "F2"
          },
          {
            "id": "machine.s1",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "program.run",
            "label": "运行程序",
            "shortcut": "R"
          },
          {
            "id": "program.run-line",
            "label": "从选中行运行"
          },
          {
            "id": "program.step",
            "label": "单段运行",
            "shortcut": "T"
          },
          {
            "id": "program.pause",
            "label": "暂停运行",
            "shortcut": "P"
          },
          {
            "id": "program.resume",
            "label": "继续运行",
            "shortcut": "S"
          },
          {
            "id": "program.stop",
            "label": "停止运行",
            "shortcut": "Esc"
          },
          {
            "id": "program.optional",
            "label": "选择停（M1）",
            "kind": "check"
          },
          {
            "id": "program.block-delete",
            "label": "程序段跳过（/）",
            "kind": "check"
          },
          {
            "id": "machine.s2",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "mdi.clear",
            "label": "清空手动输入历史",
            "shortcut": "Ctrl+M"
          },
          {
            "id": "mdi.copy",
            "label": "复制历史指令",
            "shortcut": "Ctrl+H"
          },
          {
            "id": "mdi.paste",
            "label": "粘贴到历史指令",
            "shortcut": "Ctrl+Shift+H"
          },
          {
            "id": "machine.s3",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "machine.calibration",
            "label": "参数校准"
          },
          {
            "id": "machine.hal-config",
            "label": "查看 HAL 配置"
          },
          {
            "id": "machine.hal-meter",
            "label": "HAL 信号监视"
          },
          {
            "id": "machine.hal-scope",
            "label": "HAL 示波器"
          },
          {
            "id": "machine.status",
            "label": "查看控制器状态"
          },
          {
            "id": "machine.debug",
            "label": "设置调试级别"
          },
          {
            "id": "machine.s4",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "machine.homing",
            "label": "回零",
            "children": [
              {
                "id": "machine.home-all",
                "label": "全部轴回零"
              },
              {
                "id": "machine.home-X",
                "label": "X 轴回零"
              },
              {
                "id": "machine.home-Y",
                "label": "Y 轴回零"
              },
              {
                "id": "machine.home-Z",
                "label": "Z 轴回零"
              }
            ]
          },
          {
            "id": "machine.unhoming",
            "label": "清除回零状态",
            "children": [
              {
                "id": "machine.unhome-all",
                "label": "清除全部轴回零状态"
              },
              {
                "id": "machine.unhome-X",
                "label": "清除 X 轴回零状态"
              },
              {
                "id": "machine.unhome-Y",
                "label": "清除 Y 轴回零状态"
              },
              {
                "id": "machine.unhome-Z",
                "label": "清除 Z 轴回零状态"
              }
            ]
          },
          {
            "id": "machine.zero",
            "label": "清除坐标系偏置",
            "children": [
              {
                "id": "machine.zero-G54",
                "label": "G54 工件坐标系（P1）"
              },
              {
                "id": "machine.zero-G55",
                "label": "G55 工件坐标系（P2）"
              },
              {
                "id": "machine.zero-G56",
                "label": "G56 工件坐标系（P3）"
              },
              {
                "id": "machine.zero-G57",
                "label": "G57 工件坐标系（P4）"
              },
              {
                "id": "machine.zero-G58",
                "label": "G58 工件坐标系（P5）"
              },
              {
                "id": "machine.zero-G59",
                "label": "G59 工件坐标系（P6）"
              },
              {
                "id": "machine.zero-G59.1",
                "label": "G59.1 工件坐标系（P7）"
              },
              {
                "id": "machine.zero-G59.2",
                "label": "G59.2 工件坐标系（P8）"
              },
              {
                "id": "machine.zero-G59.3",
                "label": "G59.3 工件坐标系（P9）"
              },
              {
                "id": "machine.zero-G92",
                "label": "G92 临时坐标偏置"
              }
            ]
          },
          {
            "id": "machine.s5",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "touch.workpiece",
            "label": "以工件为对刀基准",
            "kind": "radio",
            "group": "touch",
            "value": "workpiece"
          },
          {
            "id": "touch.fixture",
            "label": "以夹具为对刀基准",
            "kind": "radio",
            "group": "touch",
            "value": "fixture"
          }
        ]
      },
      {
        "id": "view",
        "label": "视图",
        "children": [
          {
            "id": "view.z",
            "label": "俯视图",
            "shortcut": "V",
            "kind": "radio",
            "group": "view",
            "value": "z"
          },
          {
            "id": "view.z2",
            "label": "旋转俯视图",
            "shortcut": "V",
            "kind": "radio",
            "group": "view",
            "value": "z2"
          },
          {
            "id": "view.x",
            "label": "侧视图",
            "shortcut": "V",
            "kind": "radio",
            "group": "view",
            "value": "x"
          },
          {
            "id": "view.y",
            "label": "正视图",
            "shortcut": "V",
            "kind": "radio",
            "group": "view",
            "value": "y"
          },
          {
            "id": "view.p",
            "label": "透视图",
            "shortcut": "V",
            "kind": "radio",
            "group": "view",
            "value": "p"
          },
          {
            "id": "view.s1",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "units.inch",
            "label": "使用英寸显示",
            "shortcut": "!",
            "kind": "radio",
            "group": "units",
            "value": "inch"
          },
          {
            "id": "units.mm",
            "label": "使用毫米显示",
            "shortcut": "!",
            "kind": "radio",
            "group": "units",
            "value": "mm"
          },
          {
            "id": "view.s2",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "show.program",
            "label": "显示程序刀路",
            "kind": "check"
          },
          {
            "id": "show.rapids",
            "label": "显示快速移动轨迹",
            "kind": "check"
          },
          {
            "id": "show.alpha",
            "label": "半透明显示刀路",
            "kind": "check"
          },
          {
            "id": "show.live",
            "label": "显示实际运动轨迹",
            "kind": "check"
          },
          {
            "id": "show.tool",
            "label": "显示刀具",
            "kind": "check"
          },
          {
            "id": "show.extents",
            "label": "显示加工范围",
            "kind": "check"
          },
          {
            "id": "view.grid",
            "label": "网格",
            "children": [
              {
                "id": "grid.off",
                "label": "隐藏网格",
                "kind": "radio",
                "group": "grid",
                "value": "off"
              },
              {
                "id": "view.grid-custom",
                "label": "自定义间距…"
              },
              {
                "id": "grid.10mm",
                "label": "10 毫米",
                "kind": "radio",
                "group": "grid",
                "value": "10mm"
              },
              {
                "id": "grid.20mm",
                "label": "20 毫米",
                "kind": "radio",
                "group": "grid",
                "value": "20mm"
              },
              {
                "id": "grid.50mm",
                "label": "50 毫米",
                "kind": "radio",
                "group": "grid",
                "value": "50mm"
              },
              {
                "id": "grid.100mm",
                "label": "100 毫米",
                "kind": "radio",
                "group": "grid",
                "value": "100mm"
              },
              {
                "id": "grid.1in",
                "label": "1 英寸",
                "kind": "radio",
                "group": "grid",
                "value": "1in"
              },
              {
                "id": "grid.2in",
                "label": "2 英寸",
                "kind": "radio",
                "group": "grid",
                "value": "2in"
              },
              {
                "id": "grid.5in",
                "label": "5 英寸",
                "kind": "radio",
                "group": "grid",
                "value": "5in"
              },
              {
                "id": "grid.10in",
                "label": "10 英寸",
                "kind": "radio",
                "group": "grid",
                "value": "10in"
              }
            ]
          },
          {
            "id": "show.offsets",
            "label": "显示坐标偏置",
            "kind": "check"
          },
          {
            "id": "show.limits",
            "label": "显示机床行程范围",
            "kind": "check"
          },
          {
            "id": "show.velocity",
            "label": "显示当前速度",
            "kind": "check"
          },
          {
            "id": "show.dtg",
            "label": "显示剩余行程",
            "kind": "check"
          },
          {
            "id": "show.large",
            "label": "放大坐标字体",
            "kind": "check"
          },
          {
            "id": "view.clear",
            "label": "清除实际运动轨迹",
            "shortcut": "Ctrl+K"
          },
          {
            "id": "show.pyvcp",
            "label": "显示自定义面板（PyVCP）",
            "shortcut": "Ctrl+E",
            "kind": "check"
          },
          {
            "id": "view.s3",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "position.commanded",
            "label": "显示指令位置",
            "shortcut": "@",
            "kind": "radio",
            "group": "position",
            "value": "commanded"
          },
          {
            "id": "position.actual",
            "label": "显示实际位置",
            "shortcut": "@",
            "kind": "radio",
            "group": "position",
            "value": "actual"
          },
          {
            "id": "view.s4",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "coordinates.machine",
            "label": "显示机床坐标",
            "shortcut": "#",
            "kind": "radio",
            "group": "coordinates",
            "value": "machine"
          },
          {
            "id": "coordinates.relative",
            "label": "显示工件坐标",
            "shortcut": "#",
            "kind": "radio",
            "group": "coordinates",
            "value": "relative"
          },
          {
            "id": "view.s5",
            "label": "",
            "kind": "separator"
          },
          {
            "id": "mode.joint",
            "label": "关节模式",
            "shortcut": "$",
            "kind": "radio",
            "group": "mode",
            "value": "joint"
          },
          {
            "id": "mode.world",
            "label": "坐标轴模式",
            "shortcut": "$",
            "kind": "radio",
            "group": "mode",
            "value": "world"
          }
        ]
      },
      {
        "id": "help",
        "label": "帮助",
        "children": [
          {
            "id": "help.about",
            "label": "关于本界面"
          },
          {
            "id": "help.reference",
            "label": "快捷键说明"
          }
        ]
      }
    ]
    readonly property var toolbar: [
      {
        "id": "machine.estop",
        "label": "切换急停状态 [F1]",
        "icon": "tool_estop"
      },
      {
        "id": "machine.power",
        "label": "机床使能／关闭 [F2]",
        "icon": "tool_power"
      },
      {
        "id": "file.open",
        "label": "打开加工程序 [O]",
        "icon": "tool_open",
        "separator": true
      },
      {
        "id": "file.reload",
        "label": "重新加载当前程序 [Ctrl+R]",
        "icon": "tool_reload"
      },
      {
        "id": "program.run",
        "label": "运行当前程序 [R]",
        "icon": "tool_run",
        "separator": true
      },
      {
        "id": "program.step",
        "label": "单段运行 [T]",
        "icon": "tool_step"
      },
      {
        "id": "program.pause",
        "label": "暂停 [P]／继续运行 [S]",
        "icon": "tool_pause"
      },
      {
        "id": "program.stop",
        "label": "停止程序 [Esc]",
        "icon": "tool_stop"
      },
      {
        "id": "program.block-delete",
        "label": "程序段跳过（/）",
        "icon": "tool_blockdelete",
        "separator": true
      },
      {
        "id": "program.optional",
        "label": "选择停（M1）",
        "icon": "tool_optpause"
      },
      {
        "id": "view.zoom-in",
        "label": "放大",
        "icon": "tool_zoomin",
        "separator": true
      },
      {
        "id": "view.zoom-out",
        "label": "缩小",
        "icon": "tool_zoomout"
      },
      {
        "id": "view.z",
        "label": "俯视图",
        "icon": "tool_axis_z"
      },
      {
        "id": "view.z2",
        "label": "旋转俯视图",
        "icon": "tool_axis_z2"
      },
      {
        "id": "view.x",
        "label": "侧视图",
        "icon": "tool_axis_x"
      },
      {
        "id": "view.y",
        "label": "正视图",
        "icon": "tool_axis_y"
      },
      {
        "id": "view.p",
        "label": "透视图",
        "icon": "tool_axis_p"
      },
      {
        "id": "view.rotate",
        "label": "切换平移／旋转视图 [D]",
        "icon": "tool_rotate"
      },
      {
        "id": "view.clear",
        "label": "清除实际运动轨迹 [Ctrl+K]",
        "icon": "tool_clear",
        "separator": true
      }
    ]
    readonly property var quickReference: [
      [
        "F1",
        "急停"
      ],
      [
        "F2",
        "机床使能／关闭"
      ],
      [
        "F3",
        "手动操作"
      ],
      [
        "F5",
        "手动输入指令"
      ],
      [
        "O",
        "打开程序"
      ],
      [
        "Ctrl+R",
        "重新加载程序"
      ],
      [
        "R / T",
        "运行程序／单段运行"
      ],
      [
        "P / S",
        "暂停／继续运行"
      ],
      [
        "Esc",
        "停止运行"
      ],
      [
        "X / Y / Z",
        "选择坐标轴"
      ],
      [
        "← → / ↑ ↓ / PgUp PgDn",
        "X／Y／Z 轴点动"
      ],
      [
        "Home",
        "选中轴回零"
      ],
      [
        "End",
        "工件对刀"
      ],
      [
        "V",
        "切换视图"
      ],
      [
        "D",
        "平移／旋转视图"
      ],
      [
        "Ctrl+K",
        "清除实际运动轨迹"
      ],
      [
        "! / @ / #",
        "切换单位／位置类型／坐标系"
      ]
    ]
    readonly property var fixture: {
      "fileName": "axis.ngc",
      "machine": "LinuxCNC-HAL-SIM-AXIS",
      "version": "2.9.10",
      "taskState": "急停",
      "tool": "未装刀",
      "activeCodes": "G0 G17 G21 G40 G49 G54 G64 G80 G90 G91.1 G94 G97 G98\nM5 M9 M48  F0.0 S0.0",
      "history": [
        "G0 X0 Y0",
        "G0 Z10",
        "G54"
      ]
    }
    readonly property var sampleProgram: [
      "( AXIS 标识演示程序，不用于实际加工 )",
      "( 原程序说明：如需试运行，可能需要先进行 Z 轴工件对刀。 )",
      "( 对刀方式取决于实际机床配置及工件位置。 )",
      "( 原程序提示：先将 Z 轴向下点动少许，再进行对刀。 )",
      "( 切换“程序段跳过”可查看带 / 标记程序段的效果。 )",
      "( 图形尺寸不合适时，可调整下方 scale 缩放参数。 )",
      "( LinuxCNC 原作时间：2012年1月19日 14:13:51 )",
      "#<depth>=2.0",
      "#<scale>=1.0",
      "G21 G90 G64 G40",
      "G0 Z3.0",
      "( 雕刻 )",
      "G17",
      "M3 S10000",
      "G0 X[1.75781*#<scale>] Y[0.5*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G1 F400.0 X[5.95508*#<scale>] Y[20.54297*#<scale>]",
      "G1 X[10.07031*#<scale>]",
      "G1 X[6.58398*#<scale>] Y[3.84961*#<scale>]",
      "G1 X[16.7832*#<scale>]",
      "G1 X[16.08594*#<scale>] Y[0.5*#<scale>]",
      "G1 X[1.75781*#<scale>]",
      "G0 Z3.0",
      "G0 X[18.72461*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G1 F400.0 X[21.75977*#<scale>] Y[15.01953*#<scale>]",
      "G1 X[25.68359*#<scale>]",
      "G1 X[22.64844*#<scale>] Y[0.5*#<scale>]",
      "G1 X[18.72461*#<scale>]",
      "G0 Z3.0",
      "G0 X[26.55859*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G1 F400.0 X[29.59375*#<scale>] Y[15.01953*#<scale>]",
      "G1 X[33.3125*#<scale>]",
      "G1 X[32.92969*#<scale>] Y[13.13281*#<scale>]",
      "G2 X[34.16342*#<scale>] Y[14.08624*#<scale>] I[8.82141*#<scale>] J[-10.13994*#<scale>]",
      "G2 X[35.52734*#<scale>] Y[14.8418*#<scale>] I[4.53823*#<scale>] J[-6.58354*#<scale>]",
      "G2 X[38.08398*#<scale>] Y[15.36133*#<scale>] I[2.53506*#<scale>] J[-5.9247*#<scale>]",
      "G2 X[39.5966*#<scale>] Y[15.13543*#<scale>] I[0.06403*#<scale>] J[-4.74845*#<scale>]",
      "G2 X[40.90039*#<scale>] Y[14.33594*#<scale>] I[-1.02874*#<scale>] J[-3.14049*#<scale>]",
      "G2 X[41.7019*#<scale>] Y[13.08328*#<scale>] I[-2.33045*#<scale>] J[-2.37388*#<scale>]",
      "G2 X[41.93945*#<scale>] Y[11.61523*#<scale>] I[-4.07102*#<scale>] J[-1.41199*#<scale>]",
      "G2 X[41.76899*#<scale>] Y[10.15744*#<scale>] I[-10.17473*#<scale>] J[0.45091*#<scale>]",
      "G2 X[41.48828*#<scale>] Y[8.7168*#<scale>] I[-39.45138*#<scale>] J[6.93932*#<scale>]",
      "G1 X[39.7793*#<scale>] Y[0.5*#<scale>]",
      "G1 X[35.85547*#<scale>]",
      "G1 X[37.57813*#<scale>] Y[8.74414*#<scale>]",
      "G3 X[37.79665*#<scale>] Y[9.84001*#<scale>] I[-62.81729*#<scale>] J[13.09579*#<scale>]",
      "G3 X[37.96094*#<scale>] Y[10.94531*#<scale>] I[-9.6524*#<scale>] J[1.99958*#<scale>]",
      "G3 X[37.50977*#<scale>] Y[12.12109*#<scale>] I[-1.54162*#<scale>] J[0.0829*#<scale>]",
      "G3 X[36.2793*#<scale>] Y[12.55859*#<scale>] I[-1.13356*#<scale>] J[-1.23903*#<scale>]",
      "G3 X[35.26888*#<scale>] Y[12.33731*#<scale>] I[0.05277*#<scale>] J[-2.65845*#<scale>]",
      "G3 X[34.36523*#<scale>] Y[11.83398*#<scale>] I[1.956*#<scale>] J[-4.57455*#<scale>]",
      "G3 X[32.71094*#<scale>] Y[9.91992*#<scale>] I[2.86418*#<scale>] J[-4.1474*#<scale>]",
      "G3 X[32.13267*#<scale>] Y[8.21493*#<scale>] I[8.76492*#<scale>] J[-3.92328*#<scale>]",
      "G3 X[31.72656*#<scale>] Y[6.46094*#<scale>] I[36.34493*#<scale>] J[-9.33906*#<scale>]",
      "G1 X[30.48242*#<scale>] Y[0.5*#<scale>]",
      "G1 X[26.55859*#<scale>]",
      "G0 Z3.0",
      "G0 X[26.09375*#<scale>] Y[16.98828*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G1 F400.0 X[22.16992*#<scale>]",
      "G1 X[22.9082*#<scale>] Y[20.54297*#<scale>]",
      "G1 X[26.83203*#<scale>]",
      "G1 X[26.09375*#<scale>] Y[16.98828*#<scale>]",
      "G0 Z3.0",
      "G0 X[46.14777*#<scale>] Y[12.78778*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G1 F400.0 X[46.61523*#<scale>] Y[15.01953*#<scale>]",
      "G1 X[50.53906*#<scale>]",
      "G1 X[48.74805*#<scale>] Y[6.41992*#<scale>]",
      "G3 X[48.55485*#<scale>] Y[5.46101*#<scale>] I[39.83359*#<scale>] J[-8.52447*#<scale>]",
      "G3 X[48.41992*#<scale>] Y[4.49219*#<scale>] I[7.34343*#<scale>] J[-1.51652*#<scale>]",
      "G3 X[48.88477*#<scale>] Y[3.41211*#<scale>] I[1.45252*#<scale>] J[-0.01493*#<scale>]",
      "G3 X[50.07422*#<scale>] Y[2.96094*#<scale>] I[1.13093*#<scale>] J[1.18803*#<scale>]",
      "G3 X[51.09961*#<scale>] Y[3.15234*#<scale>] I[-0.00663*#<scale>] J[2.87782*#<scale>]",
      "G3 X[52.13867*#<scale>] Y[3.75391*#<scale>] I[-1.85377*#<scale>] J[4.40013*#<scale>]",
      "G3 X[53.0957*#<scale>] Y[4.68359*#<scale>] I[-3.51724*#<scale>] J[4.57812*#<scale>]",
      "G3 X[53.88867*#<scale>] Y[6.05078*#<scale>] I[-4.71119*#<scale>] J[3.64605*#<scale>]",
      "G3 X[54.44922*#<scale>] Y[8.10156*#<scale>] I[-12.97687*#<scale>] J[4.64901*#<scale>]",
      "G1 X[55.89844*#<scale>] Y[15.01953*#<scale>]",
      "G1 X[59.82227*#<scale>]",
      "G1 X[56.78711*#<scale>] Y[0.5*#<scale>]",
      "G1 X[53.12305*#<scale>]",
      "G1 X[53.5332*#<scale>] Y[2.46875*#<scale>]",
      "G2 X[51.14513*#<scale>] Y[0.79202*#<scale>] I[-6.21919*#<scale>] J[6.3187*#<scale>]",
      "G2 X[48.29688*#<scale>] Y[0.1582*#<scale>] I[-2.84268*#<scale>] J[6.05776*#<scale>]",
      "G2 X[46.78426*#<scale>] Y[0.3841*#<scale>] I[-0.06403*#<scale>] J[4.74845*#<scale>]",
      "G2 X[45.48047*#<scale>] Y[1.18359*#<scale>] I[1.02874*#<scale>] J[3.14049*#<scale>]",
      "G2 X[44.68637*#<scale>] Y[2.45262*#<scale>] I[2.34744*#<scale>] J[2.35189*#<scale>]",
      "G2 X[44.45508*#<scale>] Y[3.93164*#<scale>] I[4.23866*#<scale>] J[1.42044*#<scale>]",
      "G2 X[44.63379*#<scale>] Y[5.43705*#<scale>] I[10.83187*#<scale>] J[-0.52256*#<scale>]",
      "G2 X[44.91992*#<scale>] Y[6.92578*#<scale>] I[45.15644*#<scale>] J[-7.90718*#<scale>]",
      "G1 X[46.14777*#<scale>] Y[12.78778*#<scale>]",
      "G0 Z3.0",
      "G0 X[61.99609*#<scale>] Y[15.01953*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G1 F400.0 X[66.16602*#<scale>]",
      "G1 X[68.28516*#<scale>] Y[10.87695*#<scale>]",
      "G1 X[71.96289*#<scale>] Y[15.01953*#<scale>]",
      "G1 X[76.73438*#<scale>]",
      "G1 X[69.99414*#<scale>] Y[7.48633*#<scale>]",
      "G1 X[73.6582*#<scale>] Y[0.5*#<scale>]",
      "G1 X[69.48828*#<scale>]",
      "G1 X[67.39648*#<scale>] Y[4.57422*#<scale>]",
      "G1 X[63.78711*#<scale>] Y[0.5*#<scale>]",
      "G1 X[58.97461*#<scale>]",
      "G1 X[65.6875*#<scale>] Y[7.9375*#<scale>]",
      "G1 X[61.99609*#<scale>] Y[15.01953*#<scale>]",
      "G0 Z3.0",
      "G0 X[78.12067*#<scale>] Y[11.80439*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G2 F400.0 X[78.15861*#<scale>] Y[11.98873*#<scale>] I[14.86609*#<scale>] J[-2.96421*#<scale>]",
      "G2 X[79.20898*#<scale>] Y[15.0332*#<scale>] I[13.03118*#<scale>] J[-2.79244*#<scale>]",
      "G2 X[80.8214*#<scale>] Y[17.48665*#<scale>] I[10.09107*#<scale>] J[-4.87534*#<scale>]",
      "G2 X[83.06445*#<scale>] Y[19.38086*#<scale>] I[7.26534*#<scale>] J[-6.32817*#<scale>]",
      "G2 X[88.42383*#<scale>] Y[20.88477*#<scale>] I[5.2993*#<scale>] J[-8.5834*#<scale>]",
      "G2 X[91.21708*#<scale>] Y[20.49528*#<scale>] I[0.10667*#<scale>] J[-9.44597*#<scale>]",
      "G2 X[93.6875*#<scale>] Y[19.13477*#<scale>] I[-1.95281*#<scale>] J[-6.46904*#<scale>]",
      "G2 X[95.32764*#<scale>] Y[16.9908*#<scale>] I[-4.27639*#<scale>] J[-4.97078*#<scale>]",
      "G2 X[96.05273*#<scale>] Y[14.39063*#<scale>] I[-7.426*#<scale>] J[-3.47204*#<scale>]",
      "G1 X[92.10156*#<scale>] Y[14.00781*#<scale>]",
      "G3 X[91.68364*#<scale>] Y[15.38196*#<scale>] I[-5.83945*#<scale>] J[-1.02535*#<scale>]",
      "G3 X[90.83008*#<scale>] Y[16.53711*#<scale>] I[-2.94269*#<scale>] J[-1.28147*#<scale>]",
      "G3 X[89.65745*#<scale>] Y[17.15799*#<scale>] I[-2.02111*#<scale>] J[-2.39937*#<scale>]",
      "G3 X[88.3418*#<scale>] Y[17.33008*#<scale>] I[-1.26203*#<scale>] J[-4.53327*#<scale>]",
      "G3 X[85.14258*#<scale>] Y[16.29102*#<scale>] I[0.01526*#<scale>] J[-5.49164*#<scale>]",
      "G3 X[83.72532*#<scale>] Y[14.83462*#<scale>] I[3.39082*#<scale>] J[-4.71749*#<scale>]",
      "G3 X[82.77734*#<scale>] Y[13.03711*#<scale>] I[7.50088*#<scale>] J[-5.10456*#<scale>]",
      "G3 X[81.88867*#<scale>] Y[8.63477*#<scale>] I[10.80218*#<scale>] J[-4.47143*#<scale>]",
      "G3 X[82.12643*#<scale>] Y[6.67148*#<scale>] I[7.47758*#<scale>] J[-0.09047*#<scale>]",
      "G3 X[83.03711*#<scale>] Y[4.91602*#<scale>] I[4.24649*#<scale>] J[1.08898*#<scale>]",
      "G3 X[85.92188*#<scale>] Y[3.60352*#<scale>] I[2.82627*#<scale>] J[2.38541*#<scale>]",
      "G3 X[88.84766*#<scale>] Y[4.64258*#<scale>] I[0.00074*#<scale>] J[4.63663*#<scale>]",
      "G3 X[90.07896*#<scale>] Y[6.0293*#<scale>] I[-3.23186*#<scale>] J[4.10967*#<scale>]",
      "G3 X[90.84375*#<scale>] Y[7.71875*#<scale>] I[-6.5029*#<scale>] J[3.96159*#<scale>]",
      "G1 X[95.0*#<scale>] Y[7.08984*#<scale>]",
      "G2 X[93.56373*#<scale>] Y[4.23114*#<scale>] I[-11.87256*#<scale>] J[4.17484*#<scale>]",
      "G2 X[91.34961*#<scale>] Y[1.92188*#<scale>] I[-7.88363*#<scale>] J[5.34275*#<scale>]",
      "G2 X[88.64367*#<scale>] Y[0.56922*#<scale>] I[-5.3138*#<scale>] J[7.24715*#<scale>]",
      "G2 X[85.64844*#<scale>] Y[0.14453*#<scale>] I[-2.92298*#<scale>] J[9.84046*#<scale>]",
      "G2 X[82.5341*#<scale>] Y[0.63758*#<scale>] I[-0.13266*#<scale>] J[9.24446*#<scale>]",
      "G2 X[79.89258*#<scale>] Y[2.35938*#<scale>] I[2.19287*#<scale>] J[6.25138*#<scale>]",
      "G2 X[78.25253*#<scale>] Y[5.37699*#<scale>] I[5.36449*#<scale>] J[4.87005*#<scale>]",
      "G2 X[77.82813*#<scale>] Y[8.78516*#<scale>] I[12.16539*#<scale>] J[3.2454*#<scale>]",
      "G2 X[78.12067*#<scale>] Y[11.80439*#<scale>] I[15.15864*#<scale>] J[0.05503*#<scale>]",
      "G0 Z3.0",
      "G0 X[98.14159*#<scale>] Y[7.6254*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G1 F400.0 X[100.83789*#<scale>] Y[20.54297*#<scale>]",
      "G1 X[104.69336*#<scale>]",
      "G1 X[110.12109*#<scale>] Y[7.13086*#<scale>]",
      "G1 X[112.92383*#<scale>] Y[20.54297*#<scale>]",
      "G1 X[116.75195*#<scale>]",
      "G1 X[112.56836*#<scale>] Y[0.5*#<scale>]",
      "G1 X[108.72656*#<scale>]",
      "G1 X[103.3125*#<scale>] Y[13.9668*#<scale>]",
      "G1 X[100.49609*#<scale>] Y[0.5*#<scale>]",
      "G1 X[96.6543*#<scale>]",
      "G1 X[98.14159*#<scale>] Y[7.6254*#<scale>]",
      "G0 Z3.0",
      "G0 X[118.27432*#<scale>] Y[8.23889*#<scale>]",
      "G1 F100.0 Z[-#<depth>]",
      "G2 F400.0 X[118.26953*#<scale>] Y[8.78516*#<scale>] I[12.585*#<scale>] J[0.3835*#<scale>]",
      "G2 X[118.60002*#<scale>] Y[11.98873*#<scale>] I[15.15864*#<scale>] J[0.05503*#<scale>]",
      "G2 X[119.65039*#<scale>] Y[15.0332*#<scale>] I[13.03118*#<scale>] J[-2.79244*#<scale>]",
      "G2 X[121.26281*#<scale>] Y[17.48665*#<scale>] I[10.09107*#<scale>] J[-4.87534*#<scale>]",
      "G2 X[123.50586*#<scale>] Y[19.38086*#<scale>] I[7.26534*#<scale>] J[-6.32817*#<scale>]",
      "G2 X[128.86523*#<scale>] Y[20.88477*#<scale>] I[5.2993*#<scale>] J[-8.5834*#<scale>]",
      "G2 X[131.65849*#<scale>] Y[20.49528*#<scale>] I[0.10667*#<scale>] J[-9.44597*#<scale>]",
      "G2 X[134.12891*#<scale>] Y[19.13477*#<scale>] I[-1.95281*#<scale>] J[-6.46904*#<scale>]",
      "G2 X[135.76904*#<scale>] Y[16.9908*#<scale>] I[-4.27639*#<scale>] J[-4.97078*#<scale>]",
      "G2 X[136.49414*#<scale>] Y[14.39063*#<scale>] I[-7.426*#<scale>] J[-3.47204*#<scale>]",
      "G1 X[132.54297*#<scale>] Y[14.00781*#<scale>]",
      "G3 X[132.12504*#<scale>] Y[15.38196*#<scale>] I[-5.83945*#<scale>] J[-1.02535*#<scale>]",
      "G3 X[131.27148*#<scale>] Y[16.53711*#<scale>] I[-2.94269*#<scale>] J[-1.28147*#<scale>]",
      "G3 X[130.09886*#<scale>] Y[17.15799*#<scale>] I[-2.02111*#<scale>] J[-2.39937*#<scale>]",
      "G3 X[128.7832*#<scale>] Y[17.33008*#<scale>] I[-1.26203*#<scale>] J[-4.53327*#<scale>]",
      "G3 X[125.58398*#<scale>] Y[16.29102*#<scale>] I[0.01526*#<scale>] J[-5.49164*#<scale>]",
      "G3 X[124.16673*#<scale>] Y[14.83462*#<scale>] I[3.39082*#<scale>] J[-4.71749*#<scale>]",
      "G3 X[123.21875*#<scale>] Y[13.03711*#<scale>] I[7.50088*#<scale>] J[-5.10456*#<scale>]",
      "G3 X[122.33008*#<scale>] Y[8.63477*#<scale>] I[10.80218*#<scale>] J[-4.47143*#<scale>]",
      "G3 X[122.56784*#<scale>] Y[6.67148*#<scale>] I[7.47758*#<scale>] J[-0.09047*#<scale>]",
      "G3 X[123.47852*#<scale>] Y[4.91602*#<scale>] I[4.24649*#<scale>] J[1.08898*#<scale>]",
      "G3 X[126.36328*#<scale>] Y[3.60352*#<scale>] I[2.82627*#<scale>] J[2.38541*#<scale>]",
      "G3 X[129.28906*#<scale>] Y[4.64258*#<scale>] I[0.00074*#<scale>] J[4.63663*#<scale>]",
      "G3 X[130.52037*#<scale>] Y[6.0293*#<scale>] I[-3.23186*#<scale>] J[4.10967*#<scale>]",
      "G3 X[131.28516*#<scale>] Y[7.71875*#<scale>] I[-6.5029*#<scale>] J[3.96159*#<scale>]",
      "G1 X[135.44141*#<scale>] Y[7.08984*#<scale>]",
      "G2 X[134.00514*#<scale>] Y[4.23114*#<scale>] I[-11.87256*#<scale>] J[4.17484*#<scale>]",
      "G2 X[131.79102*#<scale>] Y[1.92188*#<scale>] I[-7.88363*#<scale>] J[5.34275*#<scale>]",
      "G2 X[129.08508*#<scale>] Y[0.56922*#<scale>] I[-5.3138*#<scale>] J[7.24715*#<scale>]",
      "G2 X[126.08984*#<scale>] Y[0.14453*#<scale>] I[-2.92298*#<scale>] J[9.84046*#<scale>]",
      "G2 X[122.9755*#<scale>] Y[0.63758*#<scale>] I[-0.13266*#<scale>] J[9.24446*#<scale>]",
      "G2 X[120.33398*#<scale>] Y[2.35938*#<scale>] I[2.19287*#<scale>] J[6.25138*#<scale>]",
      "G2 X[118.69393*#<scale>] Y[5.37699*#<scale>] I[5.36449*#<scale>] J[4.87005*#<scale>]",
      "G2 X[118.27432*#<scale>] Y[8.23889*#<scale>] I[12.16539*#<scale>] J[3.2454*#<scale>]",
      "G0 Z3.0",
      "M5",
      "M2"
    ]
    readonly property url axisLogo: Qt.resolvedUrl("assets/axis-48x48.png")
    function findItem(id, entries) {
        const items = entries || menus;
        for (let i = 0; i < items.length; ++i) {
            if (items[i].id === id) return items[i];
            if (items[i].children) {
                const found = findItem(id, items[i].children);
                if (found) return found;
            }
        }
        return null;
    }
}
