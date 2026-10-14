# 需求书 · OpenModelica-Full-Wasm（2026-10-13）

> **性质**：需求书（不是实现、不是设计稿）。每条需求带**实测现状**与**可复跑的验收判据**；
> 写不出验收判据的条目不进本单（本仓事实纪律）。
> **读者**：不需要本仓上下文——每条自带背景。

---

## §0 这个仓要干什么

**在浏览器里跑 OpenModelica**（Modelica 编译器 + 仿真运行时），纯客户端、零服务端，
作为 `Octave-Full-Wasm`（MATLAB 语言那一侧）**平级的第二个引擎**。

**为什么需要它**（一句话）：MATLAB 生态有三根轴 —— **① 语言**（Octave 已覆盖）、
**② Simulink 因果块图**、**③ Simscape 非因果物理建模**。第 ③ 轴本仓零覆盖，而
OpenModelica 是那块的现实解（它自带跨域物理库 MSL，且有**官方 wasm 构建目标**）。

**两个引擎的分工**（不是重复，是接力）：
```
OM 档：方程级物理建模（符号化 + 指标约简 + MSL）→ 仿真 → .mat
                                                      ↓
Octave 档：读 .mat → 数值求解 + 控制/信号/统计 + 矩阵语言 → 分析/画图
```
这与 MATLAB 里 "Simscape 建模、MATLAB 分析" 是**同一个分工**，只是用两个 wasm 引擎实现，
中间用 `.mat` 握手。

---

## §1 现状（全部实测，复跑方式见 §6）

### 1.1 可行性：**已证**（第三方演示实测，2026-10-13）

真浏览器里，`EthanJamesLew/omc-web` 的在线演示把 `BouncingBall.mo` 跑通全链路：

| 阶段 | 耗时 | 产物 | 大小 |
|---|---|---|---|
| parse modelica | 381 ms | `BouncingBall.mo` | 425 B |
| generate C | 28 ms | `BouncingBall_c.zip` | 57.7 KB |
| **compile to wasm** | **49.57 s** | `BouncingBall.wasm` | **1.18 MB** |
| simulate | 50 ms | `BouncingBall_res.mat` | 14.3 KB |

4/4 complete，350 samples / 13 events / 3 vars，出三条真曲线。
**证据**：`docs/evidence/omc-web-demo.png`（在 `Octave-Full-Wasm` 仓里，
路径 `build/113/evidence-omc-web-demo.png`）。

⚠️ 那条是**第三方路线**（浏览器内再跑一次 clang，用 emception）。**官方路线见 1.2。**

### 1.2 官方路线：**存在，且是 CMake 原生**（本仓要走的路）

OpenModelica 官方主仓的 `OMCompiler/Compiler/.cmake/rust_omc.cmake`（2313 行）里：

| 事实 | 证据 |
|---|---|
| 官方有 wasm 构建目标 | `RUST_OMC_WASM_RUNTIME`（13 处）、`omc.wasm`、`RUST_OMC_WASM_ARTIFACTS_OUT` / `RUST_OMC_PREBUILT_WASM_DIR`（产物交接） |
| WASI 交叉编是一等公民 | `wasm32-wasip1` **27 处**；写 `CMAKE_C_COMPILER_TARGET wasm32-wasip1` 工具链文件 |
| 求解器也交叉编 | `option(RUST_OMC_ENABLE_SUNDIALS "...for wasm32-wasip1")`（SUNDIALS/KLU/UMFPACK/Lis） |
| wasm-jit 运行时 | `wasm32-unknown-unknown` + `openmodelica_codegen_wasm_jit_runtime.wasm` |
| 注释明说需要 | "clang + wasi-libc + wasm-ld" |
| 官方 wasm 页面在树里 | `wasm/{index.html, omc-cli.js, omc-terminal/, simulator/, fmi-simulator/, omplot/, anim/}` |

