# OpenModelica-Full-Wasm

[English](README.md) · [中文](README.zh.md) · [Deutsch](README.de.md)

**OpenModelica**（Modelica 编译器 + 仿真运行时）→ **WebAssembly**，跑在浏览器里，
**纯客户端计算、无服务端执行端点**。

> 🔒 本仓是 **private**。姊妹仓 [`Octave-Full-Wasm`](https://github.com/ArchivalEra/Octave-Full-Wasm)
> 是**平级**的另一半（那个跑 MATLAB 语法那一侧）。

---

## 为什么有这个仓（一句话）

MATLAB 生态有**三根轴**：

| 轴 | 是什么 | 谁覆盖 |
|---|---|---|
| ① | MATLAB **语言**（`.m` / 矩阵语义） | `Octave-Full-Wasm` |
| ② | **Simulink**（因果块图） | `Octave-Full-Wasm` 引擎 + 一个 JS 前端 |
| ③ | **Simscape**（**非因果物理建模**：电/流体/热/机械…） | **本仓** |

第 ③ 轴姊妹仓**天然给不了**：Octave 是数值/命令式语言，没有"符号化 + 指标约简 + DAE"那套机器。
**实测证据**（姊妹仓 8761 页面实测）：Octave 能解 **index-1 DAE**（RC 电路 `V(5)=0.9931`，
理论 `0.9933`），但**解不了 index-3**（约束摆 `IDASolve failed`）—— 而指标约简
**正是 OpenModelica 编译器的核心工作**。两个引擎是**接力**，不是重复。

## 两个引擎怎么配合（同一个 `.mat` 通道）

```
OpenModelica 档：方程级物理建模（符号化 + 指标约简 + MSL 物理库）
                        │  仿真
                        ▼
                 xxx_res.mat（MAT4）
                        │
Octave 档：load → 数值求解 + 控制/信号/统计 + 矩阵语言 → 画图/分析
```

这与 MATLAB 里 **"Simscape 建模、MATLAB 分析"** 是**同一个分工**，只是用两个 wasm 引擎实现，
中间用 `.mat` 而不是共享内存。`.mat` 握手**两边现成都有的东西**（OM 仿真输出就是 MAT4；
Octave 读写 `.mat` 实测全通）。

## 走官方路线（不是第三方配方）

OpenModelica **官方主仓**有第一方 wasm 构建目标（`OMCompiler/Compiler/.cmake/rust_omc.cmake`）：
`RUST_OMC_WASM_RUNTIME`、`wasm32-wasip1` 交叉编、`omc.wasm`、产物交接、`wasm-jit` 运行时。
⇒ **本仓照这条走** —— 也就是"上游 submodule + 自己交叉编 + 同源托管"，
**与 `Octave-Full-Wasm` 是同一种仓库**（区别只在工具链：本仓 **Rust + wasm32-wasip1**）。

## 两条线（一线一架构）

    master              → 产物 wasm64，只编 wasm64（⚠️ 上游未接路径，暂出 wasm32 产物）
    wasm32              → 产物 wasm32，只编 wasm32

判据 = `python3 build/113/check-lane-purity.py`（宿主 / 模块 / 站点本档专属目录三处同档；
错档逐条点名、rc=1；反向断言：喂错档必须红）。

**★ 性能线 `IllegalPerformance` 已按用户点令删除**（2026-10-14，本地 + 远端）：它**只有
wasm64 按官方 fork 管线做到生产级之后**才是"脱离官方树的开发"，在那之前开线没有用 ⇒
本仓当前**两线**；wasm64 生产级后**重建**该线。原线对象**不删**（本仓铁律），
钉在 tag `archive/ilperf-f283610`。

**两条线已在位**（`master` / `wasm32`），且**内容已同步** ——
`git diff master <线> --stat` 应为空（`wasm32` 与 master **同一提交**）。

**★ 当前发布 = 仅 wasm32 线一个版本**（2026-10-17）：`v0.1.0-wasm32`（codename first-light）
—— 版本身份证 `build/VERSION.json`、发布说明 `docs/RELEASE-v0.1.0-wasm32.md`、
git tag `v0.1.0-wasm32`。master 线**当前适用档 = wasm32**（wasm64/多线程卡上游，
悬案 02，上游接路径即翻面）。


## 事实系统（Einfacht，反幻觉）

**★ 一条实战教训（2026-10-14，被复跑闸门抓到）**：**波动的观测量不能以原值进台账**。
JS 堆峰值、编译耗时这类"每轮都变"的量，放进台账必然让复跑闸门红（那不是产物问题，
是**判据与量的性质不匹配**）⇒ 本仓改成**量级档**（堆峰值取整到 5 MiB、编译耗时取整到 **500ms**，
`cmd` 里做同样的取整，⇒ 逐字复跑稳定）。
**第 2 课：档要粗于噪声** —— 100ms 档实测仍会翻（295→300 vs 306→400），档位跨过噪声才有意义。


数字的**唯一产地**是 `build/FACTS.json`；文档正文**不手抄数字**，写 `[[键名]]`；
每条事实旁写**复跑命令**，闸门每次提交逐字执行。每个闸门必须**能证明自己会红**
（`sh gates-selftest.sh`）。

## 文档地图

| 文件 | 内容 |
|---|---|
| `docs/REQUIREMENTS.md` | **需求书**：要做什么，每条带实测现状 + 验收判据 |
| `docs/EINFACHT-INTEGRATION.md` | **Einfacht 接入方法**（含 7 个实测坑） |
| `docs/FORK-PIPELINE-AND-LESSONS.md` | **fork 管线 + 全部经验**（怎么搬上游、怎么维护） |
| `docs/LANES-AND-MEMORY-MODEL.md` | **内存架构与分支线经验**（wasm32/wasm64 两档判据、三次混编事故的真实报错、架构纯度闸门三判据、多档站点与择档；含『上游零 wasm64 支持』下一线一架构照样成立的处理）|
| `maintaince.md` | 方向与地图 |
| `STATE.md` | 活状态（+ 文末机器块） |
| `AGENTS.md` | 给 agent 的硬规矩 |
| `CONTEXT.md` | 术语表（每词一条定义 + 一行复跑证据） |
| `HISTORY.md` | 历史（append-only） |
| `mail/` | 跨 agent 通信收件箱（只追加）：其他仓写给本仓的信 + 本仓对外往来；规矩见 `mail/README.md`。端口往来：`001`（额外内容仓推广 content-list）+ `002`（本仓回：暂无内容可报、缺席是合法行为）+ `003`（额外内容仓确认）+ `004`（产地已裁决：`consumer` 轴采纳、能力层 `content` 留空）+ `005`（产地第二批答复：无直接影响） |

## 现行状态

**★ 需求 A 已结案**（2026-10-13）：官方 wasm 目标** build 出了产物，且 Node 里跑得动** ——
产物 `OpenModelicaCompiler_bg.wasm`（`omc.build.json` **verdict=ok**），
`node omc-cli.js 'getVersion()'` 出串。工具链 = **clang 24** + 同源精编 wasm32 builtins
+ Rust `nightly-2026-05-31`；构建路径 = 宿主直跑（本机 docker 不可用）。
**上游 pin**：`upstream/openmodelica` = `cbff5eb7…`、`OMCompiler/3rdParty` = `ae7e482a…`。

**还没做的**（别混）：浏览器端到端跑模型（需求 B）与 `.mat` 握手（需求 D）。
**需求 B 已结案**（2026-10-14）：模型在 wasm 里**跑完**并产出 **MAT4** 结果文件
（`LOG_SUCCESS | The initialization finished successfully`），`h` 的 500 点曲线
是真物理（从 1.0 衰减 + 弹跳）。判据：`node test/node/accept-omc-simulate.mjs`
→ **10 PASS / 0 FAIL**（含反向用例）。根因与修补全过程见
`.scratch/open-questions/issues/03-simulate-needs-host-solver.md`（`resolved`）。

**需求 D 已结案**（2026-10-14）：`.mat` 握手打通 —— OM 仿真结果喂进 **Octave 引擎**
（真浏览器、8761 站点）读出变量且数值合理；判据 `sh test/browser/run-mat-handshake.sh`
→ **14 PASS / 0 FAIL**（含 D3 反向断言；"数值合理"是对**解析解**的 4 条硬判据，
不是"看着差不多"）。对姊妹仓**零写入**（只借它的 harness 与只读站点）。
握手点是**语义映射**而非 `load`：
Octave 的 `load` 认 MAT4 格式但不产生 `h`/`v`（变量名在 `name` 矩阵的列里）⇒
本仓 `bridge/omc_mat_load.m` 补这一层。**D4 同页成本实测 = 当前不可行**
（OM 91.2MB 模块一编译整页崩），悬案 04 交决策。

**需求 B 已结案**（2026-10-14）：页面内 `loadFile` + `simulate` 出 **MAT4**
（web 档产物 + 本仓站点；判据 `sh test/browser/run-omc-page.sh` → **10 PASS / 0 FAIL**）。
**需求 E 已结案**：`omc_simulate_model('BouncingBall')` 在**真 Octave 引擎**里返回
**628×7 数据矩阵**（判据 `sh test/browser/run-omc-bridge.sh` → **11 PASS / 0 FAIL**）。
桥是**两段式**（`.m` 提交即返回、宿主驱动）—— `.m` 侧忙等会与宿主互等死锁（实测）。

**★ 同页已实现**（2026-10-14，wasm32）：两个引擎在**同一页面**跑通，页内完成 `.mat` 握手
（判据 `sh test/browser/run-samepage.sh` → **8 PASS / 0 FAIL**）。**产物已压缩**：
`-Oz` 把 web 档 omc **91.4 MB → 74.6 MB（−18.4%）**，验收仍全绿。
（早先"同页不可行"的结论已**翻案**：那是测量方法的错，见 `build/retractions.json`。）

⚠️ **wasm64 的边界**（2026-10-14 更正，见 `build/retractions.json` 的 `R-02-1`）：
**工具链侧可做** —— `cargo build --target wasm64-unknown-unknown -Zbuild-std=core,alloc`
**8.8 秒编成**（可行件 `build/113/build-w64-spike.sh`，5 条自证），纯度闸门认档 wasm64、
反向断言正确红；⚠️ **缺的只是上游 CMake 路径**（`rust_omc.cmake` 0 命中 wasm64）
——"上游还没接进构建系统"，**不是"编不出来"**。

**★ 性能线 `IllegalPerformance` 已按用户点令删除**（2026-10-14）：它**只有 wasm64 按官方
fork 管线做到生产级之后**才是"脱离官方树的开发"，在那之前开线没有用 ⇒ 本仓回到两线；
wasm64 生产级后**重建**该线。**wasm64 工具链侧可做**这条事实保留（它是重建的前置）。
（基线件 `build/113/ilperf-baseline.sh` 与可行件 `build/113/build-w64-spike.sh` 仍在仓里 ——
前者量到的 SIMD/post-MVP 指令面是**当前产物**的事实，后者是**重建该线**的可行性前置。）

**下一步 = 需求 F**（`Octave-UI` 集成）。

### 两条线的验收状态（2026-10-15 实测）

- **wasm32 线：不需要 COI（实测）** —— 产物 0 原子指令 / 0 线程导入 / 0 共享 memory
  （台账 `omc_web_atomic_ops` = 0）；用**普通 http.server（零 COI 头）**服务站点，
  浏览器验收**全绿**（omc-page 10/0、samepage 8/0；另两套 14/0、11/0）。
  站点纯度：宿主 + 13 附属模块全 wasm32（台账 `site_wasm32_mods`）。
  如实记：无 COI 时 cancel-poll / progress-sink / FMU-AOT 三个增强面降级（SAB 控制块）。
- **master 线：wasm64 与多线程都卡上游（查实）** —— wasm64 结算件 NOT-YET（悬案 02）；
  上游 wasm 面无运行期线程路径（`RUST_OMC_THREADS` 是编译期并行；无 rayon/wasi-threads；
  coi_server 说的 "threaded builds" 指 Qt 前端）⇒ master 线暂出 wasm32 产物，
  两个目标都在等上游接路径。

⚠️ **需求书原文被实测推翻四处**（记在 `docs/REQUIREMENTS.md` §7，不静默改原文）：
`master` 线要的 **wasm64 上游零支持** ⇒ 首批产物出 **wasm32**；产物真名是
**`OpenModelicaCompiler_bg.wasm`**（不是 `omc.wasm`）；一步式配方缺
`RuntimeSources.mo` ⇒ 走两步链；wasm 路径不需要 OMBootstrapping。

## 许可

**AGPL-3.0-or-later**（见 `LICENSE`）。
上游 OpenModelica 是 **AGPLv3 / OSMC-PL 双选** —— 与本仓兼容。
上游第三方库各自许可见 `THIRD-PARTY-NOTICES.md`。

## 文件清单（自动）

<!-- AUTO:FILES -->
<!-- /AUTO -->
