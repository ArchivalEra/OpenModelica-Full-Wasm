# HISTORY · 历史（append-only）

> 只追加，不改写。被推翻的断言进 `build/retractions.json`（不在这里删）。
> 每条带"当时是什么状态"，**当历史读，别当现状**（现状看 `STATE.md`）。

## 5.x 建仓：骨架期（2026-10-13）

- **起因**：用户点令"给那个块图仓删了或者改名成 OpenModelica-Full-Wasm，AGPL3，
  把需求书和 Einfacht 接入方法和 fork 管线制作方法和你的所有经验做成三个 md 放仓库里。
  那个仓库也应该出 wasm32 和 wasm64 和 IllegalPerformance 三条线…记住那个仓库得是 private。
  再配上白名单 gitignore，然后最后克隆到 /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/"。

- **澄清了一件事**：用户说的"那个块图仓"在 GitHub org 里**不存在**（查证：org 全仓列表
  无 block/diagram/modelica/omc 相关仓）⇒ 所以没有"删除/改名"动作，**只有建仓**。
  `master` 分支不叫 `main`（照姊妹仓习惯）。

- **建的东西**：
  - `ArchivalEra/OpenModelica-Full-Wasm`（**private**，AGPL-3.0）；
  - 三份经验文档（用户点令）：`docs/REQUIREMENTS.md`（需求书）、
    `docs/EINFACHT-INTEGRATION.md`（Einfacht 接入，7 个实测坑）、
    `docs/FORK-PIPELINE-AND-LESSONS.md`（fork 管线 + 全部经验）；
  - 白名单 `.gitignore`（48 条放行规则）；
  - Einfacht 机制层 vendored（`zreflect/` 27 文件 + `reflect-hooks/`）+ **本仓数据层**
    `zreflect/measure_openmodelica.py`；
  - 三线分支：`master` / `wasm32` / `IllegalPerformance`；
  - 本仓专属闸门 `build/113/check-lane-purity.py`（8 条自证，含 4 条反向断言）。

- **对上游 Einfacht 做了一处改进**：数据层模块名从**写死**（`measure_octave`）改成
  旋钮 `REFLECT_MEASURE_MODULE` ⇒ "换仓库只换一个文件"这条承诺才真成立。

- **★ 那次改进立刻被 C4 闸门抓了一次**：第一版顺手引入了第二个环境变量（严格模式），
  而它**没进旋钮登记表** ⇒ `facts.py --render-doc` 当场报
  "记号 `REFLECT_MEASURE_STRICT` 出现在 zreflect/*.py 里但不在旋钮登记表 —— 幻影旋钮"。
  ⇒ **这就是 C4「名录对账」要抓的形状**（文档承诺了、代码不读 ⇒ 配了静默无效）。
  修法：**不引入那个变量**（模块不在就静默回落通用占位）。
  附带教训：给"将来可能用"的名字留位子 = 自己制造幻影。

- **上游可行性（本批之前的查证，记在此备查）**：Modelica 能在浏览器跑 —— 第三方
  `omc-web` 演示把 `BouncingBall.mo` 跑通 `parse → C → 浏览器内编译 → 仿真 → 出图`；
  但**官方路线**是第一方 CMake wasm 目标（`rust_omc.cmake` 的 `RUST_OMC_WASM_RUNTIME`），
  本仓走官方。详细实测在姊妹仓
  `Octave-Full-Wasm/build/113/NOTES-experiment-omc-wasm.md`（§1–§11）。

## 5.y 首批构建管道（需求 A，2026-10-13）

**起因**：用户点令"无人值守出 wasm32 最终产物，紧贴 Einfacht 行动"。执行中用户追加
"改 clang 24"。

- **上游 pin 落地**：`upstream/openmodelica` submodule = **`cbff5eb7…`**（clone 时 master HEAD；
  侦察日查到的 `ffe6ff58` 已被上游推进两个提交 —— 正好实证"pin 的是 commit，跑的是别处的树"）；
  递归 init 其 `OMCompiler/3rdParty` = **`ae7e482a…`**（sundials/SuiteSparse 随 gitlink 固定）。
- **需求书四处原文被实测推翻，全部记进 `docs/REQUIREMENTS.md` §7**（不静默改原文）：
  · **R1 wasm64**：上游零支持（`rust_omc.cmake` 2312 行 0 命中 `wasm64` + 5 处显式
    `memory64: false`；全仓 code search 0）⇒ 首批出 **wasm32**。悬案 02 挂可跑结算件。
  · **R2 产物真名**：`OpenModelicaCompiler_bg.wasm`（wasm-bindgen 出包），不是 `omc.wasm`。
  · **R3 隐藏前置**：一步式配方缺 `SimulationRuntime/c/RuntimeSources.mo`（wasm 模式跳过
    整个 SimulationRuntime，而 mmtorust 源表引用它；官方 CI 专门 stash/unstash 搬运）
    ⇒ 本仓改用**官方两步链**（stage1 native configure 生成该文件 + wasm 交接件 → stage2 wasm 包）。
  · **R4 不需要 OMBootstrapping**：Rust 模式在 `Compiler/CMakeLists.txt:66-71` 直接 `return()`
    ⇒ pin 表 = 2 tree + 2 toolchain（不是三件）。
- **工具链（用户点令 clang 24）**：
  · **clang 24** = LLVM-wasm 仓 emsdk 内置的 `clang-24`（24.0.0git @55ea1f4e），实测自包含
    ⇒ 复制进 `tools/bin24/`（不动源仓）；
  · **wasm32 builtins 同源精编**：上游 configure 要 `<clang -print-resource-dir>/lib/wasi/
    libclang_rt.builtins-wasm32.a`，系统缺、无 root 装不了 apt（llvm-24 在 Debian experimental
    且直连 404 实测）⇒ 用 clang 24 编 llvm-project@55ea1f4e 的 compiler-rt（**146/146 对象**）
    → `tools/clang-resource/lib/wasi/`（117704 字节）；overlay 由 wrapper 注入 `-resource-dir`；
  · **Rust** = 上游 `rust-toolchain.toml` 钉的 `nightly-2026-05-31`（+ `wasm32-unknown-unknown`
    / `wasm32-wasip1` / `rust-src`）。
- **新增闸门 5 个，全部带三类用例自证并登记进 `build/gates-selftest.sh`**：
  `provision-toolchain.sh`（8 PASS）、`build-clang24-builtins.sh`（5）、`build-omc-wasm.sh`（9）、
  `check-wasm64-upstream.sh`（4，悬案 02 结算件）、`provision-upstream.sh --selftest`（5）。
  ⇒ 本仓专属闸门自证台现 **10 个闸门全绿**。
- **自证抓到 3 个真 bug（都是我自己写的）**，逐个修掉：
  ① `verdict_of` 空期望时 `case *""*` 匹配一切 ⇒ **静默返回 ok**（零值守卫用例抓到）；
  ② 源表抽取器对空表 `print("")` 吐空行 ⇒ 冒充"抽到了东西"；
  ③ `sources_of` 的 `wc -l` 在无尾换行时报 1（改用 `grep -c ''`）。
- **witness 闸门加宿主模式**：本机 docker 不可用（不在 docker 组 + `sudo` 被 `no_new_privs` 挡）
  ⇒ 加 `stamp_read`/`probe` 字段，让这条闸门在无 docker 机器上仍是**真断言**（不是恒 SKIP）。
  自证从 12 条加到 **15 条**（3 条宿主模式反向用例）。
- **补了一处历史漏洞**：`build/lib/gate.py` 被 `.githooks/` 四个检查器 import 却**从未提交**
  （`!build/*.py` 的 fnmatch 不跨 `/`）⇒ 克隆即坏。白名单已补（这是 `check-whitelist.py`
  的已知盲区第一次在本仓咬人，被本批实测抓到）。
- **★ 一个差点静默失效的坑（记下来）**：`facts.py` 的 `REFLECT_MEASURE_MODULE` 未被加载时
  静默回落到上游占位实现（数 md/py 文件的通用事实）**并且把台账写"成功"**（打印"已写出 4 条事实"，
  实际值被 guard 拦下不写）。⇒ 教训：**跑 facts 必须用钩子语境**（`. reflect-hooks/einfacht-env.sh`），
  否则量到的是假事实。已改用钩子同款语境 + 改口守卫逐条核对（`upstream_pins 0→4`、
  `whitelist_rules 48→56` 两条经核对后 `--accept-changes` 放行）。