⇒ **本仓走官方 CMake 目标**（照本仓"来时路"：上游 submodule + 自己交叉编 + 同源托管），
**不抄第三方 emception 配方**。

### 1.3 与 Octave 引擎的互补性（实测，决定"同页"成立）

| DAE 类型 | 例子 | Octave 引擎实测 |
|---|---|---|
| index-1（Mass 矩阵） | `ode15s` + `odeset('Mass',M)` | **✓** |
| index-1（全隐式） | `ode15i`：RC 电路 | **✓ V(5)=0.9931**（理论 0.9933） |
| index-1（多节点） | `ode15i`：双节点 RC 网络 | **✓ V2(5)=0.9593** |
| **index-3（约束系统）** | `ode15i`：约束摆 | **✗ `IDASolve failed`** |

index-3 → index-1 的**指标约简是符号处理**（Pantelides），**正是 OM 编译器的核心工作**
⇒ 两引擎互补，不是重复。

### 1.4 交换格式：`.mat`（两边现成）

- Octave 引擎能读写 `.mat`（`-v7` / `-v4` / 默认，实测全通）；
- omc-web 的仿真输出就是 `.mat`（"dump MAT4 trace"）。
⇒ **一次 `.mat` 握手** = 语义互通。

### 1.5 上游脚本协议：`sendExpression` ↔ `omc_eval`（MATLAB 语义桥已存在）

- 官方 `OpenModelica/OMMatlab`（MATLAB 客户端）用 `omc.sendExpression(src)` 经 **ZeroMQ**
  连本地 omc 进程；
- **浏览器官方 OM wasm 暴露同一族命令**：`omc_eval(src)`（实测 `omc-cli.js` 的导出面：
  `omc_init` / `omc_eval` / `omc_set_env` / `omc_enable_wasm_blobs` / `omc_take_pending_downloads`）。

⇒ **同一协议，两个传输层**。要做的是 Octave 侧的 `omc_*` 桥函数族（拼脚本 → 调 `omc_eval`
→ 读回 `.mat`）。⚠️ **不移植 OMMatlab 本体**（它要本地进程 socket，浏览器没有）。
⚠️ `sendExpression` **不是** MATLAB 语言翻译器（是命令字符串，不是把 `.m` 变 `.mo`）。

---

## §2 需求（按"能不能上"排序，每条带验收判据）

### 需求 A · 官方 wasm 目标构建出 `omc.wasm`（**第一步，唯一真未知**）

**A1 工具链**：Rust + `wasm32-wasip1` target + wasi-libc + wasm-ld（官方 CMake 注释明说）。
**A2 构建**：照 `rust_omc.cmake` 的 `RUST_OMC_WASM_RUNTIME` 目标，产出 `omc.wasm`。
**A3 验收**：产物存在且能在 Node 里 `omc_eval('getVersion()')` 返回版本串。
**A4 反向断言**：坏产物（缺 wasi sysroot / 缺 sundials-wasm）**必须**在构建期报错，
不许产出静默可加载但运行期炸的件。

### 需求 B · 浏览器内跑通一个 Modelica 模型（端到端）

**B1** 页面里 `omc_eval('loadFile("BouncingBall.mo"); simulate(BouncingBall)')` 产出 `.mat`。
**B2 验收**：`.mat` 文件头正确（MAT4 魔数）、变量数/采样数与参考一致。
**B3 反向断言**：语法错误的 `.mo` ⇒ `getErrorString()` 给出可读错误（不许静默）。

**★ 2026-10-14 已结案**：`sh test/browser/run-omc-page.sh` → **10 PASS / 0 FAIL**。
用的是 **web 档产物**（`MODE=web-release` 构建，与 node 档是两个独立构建）+ 本仓站点
（`build/promote-site.sh` 发布、`build/serve-coi.py` 带头服务）。
实测：页面内 `loadFile → true`、`simulate` 出 MAT4（字节级解析：6 矩阵、`data_2` = 5×628、
`name` = 7 列）；B3 反向给出带定位的可读错误。⚠️ 一条实测坑记在 §7 R7（web 档的导出形状）。

