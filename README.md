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
**实测证据**（姊妹仓 8761 页面实测）：Octave 能解 **index-1 DAE**（RC 电路 `V(5)=0.9931`
vs 理论 `0.9933`），但**解不了 index-3**（约束摆 `IDASolve failed`）—— 而指标约简
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

## 三条线（一线一架构）

    master              → 产物 wasm64，只编 wasm64
    wasm32              → 产物 wasm32，只编 wasm32
    IllegalPerformance  → 性能线（SIMD / 多线程 / 优化库）

判据 = `python3 build/113/check-lane-purity.py`（宿主 / 模块 / 站点本档专属目录三处同档；
错档逐条点名、rc=1；反向断言：喂错档必须红）。

**All three lines are already in place** (`master` / `wasm32` / `IllegalPerformance`, same baseline commit) — see `git branch -a`.


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
| `docs/LANES-AND-MEMORY-MODEL.md` | **Memory-model & lane experience** (wasm32/wasm64 read-outs, the three real mixing incidents, the purity gate's three criteria, multi-lane sites and lane selection; incl. how the three lines still hold when the upstream has zero wasm64 support) |
| `maintaince.md` | 方向与地图 |
| `STATE.md` | 活状态（+ 文末机器块） |
| `AGENTS.md` | 给 agent 的硬规矩 |
| `CONTEXT.md` | 术语表（每词一条定义 + 一行复跑证据） |
| `HISTORY.md` | 历史（append-only） |

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

⚠️ **wasm64 仍是双缺**：上游 CMake 无路径 **且 Rust 侧没有 `wasm64-unknown-unknown` target**
⇒ 编译器主体编不成 wasm64（姊妹仓的 Emscripten `-sMEMORY64=1` 是 C/C++ 路径，不能照搬）。

**`IllegalPerformance` 线已开工**（2026-10-14）：基线已立（`build/113/ilperf-baseline.sh`）——
产物 74.6 MB、**SIMD 5876 处 + post-MVP 23,451 处已在产物里**、features 九项、memory 导出形态。
**★ wasm64 工具链侧可做**（同日实测更正）：`cargo build --target wasm64-unknown-unknown
-Zbuild-std=core,alloc` **8.8 秒编成**（可行件 `build/113/build-w64-spike.sh`，5 条自证），
纯度闸门认档 wasm64、反向断言正确红。⚠️ **缺的只是上游 CMake 路径**
（`rust_omc.cmake` 0 命中 wasm64）——"上游还没接进构建系统"，**不是"编不出来"**。
线内**不动默认线**；性能候选按"A/B 差分门 + 负判决也是资产"推进。

**下一步 = 需求 F**（`Octave-UI` 集成）/ 性能候选逐条验。

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
- `.githooks/check-state.py` (13270 bytes)
- `.githooks/check-wants.py` (10926 bytes)
- `.githooks/check-whitelist.py` (3216 bytes)
- `.githooks/state_facts.py` (11428 bytes)
- `.githooks/update-readme.py` (2270 bytes)
- `.githooks/update-state.py` (5884 bytes)
- `.githooks/witness-upstream-pin.py` (15708 bytes)
- `.gitignore` (4916 bytes)
- `.gitmodules` (122 bytes)
- `.scratch/open-questions/issues/01-omc-wasm-buildable.md` (3536 bytes)
- `.scratch/open-questions/issues/02-wasm64-unsupported.md` (3818 bytes)
- `.scratch/open-questions/issues/03-simulate-needs-host-solver.md` (6171 bytes)
- `.scratch/open-questions/issues/04-samepage-memory-cost.md` (3105 bytes)
- `AGENTS.md` (8090 bytes)
- `CONTEXT.md` (6458 bytes)
- `HISTORY.md` (38136 bytes)
- `LICENSE` (34523 bytes)
- `README.de.md` (10353 bytes)
- `README.zh.md` (8972 bytes)
- `STATE.md` (23072 bytes)
- `THIRD-PARTY-NOTICES.md` (2149 bytes)
- `bridge/omc_bridge.js` (7217 bytes)
- `bridge/omc_call_internal.m` (3755 bytes)
- `bridge/omc_collect.m` (1128 bytes)
- `bridge/omc_fs_read.m` (1441 bytes)
- `bridge/omc_fs_write.m` (485 bytes)
- `bridge/omc_fs_write_b64.m` (455 bytes)
- `bridge/omc_getVersion.m` (1752 bytes)
- `bridge/omc_mat_load.m` (7687 bytes)
- `bridge/omc_simulate.m` (2678 bytes)
- `bridge/omc_simulate_async.m` (1229 bytes)
- `bridge/omc_simulate_model.m` (1790 bytes)
- `bridge/omc_submit.m` (1492 bytes)
- `build/113/build-clang24-builtins.sh` (6408 bytes)
- `build/113/build-omc-wasm.sh` (23539 bytes)
- `build/113/build-w64-spike.sh` (7866 bytes)
- `build/113/check-lane-purity.py` (20889 bytes)
- `build/113/check-wasm64-upstream.sh` (4054 bytes)
- `build/113/gen-runtime-sources-mo.sh` (7744 bytes)
- `build/113/ilperf-baseline.sh` (5003 bytes)
- `build/113/measure-samepage-cost.sh` (8980 bytes)
- `build/113/provision-toolchain.sh` (13684 bytes)
- `build/FACTS.json` (10079 bytes)
- `build/gates-selftest.sh` (3859 bytes)
- `build/lib/gate.py` (7246 bytes)
- `build/pins.json` (971 bytes)
- `build/promote-site.sh` (6134 bytes)
- `build/provision-upstream.sh` (5930 bytes)
- `build/retractions.json` (1704 bytes)
- `build/serve-coi.py` (3033 bytes)
- `build/upstream-lock.json` (2909 bytes)
- `build/upstream-pins.json` (2957 bytes)
- `docs/EINFACHT-INTEGRATION.md` (9200 bytes)
- `docs/FORK-PIPELINE-AND-LESSONS.md` (10802 bytes)
- `docs/LANES-AND-MEMORY-MODEL.md` (7638 bytes)
- `docs/REQUIREMENTS.md` (21499 bytes)
- `docs/agents/domain.md` (3359 bytes)
- `docs/agents/fact-system.md` (14131 bytes)
- `docs/agents/issue-tracker.md` (3217 bytes)
- `docs/agents/memory.md` (3919 bytes)
- `docs/agents/triage-labels.md` (1606 bytes)
- `docs/agents/upstream-issues.md` (12882 bytes)
- `doctor.json` (645 bytes)
- `gates-selftest.sh` (13572 bytes)
- `maintaince.md` (6300 bytes)
- `reflect-hooks/Einfacht.env` (1995 bytes)
- `reflect-hooks/Einfacht.env.example` (1606 bytes)
- `reflect-hooks/einfacht-env.sh` (4231 bytes)
- `reflect-hooks/install.sh` (575 bytes)
- `reflect-hooks/pre-commit` (4531 bytes)
- `reflect-hooks/pre-push` (3790 bytes)
- `site/omc-bridge.html` (5956 bytes)
- `site/samepage.html` (14655 bytes)
- `test/browser/accept-mat-handshake.mjs` (9671 bytes)
- `test/browser/accept-omc-bridge.mjs` (18075 bytes)
- `test/browser/accept-omc-page.mjs` (5493 bytes)
- `test/browser/accept-samepage.mjs` (6594 bytes)
- `test/browser/run-mat-handshake.sh` (2414 bytes)
- `test/browser/run-omc-bridge.sh` (1146 bytes)
- `test/browser/run-omc-page.sh` (1175 bytes)
- `test/browser/run-samepage.sh` (1104 bytes)
- `test/browser/selftest-mat-bridge.sh` (7210 bytes)
- `test/node/accept-omc-getversion.mjs` (4653 bytes)
- `test/node/accept-omc-simulate.mjs` (7828 bytes)
- `test/node/manifest.json` (1279 bytes)
- `test/node/produce-result-mat.mjs` (3803 bytes)
- `test/node/run.sh` (1019 bytes)
- `upstream/openmodelica` (4096 bytes)
- `zreflect/__init__.py` (112 bytes)
- `zreflect/check_ab.py` (8423 bytes)
- `zreflect/check_envfile.py` (15627 bytes)
- `zreflect/check_facts.py` (7705 bytes)
- `zreflect/check_facts_replay.py` (17601 bytes)
- `zreflect/check_instruments.py` (9383 bytes)
- `zreflect/check_invariants.py` (9065 bytes)
- `zreflect/check_locks.py` (9114 bytes)
- `zreflect/check_pins.py` (10754 bytes)
- `zreflect/check_questions.py` (8019 bytes)
- `zreflect/check_readme_sync.py` (9862 bytes)
- `zreflect/check_retractions.py` (6211 bytes)
- `zreflect/check_stale.py` (12272 bytes)
- `zreflect/check_world.py` (17168 bytes)
- `zreflect/collect.py` (5329 bytes)
- `zreflect/doctor.json.example` (1242 bytes)
- `zreflect/doctor.py` (15657 bytes)
- `zreflect/facts.py` (19991 bytes)
- `zreflect/gate.py` (10914 bytes)
- `zreflect/guard.py` (9208 bytes)
- `zreflect/knobs.py` (13858 bytes)
- `zreflect/ledger.py` (11552 bytes)
- `zreflect/living.py` (3688 bytes)
- `zreflect/measure_openmodelica.py` (17877 bytes)
- `zreflect/registry.py` (26659 bytes)
- `zreflect/render.py` (6408 bytes)
- `zreflect/runner.py` (5210 bytes)
<!-- /AUTO -->