### 5.y.1 构建期踩到的四个坑（全部实测，逐条带根因）

1. **stage1 不能是 native configure**：试了两次（① 缺 Fortran 编译器 → ② 关掉 MOO/优化后
   又缺 minizip）⇒ native 路径要一堆本机没有的 native 依赖（无 root 装不了）。
   **正解**：stage1 也开 `OM_OMC_WASM=ON`（要它产的只是 wasm 交接件，那三样 wasm 模式一样产），
   `RuntimeSources.mo` 用**单独生成器**产（官方 CI 也是 stash 出来的）。
2. **`stddef.h`/`stdarg.h` not found**（在 wasi-libc 交叉编时才炸，离根因很远）：
   overlay 的 `include` 是用 `bin24/clang-24 -print-resource-dir` 铺的，而**二进制复制后**
   它按自身位置推 → 返回不存在的 `<tools>/lib/clang/24` ⇒ overlay 里是**断链** ⇒
   clang 的内建头全丢。**正解**：用**源** resource-dir（emsdk 那份）铺 overlay；
   并在 `provision-toolchain.sh status` 加一条"内建头找得到"的断言把它拉到眼前。
3. **`function(f) endfunction()` 单行**在 CMake 3.20 报 parse error（写生成器时）。
4. **两次并发 rustup** 抢同一 toolchain 目录 ⇒ `missing manifest`（半装）。
   **教训**：安装类重活**一次只起一个**；已后台化的不重跑。

### 5.y.2 一个网络事实（值得记：它差点让本批"看着像卡死"）

`static.rust-lang.org` **直连 19 KB/s、经 `127.0.0.1:2080` 代理 7.5 MB/s**（实测，快 380×）。
按直连装 Rust nightly 需要数小时。⇒ `provision-toolchain.sh` 已把"探测代理可达性、
可达就走代理"写进代码（不是靠人记得 export）。

### 5.y.3 ★ **需求 A 结案：产物 build 出来了，且 Node 里跑得动**（2026-10-13 22:31）

- **产物**：`/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/`
  · `web/pkg-nodejs/OpenModelicaCompiler_bg.wasm` = **88,701,756 字节**
    （sha256 前 16：`eb1f63c66832eb6f`）
  · 同目录 `OpenModelicaCompiler.js`（wasm-bindgen glue）+ `omc-cli.js`（官方 launcher）
    + `wasm-blobs/`（liblapack / libc_pic / ModelicaUtilities）+ `fmu-loaders/`
  · 产物身份证 `omc.build.json` **verdict=ok**（`--verify` 实核后写入）
- **A3 判据实跑**（工单 01 的 Settling）：
  · `bash build/113/build-omc-wasm.sh --verify` → **rc=0**、写 `verdict=ok`；
  · `node web/omc-cli.js 'getVersion()'` → **`"-rust"`**（Rust 版 omc 的版本串；
    无 git tag 的构建树走上游 `SOURCE_REVISION=unknown` 降级路径 ⇒ 不是空串）；
  · `test/node/accept-omc-getversion.mjs` → **9 PASS / 0 FAIL**（含反向断言）；
  · `check-lane-purity.py --lane wasm32 --host … --mod ×3` → **OK**（宿主 3 个 side module 全同档）。
- **★ 跑得动的旁证（超出 A3 的部分，如实记但不吹）**：把 `BouncingBall.mo` 用
  `wasi_write_file` 写进 VFS 后：
  · `loadFile(...)` → **true**；`getClassNames()` → **{BouncingBall}** ⇒ **前端全通**
    （词法/语法/语义 + 类装载）；
  · `simulate(...)` 到**运行期**才停下（`rt_host_lin_solve` 是宿主注入的 JS 回调，
    Node CLI 没接）⇒ **需求 B 的活**（浏览器/宿主胶水），不是 A 的判据。
    注意：**别把它说成"仿真失败"** —— omc 编译前端通过、错误发生在 wasm-jit 引擎要宿主回调时。
- **关卡一路踩过的（全部已修，见 5.y.1 与下面 5.y.4）**：4 个 stage1 配置错、
  1 个 overlay 断链（stddef.h）、1 个 wasm-opt 旗标不兼容、3 个闸门自身的判据 bug。

### 5.y.4 ★ 闸门自己有三个判据 bug（都靠**真产物**暴露，已修 + 加自证）

1. **`check-lane-purity.py` 对 wasm 恒读不到架构 ⇒ 假红**：wasm 格式**没有** `Arch:` 头
   （实测：`llvm-objdump -h` 与 wabt `wasm-objdump -h` 对 .wasm 都不吐那行）。
   ⇒ 加 `_wasm_arch()`：解析 memory 段（id=5）的 limits flags 位 0x4（= memory64 标志）。
   **修的过程中又踩第二个坑**：主模块也有 import 段（函数 import），在那里早 return 会让
   宿主都读不到 ⇒ 必须继续走到 memory 段。
2. **side module 无法从字节流判档**（实测：`wasm-blobs/*.wasm` 是 `--experimental-pic --shared`
   产的 dylink.0 模块，**无 memory 段、无 import memory**，内存由加载器按 `mem_size` 分配）
   ⇒ 新增 `SIDE` 标记 + 判据改成**"必须与宿主同档"**（这才是纯度闸门的本意），
   并在报告里**记明**这条是靠宿主档推的（别假装直接读出来了）。
   **反向用例**：宿主自己也是 side module ⇒ 判据退化，**必须报**。
3. **`build-omc-wasm.sh --verify` 的版本串判据太窄**（只认 `OpenModelica|1.x`）⇒ 把合法的
   `"-rust"` 判红。改成"非空 + 单 token + 不含错误字样"，**并保留**"该报的必须报"
   （错误字样/空产物仍然红）。同类修正也落到 `test/node/accept-omc-getversion.mjs`。
- **教训（通用）**：**判据的"适用面"本身要过真产物**。三条 bug 都不是逻辑错，是
  "判据假设了别的格式"（ELF 的 Arch 头 / 非 dylink 的 wasm / 有 tag 的构建树）
  —— 只有**喂真产物**才会暴露。这正是本仓"能编过 ≠ 能用了"的又一次实证。

## 5.z 需求 B 攻关（2026-10-13 深夜，**未结案** —— 关机打断了重建）

**目标**：浏览器/Node 里跑通一个 Modelica 模型并出 `.mat`（需求 B）。

- **进展（实测，都是真跑出来的）**：`loadFile` → **true**、`getClassNames()` → **{BouncingBall}**、
  `translateModel` → **true** 且真的写了 `/tmp/BouncingBall.wasm`（`wasi_path_open` 返回有效 fd）
  ⇒ **编译器前端在 wasm 里全通**（词法/语法/语义/代码生成/写模块）。
- **卡点（报文逐字）**：`omc_simulate(...)` 与 `omc_sim_start(...)` 两条路都报同一个 Trap：
  `WebAssembly.Instance(): Import #0 "env" "rt_host_lin_solve": function import requires a callable`
  ⇒ **实例化模型模块时缺一个宿主函数**。
- **★ 根因（逐字证据链，已定位）**：
  · 上游 `openmodelica_wasm_jit/build.rs:1768-1775` 按"宿主是不是 wasm32"决定运行时 blobs 的**特征集**：
    native 那一支带 **`host_lin_solve`**（稀疏求解甩给宿主原生求解器），
    web 那一支带 **`inwasm_solve`**（rsparse 在 wasm 内解）。
  · 本仓两步链里，交接件 `blobs/runtime_wasip1_interactive.wasm` 是 **stage1（native 宿主）**编的，
    而 stage2 **按文件名直接复用**（`build.rs:1983 prebuilt_in`；stage2 stamp 实测 = `prebuilt:<该文件>`）。
  · 实测指纹三层一致：stage1 stamp = `…:host_lin_solve,host_log,primme`；
    交接件与 web 包里那份 **sha256 相同**（`1f89fef3…`）；
    `wasm-objdump -x` 数 `env.rt_host_lin_solve` 导入 = **1**（对照：按 web 特征单独编的 = **0**）。
  · 而 Node/浏览器宿主**没有原生求解器** ⇒ 那个 import 无人填 ⇒ Trap。