### 需求 C · 三线（wasm32 / wasm64 / IllegalPerformance）

> ⚠️ **2026-10-14 用户点令：性能线 `IllegalPerformance` 删除**（本地 + 远端）⇒ 本需求**现为两线**。
> 理由（用户原话）：IP 线**只有 wasm64 目标按官方 fork 管线做到生产级之后**才是"脱离官方树的
> 开发"；在那之前开线做出来的东西**没有用**。⇒ wasm64 生产级后**重建**该线（不续用旧线）；
> 原线对象**不删**，钉在 tag `archive/ilperf-f283610`（本仓铁律：不删 git 对象）。
> 下面的 C1 原文保留（它记的是"当初要什么"），**C1 第三条已失效**。

**C1 线划分 = 一线一架构**（沿用 `Octave-Full-Wasm` 的用户点令，2026-10-12）：
- `master` 线 → 产物 **wasm64**，只编 wasm64；⚠️ **2026-10-13 实测：上游不支持**（见 §7 修正记录 R1）；
- `wasm32` 线 → 产物 **wasm32**，只编 wasm32；
- ~~`IllegalPerformance` 线 → 性能线（SIMD / 多线程 / 优化 BLAS 之类）~~ **【2026-10-14 用户点令删除】**。
**C2 判据可执行**：照 `Octave-Full-Wasm/build/113/check-lane-purity.py` 的形状写本仓的
**架构纯度闸门**（宿主 / `.oct` 等价物 / 站点本档专属目录三处同档；错档逐条点名、rc=1）。
**C3 反向断言**：喂错档产物 ⇒ **必须红**。

### 需求 D · 与 Octave 引擎的 `.mat` 握手（同页集成）

**D1** OM 档产出 `.mat` ⇒ Octave 档 `load` 进来做后处理（画图 / 控制设计 / 统计）。
**D2 验收**：端到端 —— OM 的 `BouncingBall_res.mat` 喂进 Octave，`load` 成功且数值合理。
**D3 反向断言**：非 `.mat` 文件喂进去 ⇒ Octave 明确报错（不许静默）。
**D4（2026-10-14 已测，结论见 §7 R6 与悬案 04）**：两引擎**同页**的成本 ——
OM 产物 **91.2 MB** + Octave **29.6 MB**（wasm 合计 **120.8 MB**）；
分步实例化时 Octave 模块可编（堆 81.4 MB），**OM 模块一编译整页就崩**
（`Target page: closed`）⇒ **当前不可行**，方向（惰性/缩产物/分 Worker）留给决策。

### 需求 E · MATLAB 语义桥（`omc_*` 函数族）

**E1** Octave 侧实现 `omc_load` / `omc_simulate` / `omc_getVersion` 之类，内部拼 OM 脚本、
调 `omc_eval`、读回 `.mat`。
**E2 验收**：在 Octave 里 `omc_simulate('BouncingBall')` ⇒ 返回数据矩阵。
**E3 边界**：只做"命令驱动"，**不做**"`.m` 自动翻译成 Modelica"（那需要符号翻译，不在本单）。

**★ 2026-10-14 已结案**：`sh test/browser/run-omc-bridge.sh` → **11 PASS / 0 FAIL**（在**真
Octave 引擎**里跑）。实测：`omc_simulate_model('BouncingBall', 'stopTime', 3.0)` ⇒
**628×7 数据矩阵**（max h=1.0000 / min<0 / 末 −0.9556）；未知模型与未支持命令**都明确报错**。
⚠️ 形态与需求书原文的差异（三条，都是实测逼出来的）记在 §7 R8：桥是**两段式**
（`.m` 提交即返回、宿主驱动），因为 `.m` 侧忙等会与宿主**互等死锁**。
实现件：`bridge/{omc_submit,omc_collect,omc_simulate_model,omc_mat_load,omc_fs_read,omc_fs_write}.m`
+ `bridge/omc_bridge.js`（宿主侧）。

