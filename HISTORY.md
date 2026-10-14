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