- **修补（已写进 `build/113/build-omc-wasm.sh`，但★未验证）**：stage1 结束后把该 blob
  **移出交接件**（改非 `.wasm` 后缀，避开 `publish_prebuilt` 的扩展名挑选）⇒ stage2 会自己重编
  web 版。依据是上游自己的原文（`build.rs:1978-1979`）："Missing from the directory,
  a blob is built as usual."
- **顺带查清**：`omc_set_inwasm_driver(1)` 只切驱动、**不换**运行时特征集；
  cmake 的 `RUST_OMC_WASM_INWASM_DRIVER` 只 append 到 **native omc 的 codegen** 分支
  （`rust_omc.cmake:1278-1281`），对 stage1 这条链不起作用（实测 stamp 未变）。
  `omc_simulate` 是**六参**签名。
- **★ 纪律（这一条最重要）**：本批**没有**把需求 B 说成"做完了"——修补未经实测，
  悬案 03 的状态是 `needs-info`，STATE 里也按"未结案"写。

### 5.z.1 ★ **需求 B 结案**（2026-10-14）

**判据实跑**：`node test/node/accept-omc-simulate.mjs` → **10 PASS / 0 FAIL**。

- **仿真真的跑完**：`messages` 含 `LOG_SUCCESS | info | The initialization finished successfully`；
  `resultFile = "/tmp/BouncingBall_res.mat"`；耗时 ~0.1s。
- **结果真产出**：25,729 字节 **MAT4**，已从 wasm VFS 取出并落盘宿主（供需求 D 的 Octave 握手）。
- **数据是真物理**（深验，不是"文件非空"就算过）：`h` 从 1.0 按 `der(v)=-g, der(h)=v`
  衰减，500 点齐全（min −0.9556 / max 1.0000），含 `when h<=0 reinit(v,-e*pre(v))` 的弹跳。
- **产物换新**：`OpenModelicaCompiler_bg.wasm` = **91,152,188** 字节（修复前 88.7MB；
  差额是补上的 in-wasm 求解器），身份证 **verdict=ok**。

**这一天修掉的四处**（都写了注释与自证）：

1. **`runtime_wasip1_interactive.wasm` 的宿主委派版**（昨天定位、今天闭环）：
   把它移出交接件 ⇒ stage2 自编 web 版 ⇒ `env.rt_host_lin_solve` 导入 **1 → 0**。
   **闭环实测**：`wasm-objdump -x` 数导入 = 0，仿真随即跑通。
2. **`build-omc-wasm.sh` 里 `#` 注释插在 cmake 参数续行中间**（dash 把它当新命令 ⇒
   `stage1 configure` 崩）。修法：注释挪出参数区。
3. **漏 blob（我昨天 `rm -rf Compiler/wasm-blobs/` 的后果）**：`libc_pic.wasm` /
   `ModelicaUtilities.wasm` 由 **`openmodelica_wasi_libc` 的 build.rs** 经 `OMC_WASM_BLOB_OUT`
   汇出，而 cargo 判定"无需重跑" ⇒ 副本没回来。**救法**：从该 crate 的 `OUT_DIR`
   取回（cargo 缓存还在）。**教训（写进 STATE）**：清产物**只删要删的那个文件**，
   别删共享输出目录。
4. **探针自身的两个判据 bug**（都是喂真产物才暴露）：
   · `omc_eval` 返回**字符串** `"true"`，我写 `=== true` ⇒ 假红；
   · MAT4 **没有 ASCII 魔数**，我照 MAT5 的 `MATLAB 5.0 MAT-file` 判 ⇒ 假红。
     正解读上游 `write_mat_header`（`openmodelica_mat_writer/src/lib.rs:405-413`）：
     `[i32 类型码][mrows][ncols][imagf][名长][名字\\0]`，首矩阵 = 类型码 51 + 4×11 `Aclass`。
   · 结果文件在 **wasm VFS** 里（不在宿主 fs）—— 取件协议
     `wasi_path_open(path) → fd` + `wasi_fd_read(fd) → Uint8Array`（照产物 `.d.ts` 契约）。

**用户点令落实情况**：`ccache` 已改回 **ON**（上游默认本也是 ON：`CMakeLists.txt:172`）
并显式 `-DOM_COMPILER_CACHE=ccache`；`OM_USE_CCACHE=OFF` 的图快写法已删。

### 5.w ★ **需求 D 结案**（2026-10-14）：`.mat` 握手打通

**判据实跑**（两条，都是真浏览器）：
- `sh test/browser/run-mat-handshake.sh` → **14 PASS / 0 FAIL**（D2 正例 8 / D3 反向 3 / 基线 2 / 注入 1）
- `sh test/browser/selftest-mat-bridge.sh` → **8 PASS / 0 FAIL**（三类用例齐备）
- `sh build/113/measure-samepage-cost.sh` → rc=0（D4 的量，见下）

**做了什么**：
- **新件 `bridge/omc_mat_load.m`**（Octave 侧桥接函数）：把 OM 的 MAT4 读成带名字的变量。
  它是需求 D 的**实质**（见 §7 R5）：Octave 的 `load` **认格式不认语义** ——
  实测 `load` 返回 struct（字段 = `Aclass`/`name`/`description`/`dataInfo`/`data_1`/`data_2`），
  但**不产生** `h`/`v`。
- **新件 `test/node/produce-result-mat.mjs`**：可复跑地产出结果 `.mat`
  （跑真仿真 → 从 wasm VFS 取件 → 落 `artifacts/BouncingBall_res.mat`）。**这是"换机器也能跑"的关键**
  （此前那份在 `/tmp` 里，是手搓的临时物）。
- **新件 `test/browser/accept-mat-handshake.mjs` + `run-mat-handshake.sh`**（D2/D3 验收）与
  **`test/browser/selftest-mat-bridge.sh`**（桥接函数自证台）。
- **新件 `build/113/measure-samepage-cost.sh`**（悬案 04 的结算件）。

**★ 四处真语义/真坑（全部喂真产物才暴露，逐条带证据）**：

1. **`dataInfo` channel 0 = 独立变量 `time`**（不是 1/2）——上游 writer 注释逐字
   "The independent variable (`time`): data_2 row 1."。第一版只认 1/2 ⇒ `time` 被**静默跳过**
   （自证台 ① 抓到："7 变量"实际只赋 6 个）。
2. **`name` 项数 ≠ `data_2` 行数**：参数 `e`/`g` 走 **`data_1`**（channel 1）。
   第一版按"行数 ≥ 变量数"写 ⇒ **假红**报"文件损坏"（文件没问题，是判据错）。
3. **Octave 内建函数名撞车**（`time`/`e`）：变量能建出来，但 `time(...)` 会走**内建**
   （`Invalid call to time`）⇒ 桥接**主动改名**（`time_2`/`e_2`）并在 `meta.renamed` 记明。
   这不是绕开问题：符号解析优先级是 Octave 的语义，只能按它的规则命名（且必须**可见地**改）。
4. **`cellstr(s.name')` 给的是列 cell** ⇒ `strcmp` 返回空 ⇒ `s.dataInfo(2,[])` 什么也没改
   ⇒ 自证台 ②c **假绿过一轮**。改成"逐列取名字再匹配"才真测到 `dataInfo` 越界那条分支。

**★ D4（同页成本）实测结论 = "当前不可行"（如实记，不是好消息）**：
- 体积：OM `91,152,188` + Octave `29,632,229` = **120,784,417** 字节（≈115 MiB）；
- 分步实例化：Octave 模块**编译成功**（710 导出、堆 81.4 MB），
  **OM 模块一编译整页就崩**（`Target page: closed`）。
- ⇒ 悬案 04 记 `ready-for-human`：三个候选方向（惰性/缩产物/分 Worker）**留给决策**，
  只做了"量"没做"选"。