### 需求 F · 与 `Octave-UI` 的集成（第二档）

**F1** OM 作为**与 Octave 平级的第二个引擎档**（**不是** UI 的 `PluginRegistry` 插件）。
**F2 集成点在 UI 层**（`.mat` 握手在 UI 编排），**Octave-Full-Wasm 仓保持绝对只读**。
**F3 供货方式**：产物**同源托管**（COEP `require-corp` 拦跨域，与 Forge 包同族约束）。

---

## §3 明确不做（本单范围外）

- **不做通用块图环境**：MSL `Blocks` 已提供因果块图库、OMEdit 已有 Qt-for-WebAssembly
  图形编辑器 ⇒ 自研是重复造轮子（见 `Octave-Full-Wasm` 的 `NOTES-experiment-omc-wasm.md` §9）。
- **不移植 OMMatlab 本体**（ZeroMQ + 本地进程 socket，浏览器没有）。
- **不做"任意 Modelica 模型都能跑"的承诺**：官方 wasm-jit 求解器覆盖窄
  （README 原文："only 1 dense linear solver, a Newton non-linear solver, Euler, and dassl"）。
- **不引入服务端**（纯客户端铁律）。

---

## §4 上游 pin 形状（紧贴 fork 管线）

| 件 | 形状 | 载体 |
|---|---|---|
| OpenModelica 主仓 | git submodule，钉 nightly SHA | `build/upstream-pins.json` |
| OMCompiler-3rdParty | 同上（与 OM SHA **同动**） | 同上 |
| OMBootstrapping（预生成 MetaModelica→C） | 同上（必须与 OM SHA 同动） | 同上 |
| Modelica 标准库（MSL） | 版本 + sha256 | `build/upstream-lock.json` |
| wasi-libc / wasm-ld 工具链 | 版本断言 | 同上 |

**见证**：`witness-upstream-pin.py` 每提交核"容器/工作树 == pin"，漂移即红。
**双重对账**：产物自证（`omc.build.json`，只记量到的事实）+ 台账 `FACTS.json`。

---

## §5 与 `Octave-Full-Wasm` 的关系（**别混**）

| | Octave-Full-Wasm | OpenModelica-Full-Wasm（本仓） |
|---|---|---|
| 语言 | Octave（= MATLAB 语法） | Modelica（**另一门语言**） |
| 角色 | 轴 ① + ② 的引擎 | 轴 ③（非因果物理建模）的引擎 |
| 工具链 | **emsdk 6.0.12** | **Rust + wasm32-wasip1**（官方 CMake） |
| 许可 | GPL/AGPL 重 | **AGPLv3 / OSMC-PL 双选** |
| 关系 | **平级，互不引用**（集成点在上游层的 `Octave-UI`） | 同左 |

⚠️ **两仓不互相 submodule**：工具链不同（emsdk vs Rust/wasi），混编是本仓明文禁止的失败模式。

---

## §6 复跑命令（本单每个数字的出处）

```bash
# 官方 wasm 目标
gh api "repos/OpenModelica/OpenModelica/contents/OMCompiler/Compiler/.cmake/rust_omc.cmake" \
  --jq .content | base64 -d | grep -nE 'RUST_OMC_WASM|wasm32-wasip1|omc\.wasm|wasm-jit' | head -30
# 官方 wasm 页面
gh api "repos/OpenModelica/OpenModelica/contents/OMCompiler/Compiler/OpenModelica.rs/wasm" --jq '.[].name'
# OMMatlab 接口
gh api "repos/OpenModelica/OMMatlab/contents/README.md" --jq .content | base64 -d | head -40
# MSL 的物理域
gh api "repos/modelica/ModelicaStandardLibrary/contents/Modelica" --jq '.[]|select(.type=="dir")|.name'
# Octave 侧的 DAE 互补性 / .mat 互通：见 Octave-Full-Wasm 的
#   build/113/NOTES-experiment-omc-wasm.md §8（逐条实测）
```

