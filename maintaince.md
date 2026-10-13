# maintaince.md · 方向与地图

本文件**只指明方向**。测出来的现状由**事实系统本身**承载（`build/FACTS.json` 台账 +
`STATE.md` 末尾的机器块，每提交复跑证真）；硬规矩由 `AGENTS.md` 承载（每次会话自动载入）。
本文件不抄数字、不抄流程 —— 抄了就会漂。

## 这个项目是什么

**OpenModelica → WebAssembly 的浏览器运行时**（纯客户端计算，无服务端执行端点）。
Modelica 语言 + 符号化 + 指标约简 + 跨域物理库（MSL），补上 MATLAB 生态**轴 ③
（Simscape 式非因果物理建模）**——那是姊妹仓 `Octave-Full-Wasm`（轴 ① 语言 + 轴 ② 块图）
**天然给不了**的一块。

**与姊妹仓平级、互不引用**：工具链不同（那边 emsdk，这边 **Rust + wasm32-wasip1**）；
集成点在上游层的 `Octave-UI`，中间用 **`.mat` 握手**。

## 地图（真值在哪里）

- **现在是什么**（活状态）：`STATE.md`（正文只写现状、数字一律引用台账键）。
- **测出来的数字**（唯一产地）：`build/FACTS.json`（源）+ `STATE.md` 的 AUTO 块（渲染）。
- **事实系统**：机制 = `zreflect/`（vendored Einfacht）；**本仓数据层** =
  `zreflect/measure_openmodelica.py`。
- **要做什么**（需求单）：`docs/REQUIREMENTS.md`（每条带验收判据）。
- **怎么用这套机制**：`docs/EINFACHT-INTEGRATION.md`（含 7 个实测坑）。
- **怎么搬上游/怎么维护**：`docs/FORK-PIPELINE-AND-LESSONS.md`（fork 管线 + 全部经验）。
- **给 agent 的硬规矩**：`AGENTS.md`。
- **历史**：`HISTORY.md`（append-only）。
- **悬案**：`.scratch/open-questions/issues/NN-*.md`（每条挂可执行结算件）。
- **术语**：`CONTEXT.md`。

## 方向

### ✅ 第一步（需求 A）：**已结案**（2026-10-13）
官方 CMake wasm 目标在本机 build 出了产物，Node 里 `getVersion()` 出串
（判据 = `build/113/build-omc-wasm.sh --verify` rc=0，工单 01 状态 `resolved`）。
**顺带更正了需求书四处原文**（`docs/REQUIREMENTS.md` §7 修正记录）：
上游今天**零 wasm64 支持**（⇒ 首批产物是 **wasm32**，悬案 02 挂可跑结算件）、
产物真名是 `OpenModelicaCompiler_bg.wasm`、一步式配方缺 `RuntimeSources.mo`（⇒ 两步链）、
wasm 路径不需要 OMBootstrapping。
**限制如实记**：`RUST_OMC_WASM_OPT=OFF`（本机 binaryen 与上游旗标不兼容）⇒ 产物未 `-Oz` 优化。

### 第二步：浏览器内跑通一个 Modelica 模型（需求 B）
⚠️ 已知断点（首批实测）：Node 侧编译器**前端全通**（`loadFile` true、
`getClassNames` → `{BouncingBall}`），`simulate()` 停在"要宿主注入 JS 回调"
（`rt_host_lin_solve`）⇒ 这正是第二步要接的胶水。
### 第三步：三线（`master`=wasm64 / `wasm32` / `IllegalPerformance`）+ 架构纯度闸门（需求 C）
⚠️ `master` 线的 wasm64 目标**上游不支持**（悬案 02）；`wasm32` 线首批产物已出。
### 第四步：与 Octave 引擎的 `.mat` 握手（需求 D）+ MATLAB 语义桥 `omc_*`（需求 E）
### 第五步：`Octave-UI` 第二档集成（需求 F）

## 分支模型（三线独立，一线一架构）

    master              → wasm64，只编 wasm64（⚠️ 上游不支持，见悬案 02；暂出 wasm32 产物）
    wasm32              → wasm32，只编 wasm32（首批产物线）
    IllegalPerformance  → 性能线（SIMD / 多线程 / 优化库）

判据 = `build/113/check-lane-purity.py`（宿主 / 附属模块 / 站点本档专属目录三处同档）。
**2026-10-13 加固**：wasm 文件**没有** `Arch:` 头 ⇒ 闸门加 memory64 标志判据；
side module（dylink.0，无 memory 段）改成"必须与宿主同档"+ 报告里记明（20 条自证）。

## 明确不做

- **不做通用块图环境**：MSL `Blocks` 已提供因果块图库、OMEdit 已有 Qt-for-WebAssembly
  图形编辑器（见姊妹仓 `build/113/NOTES-experiment-omc-wasm.md` §9）。
- **不移植 OMMatlab 本体**（ZeroMQ + 本地进程 socket，浏览器没有）。
- **不承诺"任意 Modelica 模型都能跑"**（官方 wasm-jit 求解器覆盖窄）。

## 开工与提交的顺序

见 `AGENTS.md` 的「批次收尾」与「提交前」两节（那是权威形态）。一句话：
**开工预检 → 实验站 → 受管辖入口发运 → 三层 SHA → 全量回归 → 三处一致 → 闸门 → 提交 → 推镜像。**