**只读纪律**：本批对姊妹仓（`Octave-Full-Wasm`）**零写入** —— 只借它的
`harness/node_modules`（playwright-core）与 8761 站点的**只读**访问；套件、桥接函数、
夹具全部从本仓注入（用户点令：不许改本仓以外任何仓库的文件）。

### 5.w.1 完工审计（2026-10-14，逐条对照需求书 D）

- **D1**（OM 产 `.mat` ⇒ Octave 读）：✅ `bridge/omc_mat_load.m` 是那层语义映射；
  产出器 `test/node/produce-result-mat.mjs` 可复跑（真仿真 → VFS 取件）。
- **D2**（`BouncingBall_res.mat` 喂进 Octave，`load` 成功且**数值合理**）：
  ✅ 文件名逐字对上需求书点名的 `BouncingBall_res.mat`；
  "数值合理"**对解析解**（不是"看着差不多"）—— 4 条硬判据：
  时间步长 = 3/500（精确）、`h(1) = 1`（初值条件，精确）、
  `h(2)` 对 `1 − ½·g·dt²` 相对误差 < 1e-6、无超调（max = 1）且真弹到地下（min < 0）。
- **D3**（非 `.mat` ⇒ 明确报错）：✅ 三条反向断言（非 mat / 截断的 MAT4 / 路径不存在）。
- **D4**（同页成本）：✅ 已测 —— 结论是"当前不可行"（见 §7 R6 与悬案 04）。
- **合计**：`run-mat-handshake.sh` = **14 PASS / 0 FAIL**；桥接自证台 = **8 PASS / 0 FAIL**。
- **用户约束（不许改本仓以外其他仓库的文件）**：✅ 姊妹仓 `git status` **空**（零写入）；
  只借其 `harness/node_modules` 与 8761 站点只读访问；本仓临时物已清理
  （harness 里剩下的 `_*.mjs` 是姊妹仓自己 9 月的遗留与它的 `check-boot.sh` 产物，未动）。

### 5.w.2 审计又抓一个真 bug（2026-10-14）：`exec node` 让 trap 失效

- **现象**：跑完套件后姊妹仓 harness 里留下 `_omc-bridge-selftest.<pid>.mjs` 残渣
  （我手工清了两轮才去查根因）。
- **根因**：两个 runner 都写成 `cd "$H" && exec node ...` —— `exec` 把 shell **换掉**，
  `trap ... EXIT` 不再执行。**姊妹仓 `run.sh:19` 逐字警告过同一件事**：
  「不能用 `exec node`：trap 要能在退出时删掉这次副本」。
- **修法**：直调 node + `rc=$?` 透传（保住退出码语义：坏输入仍 rc=2 实测通过）；
  另加"开跑前清自己的旧残留"（上游 shell 被取消时 trap 也不跑）。
- **教训**：这条是"**照抄了形状、漏了注释里的禁令**"——姊妹仓的注释是**经验载体**，
  抄代码时要连注释一起读。

## 5.v 需求 E 攻关（2026-10-14）：MATLAB 语义桥 `omc_*`

**目标**（需求书 E）：Octave 侧实现 `omc_getVersion`/`omc_simulate`（拼 OM 脚本 → 调 omc → 读回 `.mat`），
E2 判据 = 在 Octave 里拿到**数据矩阵**；E3 边界 = 只做命令驱动，不做 `.m`→Modelica 翻译。

**★ 架构（六条实测教训定出来的形状；每条都踩过，写下来免得重走）**

1. **两条 wasm 各占一个文件系统**：Octave 的 MEMFS 与 omc 的 VFS **互不可见**
   （实测 `omc.wasi_path_open('/tmp/BouncingBall.mo') → -1`，而 Octave 侧明明写好了）
   ⇒ 桥必须**搬运字节**（宿主从一侧读出、写进另一侧）。
2. **`__web_fetch_sync__` 那条路被实测排除**：Octave 的 sync XHR 是它唯一的"同步取字节"通道，
   但我起了 Service Worker 专门试：**async fetch 被 SW 应答、sync XHR 不被拦截**（规范如此）
   ⇒ 不能靠"宿主现算 + sync XHR 取"。
3. **`.m` 侧绝不能忙等（死锁）**：Octave 的忙等占住它所在线程，而宿主读写 MEMFS 也要经同一
   上下文 ⇒ **两边互等**。实测：Octave 忙 3s 时宿主 evaluate 被阻塞 **2701ms**
   （worker 模式下同样成立，因为 worker 是单线程）。
   **现象极具欺骗性**：桥的应答文件明明写好了，Octave 却读不到。
   ⇒ 落成**两段式**：`.m` 只 `omc_submit()`（提交即返回）→ 宿主转给 omc、写回应答 →
   **宿主再调** `omc_collect(seq)` 取回。任何时刻只有一边在跑。
4. **`pause()` 在本 build 里把 evaluate 整条挂死**（rc=-99，连后续 `disp` 都不执行）；
   而 `while toc<t, end` 忙等正常 ⇒ 轮询只能用忙等（但见第 3 条：忙等要分片/让宿主先跑）。
5. **Octave 必须跑在站点的 worker 模式**（`?worker=1`）：主线程留给宿主桥
   （主线程模式下 Octave 独占线程 ⇒ 宿主插不进去）。这是"两个 wasm 各自占线程"的必然。
6. **两条独立通道别混**（worker 模式）：
   · `OctaveWorker.eval` 的返回是 `{id,kind,rc,err,ms}` —— **不含求值结果**；
   · `disp` 输出经 postMessage `{kind:'out'}` 落到**页面 DOM 的 `#output`**（不是 page console）。
   ⇒ 取值只能走 DOM；传输大块内容用 **base64 分块**（`__OMCFS_BEGIN__/_L/_END__` 协议，
   见 `bridge/omc_fs_read.m` 的头注：直接 `disp` 多行只在第一行带标记，逐字符转义不可逆）。

**交付件**（本仓）：`bridge/{omc_submit,omc_collect,omc_getversion,omc_simulate_async,omc_fs_read,omc_fs_write}.m`
+ `bridge/omc_bridge.js`（宿主侧）+ `test/browser/accept-omc-bridge.mjs` + `run-omc-bridge.sh`。
**注意**：`bridge/omc_simulate.m` / `omc_call_internal.m` 是**同步版**（第一版设计），
在真实环境下会死锁 ⇒ 保留作"反面教材 + 单机无宿主时的形状参考"，**正式路径是两段式那套**。

### 5.v.1 ★ **需求 B 结案**（2026-10-14）：页面内端到端

**判据实跑**：`sh test/browser/run-omc-page.sh` → **10 PASS / 0 FAIL**。

- **前置**：`MODE=web-release` 构建出 **web 档产物**（与 node 档是**两个独立构建**；
  100 个文件：`omc/OpenModelicaCompiler_bg.wasm` 91,423,608 字节 + 官方页面族）。
  `--verify` 已**档位感知**（web 档没有 `omc-cli.js` —— 那是 node 档的 launcher）。
- **站点**：新件 `build/promote-site.sh`（**受管辖入口**，三件套 `--dry-run/--verify/--selftest`
  齐备，自证 5 条含 4 条反向）+ `build/serve-coi.py`（**必须**带头 COOP/COEP ——
  普通 `http.server` 发不出那两个头 ⇒ 多线程档**静默**落回基础档）。
  ⚠️ 实测：8765 上原本驻着我早先的探针服务 ⇒ 发布后第一轮 404；**换占端口要按 PID 杀**
  （`pkill -f 'serve-coi.py 8765'` 匹配不上，那条进程的 argv 是 `.../site-probe/serve.py`）。
- **页面** `site/omc-bridge.html`（本仓自己的演示 + 探测页）：页面里
  `loadFile → true`、`simulate` 出 **MAT4**；判据不走"页面自报"，而是**把字节搬到 Node 侧再解析**
  （6 矩阵、`data_2` = 5×628、`name` = 7 列）——"自报"可以被写错，字节不会。
- **B3 反向**：语法错的 `.mo` ⇒ `loadFile` 不为 true 且 `getErrorString()` 给出带定位的可读错误。
- **★ 一个真坑（记进 §7 R7）**：web 档是 **wasm-bindgen ESM** —— 那些 `omc_*` 是**具名导出**，
  而 `default` 是**初始化函数**（`__wbg_init`），**不是模块对象**。
  第一版错拿 `mod.default` 当模块对象 ⇒ `omc.omc_set_env is not a function`。