---

## §7 修正记录（实测推翻**需求书原文**的地方，append-only）

> 为什么有这一节：需求书 §1 的 1.2 引用的是**侦察性查证**（读上游文档/CMake）；真正上手构建时
> 会撞上文档里没写的东西。**改需求书原文会掩盖"我们曾经这么以为"**，所以只在此追加。

### R7（2026-10-14）· wasm64 的**真实边界**：工具链可做、上游未接（更正 R1 的框法）

- **R1 说"上游零支持"**——那条成立于"上游构建系统"这一面（`rust_omc.cmake` 0 命中 wasm64），
  但**不能推出"编不出来"**。实测（`build/113/build-w64-spike.sh`，5 条自证）：
  Rust 侧 **`wasm64-unknown-unknown` 在编译器内置目标表里**（`rustc --print target-list`），
  `-Zbuild-std=core,alloc` **8.8 秒**就能编出 wasm64；Node 实例化成功（BigInt 参数是 64 位特征）；
  本仓纯度闸门认档 wasm64 且反向断言正确。
- **⇒ 边界应表述为**："工具链侧可行；**上游 CMake 尚未提供 wasm64 路径**"
  ⇒ wasm64 工作 = **等上游接路径**（或本仓自建一条路径，另立工单）。
  ⚠️ **2026-10-14 用户点令**：承接 wasm64 的那条线（原 `IllegalPerformance`）**已删** ——
  wasm64 按官方 fork 管线做到生产级后**重建**该线；本 R7 记的"工具链侧可做"这条事实**保留**，
  它是"重建该线"的前置。

### R1（2026-10-13）· C1 的「master 线 → wasm64」今天不可达：**上游零支持**

- **原文**：C1「`master` 线 → 产物 wasm64，只编 wasm64」。
- **实测**：上游 `OMCompiler/Compiler/.cmake/rust_omc.cmake`（2312 行）grep `wasm64` = **0 命中**
  （同期 `wasm` 469 命中）；全仓 code search `wasm64 repo:OpenModelica/OpenModelica` = **0**；
  `memory64` 5 处命中**全是 `memory64: false`** 的显式关闭；上游 `rust-toolchain.toml` targets
  只有 `wasm32-unknown-unknown` + `wasm32-wasip1`。
- **旁证（不是我们不行）**：本仓 clang 24 实测 `--target=wasm64-unknown-unknown -c` **通过**
  ⇒ 工具链能编，缺的是**上游的 CMake 目标与 Rust target 面**。
- **处置**：master 线暂出 **wasm32** 产物（官方唯一支持档）；C1 原文保留 + 就地标注；
  悬案 `.scratch/open-questions/issues/02-wasm64-unsupported.md`（结算件
  `build/113/check-wasm64-upstream.sh`，上游加支持即翻面成 rc=0）。
- **复跑**：`bash build/113/check-wasm64-upstream.sh` → 现在 `NOT-YET: …（0 处命中）` rc=1。

### R2（2026-10-13）· 产物真名不是 `omc.wasm`，是 `OpenModelicaCompiler_bg.wasm`

- **原文**：§1.2 表格与需求 A2 写「产出 `omc.wasm`」。
- **实测**：`rust_omc.cmake:1973` `set(_wasm_name OpenModelicaCompiler)`；`:2255-2259` wasm-bindgen
  `--out-dir <web>/pkg-nodejs --target <host>` ⇒ 产物 `OpenModelicaCompiler_bg.wasm` +
  `OpenModelicaCompiler.js`（glue）。`omc.wasm` 在整棵树里**只出现在注释**（4 处）。
- **处置**：事实键与身份证按**真名**记（`omc_build.json.measured.files.omc_bg_wasm`），
  文档写"omc 包（wasm-bindgen 出包）"。**A3 判据不变**：Node 里 `getVersion()` 出串。