### 5.v.2 两需求合计

| 需求 | 判据 | 结果 |
|---|---|---|
| **B**（页面内端到端） | `run-omc-page.sh` | **10 PASS / 0 FAIL** |
| **E**（MATLAB 语义桥） | `run-omc-bridge.sh` | **11 PASS / 0 FAIL** |

新增件：`site/omc-bridge.html`、`build/promote-site.sh`、`build/serve-coi.py`、
`test/browser/{accept-omc-page,accept-omc-bridge}.mjs` + 两个 runner、
`bridge/{omc_submit,omc_collect,omc_simulate_model,omc_simulate_async,omc_fs_read,omc_fs_write,omc_getVersion,omc_mat_load}.m`、
`bridge/omc_bridge.js`。
**只读纪律**：对姊妹仓零写入（只借 harness 的 playwright-core 与 8761 站点只读访问）。

## 5.u 同页集成（wasm32）+ 产物压缩 + wasm64 边界（2026-10-14，用户点令）

**用户点令**：读新 doc（`docs/LANES-AND-MEMORY-MODEL.md`）→ 先在 wasm32 做到**同页实现**，
然后**实现产物压缩**，再开 `IllegalPerformance` 分支**开始发展 wasm64**。

### 5.u.1 ★ R6 翻案：同页本来就可做，是我**测量方法错了**

- **旧结论**（§7 R6）："OM 模块一 `WebAssembly.compile` 就整页崩 ⇒ 同页当前不可行"。
- **翻案证据**：那次探针把 91MB 模块 **base64 成 ~122MB JS 字符串 + 巨型数组**再编译 ⇒
  内存放大把它变成"崩"。改用 **`WebAssembly.compileStreaming`**（引擎直接消化响应体）：
  Octave 29.6MB **92ms** + omc 91.4MB **219ms**，**同页都跑起来**，JS 堆峰值 **23–28MB**。
- 已登记 `build/retractions.json` 的 `R-R6-1`（翻案台账会拦"它重新出现"），
  §7 R6 就地标注翻案、保留旧结论作教训。

### 5.u.2 ★ 同页实现（`site/samepage.html`）：8 PASS / 0 FAIL

- 判据 `sh test/browser/run-samepage.sh`：两引擎**同页**跑起来 + **页内 `.mat` 握手**闭环
  （omc 产出 → 写进 Octave 的 FS → 用需求 D 的 `omc_mat_load` 读出
  `VARS time_2,h,v,der_h_,der_v_,e_2,g` / `N 628` / `HMAX 1.0000` / `HEND −0.9556`）+
  坏件反向必须报错 + 内存实测记账。
- **踩到的四个真坑**（都写进页面注释，别再犯）：
  ① Octave 必须跑**我们钉的 base 档**：它的 `pickFrom` 按 COI+`hasMemory64` 会自动挑
     **w64**（本机浏览器支持 memory64！）⇒ 而我们只拷了 base 档 ⇒ 404。
  ② 资源路径走 `opts.base`（`createOctaveCore` 收的；`locateFile` 不是它对外的口）。
  ③ 输出汇是 **`opts.host.print`**（更里层）；站点的 `createOctaveHost` 把它接到 `console.log`。
  ④ **长脚本要写文件 + `source`**（把 `;` 拼接的多语句一把梭给 `eval_string` 会 rc=0 但什么
     都不发生）；结果也**写文件读回**（stdout 有三层汇，FS 是唯一确定通道）。
  另：`promote-site.sh` 只拷 `bridge/*.js` 漏了 `*.m` ⇒ 页面 fetch 到 404 的 HTML
  ⇒ Octave 报 `syntax error near line 1`（"列清单漏扩展名"的同一族错误，已修）。

### 5.u.3 ★ 产物压缩：`-Oz` 91.4MB → 74.6MB（**−18.4%**）

- **又一处误判更正**：早先记的"binaryen 133 与上游旗标不兼容"**是错的** ——
  binaryen 133 **认** `--enable-bulk-memory`（也认 `-opt` 别名）；当时失败是**我手测时把整套
  旗标给漏了**（只给一两个 enable ⇒ 报 "requires bulk memory/SIMD"，看起来像版本不兼容）。
- 用**上游原样整套旗标**（`rust_omc.cmake:829-832` 的 7 个）实测：约 69s，
  **导出/导入面逐名不变**（538 exports / 116 imports 无差集），替换后
  **OMC-PAGE 10 PASS/0 + SAME-PAGE 8 PASS/0 全绿**。
- 已作为**构建脚本自己的步骤**接入（`WASM_OPT=ON` 时跑；旗标自己写、前后字节与耗时记账到
  `wasm-opt.stats`）—— 不靠上游那条难分辨的 `RUST_OMC_WASM_OPT`。

### 5.u.4 wasm64：**上游 + Rust 双缺**（边界如实记）

- 上游：`check-wasm64-upstream.sh` → `NOT-YET（0 处命中）`（悬案 02 的结算件，rc=1）。
- **Rust 侧更硬**：`rustup target list` 里**没有 `wasm64-unknown-unknown`**（稳定与
  nightly-2026-05-31 都没有）⇒ OM 编译器主体（`libopenmodelica_compiler` 是 Rust cdylib）
  **无法编成 wasm64**。姊妹仓能出 wasm64 是因为 Emscripten 有 `-sMEMORY64=1`（C/C++ 路径），
  本仓是 Rust+CMake 目标 ⇒ **根因不同，不能照搬**。
- ⇒ `IllegalPerformance` 线的 wasm64 工作量 = **等上游 Rust target + 上游 CMake 路径**；
  本仓能先做的是：**把该线的纯度判据与档表先立起来**（文档 §3/§6 已给形状），
  以及把性能候选（SIMD/多线程/优化求解器）按 §5 的纪律（A/B 差分门、负判决也是资产、
  不许改默认档）逐条验。

## 5.t `IllegalPerformance` 线开工（2026-10-14，用户点令第三步）

**用户点令**："再直接开一个名为 IllegalPerformance 的分支直接开始发展 wasm64"。

- **分支现状**：`IllegalPerformance` 已存在（建仓时三线之一）；本批把 `master` 的底座
  合过来（同页/压缩/桥接件都在），**线内不动默认线**（§5 纪律：性能线是候选线，发运是产品决定）。
- **★ 档身份实测（本线第一步不是"编 wasm64"，而是"先看清边界"）**：
  · `build/113/check-wasm64-upstream.sh` → `NOT-YET（0 处命中）`：**上游 CMake 无 wasm64 路径**；
  · **Rust 侧更硬**：`rustup target list` 里**没有 `wasm64-unknown-unknown`**（稳定与
    `nightly-2026-05-31` 都查了）⇒ 编译器主体（`libopenmodelica_compiler` 是 Rust cdylib）
    **编不成 wasm64**；
  · 姊妹仓能出 wasm64 的事实依据是 **Emscripten 的 `-sMEMORY64=1`（C/C++ 路径）** ——
    本仓是 **Rust + CMake**，**根因不同、不能照搬**（`docs/LANES-AND-MEMORY-MODEL.md` §4 同旨）。
  ⇒ 结论：wasm64 的工作量**卡在上游**（两条同时满足才可开工：上游 CMake 路径 + Rust
    memory64 目标）。悬案 02 已补这条；**本线当前能做的**是先立基线与判据。
- **★ 基线已立（新件 `build/113/ilperf-baseline.sh`，4 条自证）**——只读、不改产物：
  · 产物：web 档 `OpenModelicaCompiler_bg.wasm` = **74,579,521** 字节（压缩后），
    sha256 `ea0a9f4f…`；
  · **已有加速面（不是待做项）**：**SIMD 指令 5876 处** + post-MVP 指令 23,451 处；
    `target_features` 段：`bulk-memory, bulk-memory-opt, call-indirect-overlong, multivalue,
    mutable-globals, nontrapping-fptoint, reference-types, sign-ext, simd128`
    （上游注释原文：rustc/LLVM 对 `wasm32-unknown-unknown` 默认开这些，
    `strip` 丢了 `target_features` 段才需要手工告诉 binaryen）；
  · memory 形态 **导入/导出 = 0/1**（wasm32：宿主导出 memory）—— 这也正是纯度闸门
    判档时要看的量之一。