### R3（2026-10-13）· 一步式官方配方有隐藏前置：`RuntimeSources.mo` 必须由别处生成

- **原文**：README:358-369 的「Web bundle only」给了一步式命令，读起来是自洽的。
- **实测**：`OM_OMC_WASM=ON` 会跳过**整个** `OMCompiler/SimulationRuntime`（`OMCompiler/CMakeLists.txt:224-226`），
  而 mmtorust 的源表引用 `SimulationRuntime/c/RuntimeSources.mo`（`meta_modelica_source_list.cmake:527`）——
  那个文件由 **SimulationRuntime 的 CMake 生成**（`SimulationRuntime/c/CMakeLists.txt:191-192`），
  且被 gitignore（`OMCompiler/.gitignore:140`）⇒ **clean checkout 的一步式构建缺这个文件**。
  官方 CI 为此专门 `stash 'runtime-sources-mo'` / `unstash`（`.CI/common.groovy:554-556,652`）；
  缺失时 mmtorust **静默跳过**（`mmtorust/src/main.rs:492-520` 记 failures 但不 exit(1)），
  于是产出半缺的 `lib.rs`（`Compiler/CMakeLists.txt:47-52` 有官方描述）。
- **处置**：本仓采用**官方两步链**（stage1 native configure 生成该文件 → stage2 wasm 包），
  见 `build/113/build-omc-wasm.sh` 头注。

### R6（2026-10-14）· ~~同页成本：量的结果就是"不可行"~~ → **★ 已翻案：可行**（同日）

> **翻案（R-R6-1，同日）**：那条"不可行"**是测量方法的错，不是事实**。
> 旧探针把 91MB 模块 **base64 成 ~122MB 的 JS 字符串 + 巨型数组**再 `WebAssembly.compile`
> ⇒ 内存放大把它变成"整页崩"。
> 改用 `WebAssembly.compileStreaming`（引擎直接消化响应体）后实测：
> Octave 29.6MB **92ms** + omc 91.4MB **219ms**，两者在**同一页面**都跑起来，
> **JS 堆峰值 23–28MB**；页内 `.mat` 握手 + 反向断言全过（`sh test/browser/run-samepage.sh`
> → **8 PASS / 0 FAIL**）。⇒ **同页已实现**（`site/samepage.html`）。
>
> 旧结论（保留作教训）：
> - 实测（`build/113/measure-samepage-cost.sh` → `artifacts/samepage-cost.json`）：
>   Octave 模块（29.6 MB）编译成功（710 导出，JS 堆 81.4 MB）；
>   OM 模块（91.2 MB）一 `WebAssembly.compile` 就整页崩（`Target page: closed`）。
> - 三个候选方向里 **"缩产物"仍值得做**（91MB → 更小 ⇒ 加载/编译更快），另两个不再需要。

### R8（2026-10-14）· 需求 E 的形态：桥必须**两段式**（`.m` 侧不许等）

- **原文**（E1）读起来像"`.m` 里调一个函数就拿到结果"（同步风格，像 `OMMatlab.sendExpression`）。
- **实测**：`.m` 侧**不能等**。Octave 的忙等会占住它所在线程，而宿主读写 MEMFS 也要经同一
  上下文 ⇒ **两边互等死锁**（实测 Octave 忙 3s 时宿主 evaluate 被阻塞 **2701ms**；
  现象极具欺骗性：桥的应答文件明明写好了，Octave 却读不到）。
  `pause()` 更糟：本 build 里把整个 evaluate **挂死**（rc=-99）。
- **⇒ 落成两段式**：`.m` 只 `omc_submit()`（提交即返回）→ 宿主把请求转给 omc、写回应答 →
  **宿主再调** `omc_collect(seq)` 取回。任何时刻只有一边在跑。
- **另外三条硬约束**（同族，见 `docs/HISTORY.md` §5.v）：两个 wasm 的 FS **互不可见**（桥要搬字节）；
  Octave 必须跑站点的 **worker 模式**（主线程留给桥）；worker 的 `eval` 返回值**不含结果**，
  取值走 DOM `#output` 通道、大块内容用 base64 分块。

### R7（2026-10-14）· web 档产物的**导出形状**与 node 档不同（需求 B 的坑）

- **原文**（B1）写 `omc_eval(...)`，读起来与 node 档同族。
- **实测**：web 档是 **wasm-bindgen ESM**：`export function omc_eval / omc_set_env / omc_init …`
  是**具名导出**，而 `export { initSync, __wbg_init as default }` —— **default 是"初始化"，
  不是模块对象**。⇒ 必须先 `await mod.default()`，再从**命名空间**取函数。
  （第一版错拿 `mod.default` 当模块对象 ⇒ `omc.omc_set_env is not a function`。）
- **另一条**：web 档**没有** `omc-cli.js`（那是 node 档的 launcher）⇒ `--verify` 必须**档位感知**
  （已改：web 档查 `omc/*.js` + `*_bg.wasm` + `index.html`，不查 CLI）。

### R5（2026-10-14）· 需求 D 的实质：Octave `load` **认格式、不认语义**

- **原文**（D1）：「OM 档产出 `.mat` ⇒ Octave 档 `load` 进来做后处理」——读起来像 `load` 就完事。
- **实测**（真浏览器，2026-10-14）：Octave 的 `load('...mat')` **能**读 OpenModelica 的 MAT4
  （返回 struct，字段就是 OM 的原始矩阵名 `Aclass`/`name`/`description`/`dataInfo`/`data_1`/`data_2`），
  但**不产生** `h`/`v` 这些变量 —— 因为 OM 的语义是「变量名在 `name` 矩阵的**列**里、
  时间序列在 `data_2` 的**行**里」，而 `load` 只把顶层矩阵名当变量名。
- **⇒ 握手点就是这一层语义映射**，本仓提供 `bridge/omc_mat_load.m`（读取 + 消毒 + 元信息）。
  验收：`sh test/browser/run-mat-handshake.sh` → **14 PASS / 0 FAIL**（D2 正例 8 + D3 反向 3）。
- **两处真语义（都是喂真产物才暴露，逐条记）**：
  · `dataInfo` 的 **channel 0 = 独立变量 `time`**（非 1/2）——上游 writer 注释逐字
    "The independent variable (`time`): data_2 row 1."；第一版只认 1/2 ⇒ `time` 被跳过；
  · `name` 项数 ≠ `data_2` 行数：参数（`e`/`g`）走 **`data_1`**（channel 1），
    按"行数≥变量数"写会**假红**报"文件损坏"。
- **还有一层不是 bug 的边界**：Octave 内建函数名撞车（`time`/`e`）—— 变量能建出来，
  但调用 `time(...)` 会走内建 ⇒ 桥接**主动改名**（`time_2`/`e_2`）并在元信息里记明。

### R4（2026-10-13）· wasm 路径**不需要** OMBootstrapping（§4 pin 表要改）

- **原文**：§4 pin 表列 `OMBootstrapping`（"预生成 MetaModelica→C"）为三件之一。
- **实测**：Rust 模式（`OM_OMC_WASM=ON` 强制）下 `OMCompiler/Compiler/CMakeLists.txt:66-71`
  在 `if(OM_OMC_ENABLE_RUST) … return()` 处直接退出 ⇒ `boot/`（含 bomc）**根本不 add_subdirectory**；
  官方 CMake 注释原文："bomc/omc are never compiled from C"。
- **处置**：本仓 pin 表 = **2 tree**（`openmodelica` + `OMCompiler/3rdParty`）+ **2 toolchain**
  （`rust-nightly` + `clang`）；OMBootstrapping 不 pin（省一棵 ~百 MB 的树，且是**错的依赖**）。