- **性能候选的下一步**（按姊妹仓 §5 的封口清单，**每条都要 A/B 差分门 + 变异自证**）：
  换分配器（姊妹仓结论：**有效**）/ 换 BLAS（**有效**，配 IEEE 逐位红线）/
  libm 标量替换（姊妹仓**负判决**：wasm 无标量 FMA）/ 热点定位（仪器，不猜）。
  ⚠️ 本仓的等价物是 `openmodelica_solvers`/`openmodelica_lapack` 那几层，**不是** BLAS 库名照搬。

### 5.t.1 ★★ 同日更正：wasm64 **工具链侧可做**（我上一条查错了地方）

- **我写错的**（5.t 里）："Rust 侧没有 `wasm64-unknown-unknown` ⇒ 编译器主体编不成 wasm64"。
  **错在查的表**：`rustup target list` 是**"可安装"列表**，不是**编译器内置目标表**。
- **实测（新件 `build/113/build-w64-spike.sh`，5 条自证，全部可复跑）**：
  · `rustc --print target-list | grep wasm64` → **`wasm64-unknown-unknown` 在**；
  · 裸编报 `can't find crate for core`（该目标**无预编译 std**）；
  · **`cargo build --target wasm64-unknown-unknown -Zbuild-std=core,alloc`** ⇒
    **8.8 秒**编出 353 字节 wasm64；
  · Node 实例化成功：`add64(2n,3n)=5`（**参数是 BigInt** —— 64 位地址空间的特征，旁证是真 wasm64）；
  · 本仓**纯度闸门认档 = wasm64**（memory64 标志判据），且**wasm32 产物喂 wasm64 档正确地红**
    （反向断言 rc=1）。
- **更正后的边界**：wasm64 在**工具链侧可做**（`-Zbuild-std` 即可）；
  缺的只是**上游 CMake 路径**（`rust_omc.cmake` 0 命中 wasm64）——
  "上游还没接进构建系统"，**不是"编不出来"**。
- 已登记翻案 `R-02-1`（防止那条错误结论重新出现）；悬案 02 就地更正，**结案条件收窄为一条**。
- **自证台当场抓到我另一处写反的判据**：`verdict_of` 的"反向断言合格"我写成了
  `rc != 1`（语义相反）—— 自证台的"该报必须报"用例把它红了，修成 `rc == 1`。

### 5.t.2 复跑闸门抓到我一条**判据与量的性质不匹配**

- **现象**：`samepage_heap_peak` 复跑输出 31,000,000 vs 台账 26,000,000 ⇒ 复跑闸门红。
- **根因（不是产物问题，是我的判据错）**：**JS 堆峰值与编译耗时都是"每轮都变的观测量"**，
  而台账的裸值契约要求"逐字复跑稳定" ⇒ 把波动的原值放进台账，**必然红**。
- **修法**（两条键都改）：`samepage_heap_peak` → **`samepage_heap_peak_mib5`**
  （向上取整到 5 MiB）；`samepage_compile_ms` → **`samepage_compile_ms100`**（取整到 100ms）。
  **cmd 与值同源同算法**（cmd 里做同样的取整）⇒ 逐字复跑稳定。
- **通用教训**：上键前先问"这个量**逐字复跑**会一样吗" —— 不会的（时间、内存、吞吐）
  就该上**档位/上界**，或只作散文记录。这条正好是"事实纪律第 2 条（口径搬进代码）"的变体：
  **量的性质决定它能以什么形态进台账**。

### 5.t.3 波动量取档的第 2 课：**档要粗于噪声**

- 把 `samepage_compile_ms` 取整到 100ms 之后，复跑闸门**仍然红**（295ms→300 档 vs
  306ms→400 档 —— 抖动跨过了档边界）。
- ⇒ 修正：粒度改 **500ms**（`samepage_compile_ms500`）。**档位必须粗于噪声**，
  否则"档"只是把抖动换了个单位。
- 另：改档名后 `check_facts` 又抓到 STATE 里一个**裸数字 500**（“500 点齐全”那句）
  —— 因为 500 已属于某台账键 ⇒ 按纪律改写成引用。**这条闸门管得细，是好事**。

## 5.t.4 删线：`IllegalPerformance` 删除（2026-10-14，用户点令）

- **用户原话**："IP 分支只有 wasm64 目标按照各种官方 fork 管线做出来达到生产级以后才是
  脱离官方树的开发，所以你现在直接做出来其实没什么用" ⇒ **删线**。
- **做的**（本仓铁律"不删 git 对象"下的合法删法）：
  ① 先打 tag `archive/ilperf-f283610` 钉住原 tip（f283610），使该提交及祖先**永久可达**；
  ② 推 tag 到远端（两步失败一次：第一次被复跑闸门拦，因为台账 `lane_branches_present`
     还是 3 —— 闸门抓对了，那正是"删了线但台账没跟上"的形状）；
  ③ 删本地分支 + 删远端分支。
- **台账变化**：`lane_branches_present` **3 → 2**（走 `--accept-changes=lane_branches_present`
  显式放行 —— 守卫按设计拒绝了静默改口）。cmd 的 awk 名单同步收成 `^(master|wasm32)$`。
- **残面清理**（"线已删"必须真的删干净，不留会说假话的句子）：三语 README、STATE、
  maintaince、AGENTS、FORK-PIPELINE、REQUIREMENTS §2C/§7R7、悬案 02、LANES §5、
  两个脚本（`ilperf-baseline.sh` / `build-w64-spike.sh`）的头注与 JSON `lane` 字段。
  **保留的**：`w64_spike_*` 两条事实（"工具链侧可做"是**重建该线的前置**，不是"线已在"）；
  纯度闸门的 `ilperf` 档名（重建时用）。
- **顺手抓到的旧假话**：README 三语里"wasm64 仍是**双缺**：上游无路径 **且 Rust 侧没有
  `wasm64-unknown-unknown` target**"—— 后半句正是**已翻案**的 `R-02-1`（查错了表：
  `rustup target list` ≠ `rustc --print target-list`）。三语同批改掉，改成 R-02-1 的结论。

## 5.s 两线验收状态实测（2026-10-15）

**wasm32 线 = 无 COI 可用（实测）**：
- 判据物三件：产物 0 原子指令（`omc_web_atomic_ops` = 0，带校准样本钉住仪器真认 atomic）、
  0 线程导入、0 共享 memory；上游 `omc_worker.js` 头注逐字 "needs no SharedArrayBuffer /
  cross-origin isolation"。
- **直接证据**：普通 `python3 -m http.server`（零 COI 头）服务站点 ⇒
  `run-omc-page.sh` **10/0** + `run-samepage.sh` **8/0** 全绿；
  另两套在姊妹仓站点（8761）：mat-handshake **14/0** + omc-bridge **11/0**。
  Node 侧 9/0 + `build-omc-wasm.sh --verify` verdict=ok。
- 如实记：无 COI 时 `omc_enable_cancel_poll` / `progress_sink` / `fmu_aot` 降级（SAB 控制块），
  主链路不受影响。

**master 线 = wasm64 + 多线程双双卡上游（查实）**：
- wasm64：结算件 `check-wasm64-upstream.sh` → NOT-YET（悬案 02 判据不变）。
- 多线程：上游 wasm 面**没有**运行期线程路径 —— `RUST_OMC_THREADS` 是 rustc 编译期并行；
  OpenModelica.rs 无 wasm-bindgen-rayon / wasi-threads；toolchain targets 仅 wasm32×2；
  coi_server 说的 "threaded builds" 是 Qt 前端那条线（`/opt/Qt/6.11.2/wasm_singlethread`）。

**顺手修掉纯度闸门一个真 bug（core2.wasm 假红暴露）**：import 段每条 = **module 名 + 字段名
两个字符串**（spec §5.5.3），旧解析只读一个 ⇒ 字段错位 ⇒ `env.memory` import 永远读不到 ⇒
fmi 的 `js-component-bindgen-component.core2.wasm` 被假报"读不到架构"。修后自证 24/0
（新增 4 条回归用例：双 name wasm32/wasm64 + 端到端正/反），全站点纯度**真绿**：
宿主 + 13 附属模块全 wasm32（`site_wasm32_mods` = 13）。

## 5.r 首发：v0.1.0-wasm32（2026-10-17，用户点令「仅发布 wasm32 线一个版本」）

- **版本号定第**：`v0.1.0-wasm32`（codename first-light）—— 首个发布版；上游 pin
  `openmodelica@cbff5eb7` + `omcompiler-3rdparty@ae7e482a`，工具链 clang 24.0.0(55ea1f4) +
  rustc 1.98.0-nightly(nightly-2026-05-31)，全部记在版本身份证 `build/VERSION.json`。
- **master 标注当前适用档 = wasm32**（STATE 线表 + 三语 README 同批）：master 的
  wasm64/多线程目标卡上游（悬案 02），上游接路径即翻面 —— 按用户点令别想太多，
  先发布能发的这一档。
- **发布件**：`build/VERSION.json`（身份：版本/档/pin/工具链/指纹台账键/验收判据）+
  `docs/RELEASE-v0.1.0-wasm32.md`（说明：能力表/指纹表/纯度/已知边界，数字全部引台账键）。
- **台账上键**：`release_version` = 0.1.0（从 VERSION.json 读出，不手抄）⇒ 26 条事实。
- **发布动作**：annotated git tag `v0.1.0-wasm32` 钉在发布提交上（两线同内容）+
  GitHub Release（附 web/node 两份 wasm 的 sha256 与字节，数字从台账取）。

## 5.q 钓鱼执法信（mail/007+008）与缺陷 1 当日修复（2026-10-19）

**收信**：007 = 首次肉眼验收凭据（四套 43/0 复现 + 四面亲验 + OMShell 从零跑到
ChuaCircuit 仿真成功——我们脚本从未覆盖的面）；008 = 钓鱼执法轮（用户点令"故意使坏，
只报不修"）——**一个发信级缺陷 + 全绿 ×10 + UX 事实 ×2 + 观察项 ×2**。

**缺陷 1（Export FMU 全挂）根因链（每环实测）**：
- 我们的 clang24 wasm-ld 给 `-shared` wasm 写 `dylink.0` **subsection 6**
  （payload `06 "wasm32"` = tool-conventions 的 target-features 声明）；
- FMU 导出走 wit-component 0.259（wasmparser 0.259）**只认子段 1–5** ⇒
  `unrecognized dylink.0 subsection: 6` bail；
- 官方 CI 的 clang 不写 6 ⇒ 上游无感；我们 14 个 blob 全带 ⇒ FMU 链接必炸 ⇒
  FMI Simulator 对普通访客不可用。**"能编过 ≠ 能用了"又一实例**（子段 6 合法，
  炸在白名单解析器）。

**修法**：`build/113/strip-dylink-features.py`（10/0 自证，含真 clang24 端到端）剥
subsection 6——语义无损（wasm32 是 dylink 默认档）。挂进构建脚本两处
（stage1 交接件 + stage2 后）防回归；幂等（上游将来认 6 也不冲突）。
关键操作序：**先剥 OUT_DIR 再让 cargo include_bytes!**（stamp 不看内容）——
本次是剥完后增量重建 stage2，新编译器子段 6 签名 0 处（旧 14 处）。

**实测**：新 web 档 74,579,404 B（sha 8287589e…，-Oz 后）；
`run-export-fmu.sh` → **6/0**（Exported BouncingBall.fmu (me_cs) 654,894 B +
下载触发 + ★反向断言）；全量回归 omc-page 10 + samepage 8 + mat 14 + bridge 11 +
node 9 = **58 PASS / 0 FAIL**。三层 SHA 磁盘/HTTP 对齐，站点已发。

**台账改口**（6 键显式放行）：omc_web_wasm_{sha,bytes}、samepage_{om,sum}_bytes、
whitelist_rules（79→81，新验收件+剥离器）、omc_web_atomic_ops（witness 换新 sha）。

**教训**：① 工具链比上游 CI 新 = 一类**版本错配缺陷**的温床（写侧新特性 × 读侧
白名单）；② blob 是 include_bytes! 进编译器的 ⇒ **改 blob 必须重建编译器**，
光改文件树没用；③ 对方钓鱼执法抓的缺陷比我们全部脚本验收加起来都深 ——
外部验收是资产。

## 5.p mail/010–012：复验结案 + 011 两问（2026-10-21）

- **010 收讫**：缺陷 1 复验收执——对方独立复验全成立（215 wasm 干净 / sha 两处一致 /
  6/0 判据 / 全链 FMI Simulator 跑通：自产 FMU → 装载 1232ms → 1695 samples）⇒ **结案**。
- **011 两问逐题实测后答**（mail/012）：
  · **A1（MSL 产物化）= 会**：下载链实测（官方索引 196 库 → Modelica 4.1.0+maint.om 的
    `8df0769a` zip，20,362,007 B，sha256 `ba66dd3a…`——注意上游索引的 sha 字段是**版本串**
    不是字节 sha）；官方管道 `omc_vfs_load_zip` 在产物导出面（"One fetch + this call
    stages a whole Modelica library"）⇒ 站内 zip 一次 fetch 即离线装库。落点
    `site-omc/assets/omc/`，**随下一个产物批次**（改产物必全量回归的纪律），落好回信。
  · **A2（进度钩子）= 半只**：`omc_enable_progress_sink` + `__omcReportProgress(permille,
    phase)` 在产物（permille 0..=1000/-1 不定；phase 0–5 含 PHASE_SIMULATE）；覆盖面
    **源码实测**：解析每文件（ParserExt.rs:398）/实例化（NFInst.mo:165）/FMU 导出每平台
    （CevalScriptBackend.mo:4556）有上报；**simulate 主链 0 命中**（simulate_fn/sim_driver
    无 report_progress）——上游备了语义位但仿真循环没人上报。UI 对 simulate 回落
    （不定胶囊）是唯一诚实形态；装库/编译阶段可接真数据（在役参考 omc_worker.js:63）。
- 浏览器探针实测确认：simulator 页主线程**不收**进度消息（控制块是 SAB 直读非消息），
  status 的「build Xms + sim Yms」分相计时是页面自己记的账。

## 5.o 转公开准备（2026-10-21）：CI 面接上 + README 公开门面 + 18 badges

- **用户点令**：本仓（OpenModelica-Full-Wasm）转为**公开**做准备；Einfacht 是收 issue 的
  上游（**零触碰**），vendored 接入在本仓自己配。
- **★ 三语 README 钩子的 CI 面接上**：本仓此前**没有** .github/workflows/ —— pre-push
  注释里承诺的"CI 跑同一条判据"是空头支票。补上两份（vendored Einfacht 形态、适配本仓）：
  · `readme-sync.yml`——三语同批的 CI 落点（check_readme_sync.py --changed，与
    pre-push 同源）；
  · `facts.yml`——**可移植子集**并诚实声明取舍：名录对账 / 机器块一致 / 白名单 /
    平台模块自证 / 纯夹具自证（check_readme_sync、check-lane-purity）；产物锚定的
    闸门（复跑 cmd、pin 见证锚在产物树）**留在装钩子有产物的机器**上由
    pre-commit/pre-push 正面执行 —— CI 不假装查过。
- **README 公开门面**（三语同批，18 枚 badge 全部可验真）：
  · CI×2（readme-sync/facts）+ release（v0.1.0-wasm32 tag）+ license（AGPL-3.0）；
  · GitHub 动态×8（stars/forks/issues/prs/last-commit/commit-activity/repo-size/code-size）；
  · 语义×6（Modelica engine / wasm32 lane / COI-not-required / clang24+Rust nightly
    toolchain / assertions-rerunnable / Einfacht-powered）；
  · 「🔒 本仓是 private」行删除（三语），换成姊妹仓 + Einfacht 指引。
- **转公开前置审计**：git grep 秘密扫描（3 命中全误报：GPL 原文/正则名/散文）⇒ 无泄漏；
  本机代理端口（127.0.0.1:2080）出现在文档属构建事实，无害。
- whitelist +2（!.github/ !.github/**）⇒ 85 条；台账 whitelist_rules 改口放行。

## 5.n mail/013–016：MSL 站内资产落地 + 渠道①收口（2026-10-25）

- **013 收讫**（三项声明对方亲验全成立）；唯一待办 = 落 MSL zip ⇒ **落地并实测闭环**：
  `site-omc/assets/omc/msl-4.1.0-maint.om.zip`（安装形状 19,482,938 B / sha `a97d8d94…`，
  台账键 msl_asset_{bytes,sha}）。判据 `site/msl-local.html` + playwright → **MSL-LOCAL
  PASS**（fetch 48ms → vfs_load_zip 4376 文件 → loadModel true / 版本 4.1.0 / ★反向
  loadModel(NoSuchPackageXYZ) fail-ok）。
- **两条对 mail/012 A1 原文的实测修正**（判据跟着实测走）：
  ① GitHub 源 zip 是仓库快照（顶层 hash 目录）⇒ 站内资产为安装形状重打包
  （sha a97d8d94… ≠ 源 zip ba66dd3a…，同 8df0769a 版本串锚定——对账对版本串不对字节）；
  ② MODELICAPATH 经 omc_set_env 传不进 loader（实测仍用默认 /.openmodelica/libraries）
  ⇒ 正确接法 = vfs_load_zip 直接落默认库目录，一次 fetch 一个调用。`.d.ts` 契约的
  "point MODELICAPATH at mount" 在本产物不成立，记档。
- 旁证（Node 同产物）：官方 installPackage 链喂站内 zip + 索引也能离线走通（pending-download
  协议的 cache 槽位喂入即装，"Package installed successfully (SHA 8df0769a…)"）——两条路都通。
- **014 裁决**：用户已选①并执行（仓 PUBLIC）；我补 asset 无认证全量下载对账：sha
  `8287589e…b001` 与 site-omc 产物逐字一致 ✓。UI 越界处置同意收口方裁定（结果对程序错，
  下不为例）。**015 收讫**（球在 UI）。
- 回信 016（逐项 + 复跑命令）。台账 26→28 条；whitelist 86；闸门全绿。
- 踩坑两枚：measure 的 `%` 格式串少参数（TypeError 现场修）；文件名带 8df0769a 会触发
  check_stale 的 sha 出处断言（含 AUTO 块 cmd 里的）⇒ 资产文件名不带长 hash（身份在台账键）。

## 5.m mail/017→018：MSL 落位修正 + 出表 + 渠道挂 asset（2026-10-25）

- **017 三件全办**：
  1. **落位修正**（我原先违规）：`assets/omc/` → `assets/msl/`——收口方新裁定 MSL 不许落
     引擎条目的树目录（会把引擎 `form:"tree"` 的字节和从 74.7MB 虚胀到 94MB+）。
     迁移后端到端判据重跑仍 PASS。
  2. **出表**：`build/extra-content/content-list.json`（producer 态一条 MSL；
     form=file / consumer=["omc"] / role=package / sha 取台账键）；新自证件
     `build/113/check-msl-content-list.py`（11 自证；宿主校验器在盘时真跑它，
     producer+site 两模式都 ok；反向五类正确红；不在盘时跑本地等价判据并明说）。
  3. **渠道**：MSL zip 挂 release `v0.1.0-wasm32` asset（GitHub digest 与台账逐字一致，
     等于第三方复核；引擎 asset 未动）。
- **命名申辩**：不同意 `name:"msl"`（缩写不可检索，且会进机器产物成为 UI 面板键）——
  建议 `modelica-standard-library`；命名权在收口方，其裁定即改。
- 反向用例设计的一课：我第一版拿「sha 值改成全 0」当反向用例 ⇒ 校验器 rc=0（它只验形状
  不验字节，这是**对的**）⇒ 是我用例设计错了，换成 sha 格式非法 / 站点态绝对 URL 才真红。
  **"该报的必须报"要先确认它真的该报**。

## 5.l mail/019–021：命名裁定收讫 + JS 胶水两键上账（2026-10-25）

- **019 收讫**：017→018 三件（落位迁移 / 出表 / release asset）对方**亲测复验全过**
  （目录已迁、宿主校验器双模式 ok、GitHub digest 与台账逐字一致）；**命名申辩采**
  （`modelica-standard-library` 定案，我表本来就按全称写，零改动）。它补的判据更硬：
  catalog 现有名字全部携带上游身份，`msl` 会是第一个生态内缩写。
- **020 提单已办**：台账补 `omc_web_js_sha` / `omc_web_js_bytes`（56,586 B /
  `56c399bd…`，**先独立实测再写**，与对方期望逐字一致）。意义：UI 运行期只认表
  `files[]`，其唯一产地 = 生产者台账；bg.wasm 键早有、JS 件缺 ⇒ UI 硬编码是**孤儿事实**。
  补键后链条通：本仓台账 → 宿主投影 → UI 从表取（它 #3 删硬编码条件齐）。
  `.d.ts` 不建键（不在下发闭包，采纳其裁定第 ② 条）。
- 台账 28→30 条；复跑闸门 30 条逐字一致。

## 5.k mail/107→023：E 线桥「从未交付」被外仓抓出（2026-10-29）

- **107 的实测成立**：Octave 产品里 `omc_simulate` / `omc_mat_load` / `omc_collect` **不存在**。
  根因：我的验收是**运行时注入**（`accept-omc-bridge.mjs` 逐件 injectFile + addpath），
  验的是桥本身，不是交付 ——「测到了 ≠ 交付了」的又一实例。我认账。
- **★ 装配形态实测定案（我第一版也写错了）**：以为「站点目录铺 bridge/ + addpath」就行，
  实测**不行** —— `addpath` 走 MEMFS，MEMFS 根只有 tmp/home/dev/proc/fonts/src/usr，
  站点 HTTP 路径不在里面（铺满 11 件后 `exist()` 仍 0）。正确形态 =
  **`M.FS.writeFile('/bridge/…')` 写进 MEMFS** 再 addpath（实测：三件全 FOUND，
  对照组 sin FOUND / 假名 MISSING）。被自己的产品态验收件抓出来的。
- **落地**：`docs/BRIDGE-DELIVERY.md`（清单/装配/时序/判据）+ `bridge/manifest.json`
  （12 件 bytes+sha）+ `check-bridge-manifest.py`（11 自证，登记后共 18 件）+
  `accept-omc-bridge-product.mjs`（零注入产品态，含对照组）。真站点实测
  **5 PASS / 3 FAIL**（三红 = 缺口本身），装配后应 8/0。
- 回信 023（三问逐答 + 给宿主的五行装配代码）。

## 5.j mail/024→026：宿主抓出「桥零调用方」+ 桥扶正为产品件（2026-10-29）

- **宿主两条新事实（都成立，我复核）**：
  ① `omc_bridge.js` **零调用方**——产品站从未 import 它（`grep -rl OmcBridge site-omc/`
     只命中它自己）；② 三条承重语义只活在验收套件里，交付件里**缺 `cd`**（resultFile 会空）
     与 **`simulateModel`**。
- **处置**：`omc_bridge.js` **扶正为产品件**——三条语义写进 `dispatch()` 本体（连注释），
  新增 `cd` 处理与 `simulateModel` 一步到位；新闸门 `check-omc-bridge.mjs`（7 条自证，
  含反向「未知命令必须拒绝」）锁住它们，**语义丢了就红**。自证台 18→19 件。
- **形态纠宿主一条**：它建议「站点铺 `omc/bridge/` + addpath」——**不够**（addpath 走
  MEMFS，站点 HTTP 路径不在其中；实测铺满 11 件后 exist 仍 0）。正确形态 = **两段**：
  站点落字节（provision 渠道）+ **运行期写 MEMFS 再 addpath**。回信 026 投宿主收件箱
  （过它的 check-mail-boundary：To: host ✓）。
- 踩坑：新闸门进自证台要 ① 可执行位 ② 末尾机器行必须是 `=== N PASS / M fail ===`
  （小写 fail）——两条都是自证台当场抓的。
