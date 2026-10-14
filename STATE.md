# STATE · 活状态

正文只写「现在是什么」，**数字一律引用 `build/FACTS.json` 的键**（或看文末机器块）。
方向与地图在 `maintaince.md`；硬规矩在 `AGENTS.md`；要做什么在 `docs/REQUIREMENTS.md`；
历史在 `HISTORY.md`（append-only）。

## 现在是什么（2026-10-13）

- **★ 需求 A 已结案：官方 wasm 目标 build 出了产物，且 Node 里跑得动。**
  产物 = `/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web/`
  （`pkg-nodejs/OpenModelicaCompiler_bg.wasm` + `omc-cli.js` + `wasm-blobs/`），
  身份证 **verdict=ok**；`getVersion()` 出串（实测值见台账
  `[[omc_wasm32_verdict]]` / `[[omc_wasm32_bytes]]` / `[[omc_version_string]]`）。
  结案判据（工单 01 的 `Settling:`）= `build/113/build-omc-wasm.sh --verify` rc=0 —— 已实跑。
  **未做的**（别混）：浏览器端到端跑模型（需求 B）与 `.mat`（需求 D）都**还没做**；
  Node 侧 `loadFile`/`getClassNames` 已通（前端全通），`simulate` 停在"要宿主注入 JS 回调"
  （那是 B 的活）。

- **构建路径 = 宿主直跑**（本机 docker 不可用：当前用户不在 docker 组、`sudo` 被 `no_new_privs`
  挡 ⇒ 姊妹仓那种"容器内构建"在本机走不通；容器化另立批次）。
  **工具链**：clang 24（用户点令；LLVM-wasm 仓 emsdk 内置件，自包含）
  + 同源精编的 wasm32 builtins + Rust `nightly-2026-05-31`（上游 `rust-toolchain.toml` 钉的）。
  **上游 pin**：`upstream/openmodelica` = `cbff5eb7…`、`OMCompiler/3rdParty` = `ae7e482a…`
  （2 tree + 2 toolchain，见 `build/upstream-pins.json`）。

- **需求书四处原文被实测推翻（记在 `docs/REQUIREMENTS.md` §7，不静默改原文）**：
  · **R1**：`master` 线要的 **wasm64 上游零支持**（`rust_omc.cmake` 0 命中 + 5 处显式
    `memory64: false`）⇒ 首批产物出 **wasm32**；悬案 02 挂可跑结算件
    `build/113/check-wasm64-upstream.sh`（上游加支持即翻面）。旁证：本仓 clang 24 实测
    `--target=wasm64-unknown-unknown -c` **通过** ⇒ 不是我们缺工具。
  · **R2**：产物真名不是 `omc.wasm`，是 **`OpenModelicaCompiler_bg.wasm`**（wasm-bindgen 出包）。
  · **R3**：一步式配方缺 `SimulationRuntime/c/RuntimeSources.mo`（wasm 模式跳过它的唯一
    生成点，缺了 mmtorust **静默半缺**）⇒ 单独生成器 + 两步链（`gen-runtime-sources-mo.sh`）。
  · **R4**：wasm 路径不需要 OMBootstrapping（Rust 模式直接 `return()`）⇒ pin 表 2 tree + 2 toolchain。

- **动机（实测支撑，来自姊妹仓的查证）**：MATLAB 生态有三根轴 —— ① 语言（`Octave-Full-Wasm`
  已覆盖）、② Simulink 因果块图、③ **Simscape 非因果物理建模（本仓要补的）**。
  实测证据（见 `Octave-Full-Wasm/build/113/NOTES-experiment-omc-wasm.md` §8/§10/§11）：
  · Octave 引擎能解 **index-1 DAE**（RC 电路 V(5)=0.9931 vs 理论 0.9933），
    **不能**解 **index-3**（约束摆 `IDASolve failed`）——而指标约简正是 OM 编译器的活；
  · 两引擎都读写 `.mat`（omc-web 仿真输出就是 MAT4）⇒ **握手格式现成**；
  · OM 官方有**第一方 wasm CMake 目标**（`RUST_OMC_WASM_RUNTIME`、`wasm32-wasip1`、
    `omc.wasm`、产物交接）⇒ 走官方路线，不抄第三方配方。

- **可行性已证（第三方演示实测）**：`BouncingBall.mo` 在真浏览器里跑通
  `parse(381ms) → 生成 C(28ms) → 浏览器内编译(49.57s) → 仿真(50ms) → 出图`。
  **本仓路线**（官方 CMake）走的是另一条：产物 88.7 MB、前端实测全通。

- **本仓对上游 Einfacht 的一处改进**：`zreflect/facts.py` 的数据层模块名从写死改成
  旋钮 `REFLECT_MEASURE_MODULE` ⇒ 「换仓库只换一个文件」这条承诺才真成立。
  （改进过程中被 C4「名录对账」抓到一次**幻影旋钮** —— 已修，见 `docs/EINFACHT-INTEGRATION.md` §4。）

## 关键约定（别混）

- **与姊妹仓平级、互不引用**：工具链不同（emsdk vs **clang 24 + Rust wasm32-wasip1**）⇒ 不互相 submodule；
- **集成点在上游层的 `Octave-UI`**（第三个引擎档），中间用 `.mat`；
- **纯客户端**：不引入任何服务端执行代码的端点。
- **本仓工具链四条硬约束**（首批实测得出，别再踩）：
  · 上游 configure 要 `<clang -print-resource-dir>/lib/wasi/libclang_rt.builtins-wasm32.a`
    —— 系统缺且无 root 装不了 ⇒ **clang24 同源精编 + resource-dir overlay + wrapper**
    （`build/113/provision-toolchain.sh` / `build-clang24-builtins.sh`）；
    ⚠️ overlay 必须用**源** resource-dir 铺（复制过的 clang 会按自身位置推出**不存在的**
    路径 ⇒ include 断链 ⇒ 编译期 `stddef.h file not found`，离根因很远才炸）；
  · Rust 用上游 `rust-toolchain.toml` 钉的 **nightly-2026-05-31**（cargo `codegen-backend`
    与 cranelift-preview 都要 nightly）——**别用别的 nightly**；
  · **`-DRUST_OMC_WASM_OPT=OFF`**（本机 binaryen 是 emsdk 版 133，与上游 `rust_omc.cmake:829`
    的旧 feature 名不兼容 ⇒ 上游自己的 build.rs:801 会 panic；上游原文就给了这个开关）。
    代价**只**是产物偏大（官方 CI 也是 PR 关、发布开）；
  · **构建期下载走代理** `http://127.0.0.1:2080`（实测：`static.rust-lang.org` 直连 19 KB/s、
    代理 7.5 MB/s，快 380×；git 已全局配，cmake 的 `file(DOWNLOAD)` 与 rustup 吃 env 代理）。
- **跑 facts 必须用钩子语境**（`. reflect-hooks/einfacht-env.sh`）：直接跑 `python3 zreflect/facts.py`
  会因 `REFLECT_MEASURE_MODULE` 未加载而**静默回落到上游占位实现**（数 md/py 文件），
  并且把台账写"成功"（值被改口守卫拦下不写）。实测踩过一次。

<!-- AUTO:FACTS -->
> 本区块由 `zreflect/facts.py --render-doc` 从 `FACTS.json` 渲染，**不要手改**（pre-commit 会重算并 `git add`）。
> 正文里的「测出来的数字」只在这里生产：要引用就写 `[[键名]]`，不要手抄数字。

| 键 | 值 | 测于 | 复跑命令 |
|---|---|---|---|
| `docs_present` | **3** | 2026-10-14T16:28:40+0800 | `ls /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/REQUIREMENTS.md /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/EINFACHT-INTEGRATION.md /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/FORK-PIPELINE-AND-LESSONS.md 2>/dev/null | wc -l` |
| `lane_branches_present` | **3** | 2026-10-14T16:28:40+0800 | `git -C /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm branch --list --format='%(refname:short)' | awk '/^(master|wasm32|IllegalPerformance)$/{n++} END{print n+0}'` |
| `om_result_mat_bytes` | **25729** | 2026-10-14T16:28:40+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/BouncingBall_res.mat` |
| `om_result_mat_sha` | `f13495579741d616…` | 2026-10-14T16:28:40+0800 | `sha256sum /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/BouncingBall_res.mat | cut -d' ' -f1` |
| `omc_version_string` | **"-rust"** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['probe'].strip())"` |
| `omc_wasm32_bytes` | **91152188** | 2026-10-14T16:28:40+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web/pkg-nodejs/OpenModelicaCompiler_bg.wasm` |
| `omc_wasm32_rustc` | **1.98.0-nightly** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['tool']['rustc'])"` |
| `omc_wasm32_sha` | `0d9866928e02b2e8…` | 2026-10-14T16:28:40+0800 | `sha256sum /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web/pkg-nodejs/OpenModelicaCompiler_bg.wasm | cut -d' ' -f1` |
| `omc_wasm32_verdict` | **ok** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json')).get('verdict'))"` |
| `omc_wasm32_web_files` | **11** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['measured']['web_files'])"` |
| `omc_web_verdict` | **ok** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-web/omc.build.json'))['verdict'])"` |
| `omc_web_wasm_bytes` | **74579521** | 2026-10-14T16:28:40+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/build/omc-out-web/web/omc/OpenModelicaCompiler_bg.wasm` |
| `omc_web_wasm_sha` | `ea0a9f4f4f4bfe3d…` | 2026-10-14T16:28:40+0800 | `sha256sum /mnt/hdd/openmodelica-wasm-build/build/omc-out-web/web/omc/OpenModelicaCompiler_bg.wasm | cut -d' ' -f1` |
| `samepage_compile_ms` | **242** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['compile_ms_total'])"` |
| `samepage_heap_peak` | **26000000** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['js_heap_peak_bytes'])"` |
| `samepage_octave_bytes` | **29632229** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['octave_wasm_bytes'])"` |
| `samepage_om_bytes` | **74579521** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['om_wasm_bytes'])"` |
| `samepage_sum_bytes` | **104211750** | 2026-10-14T16:28:40+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['sum_wasm_bytes'])"` |
| `toolchain_builtins_bytes` | **117704** | 2026-10-14T16:28:40+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/tools/clang-resource/lib/wasi/libclang_rt.builtins-wasm32.a` |
| `toolchain_clang` | **24.0.0** | 2026-10-14T16:28:40+0800 | `/mnt/hdd/openmodelica-wasm-build/tools/bin/clang --version | head -1 | grep -oE '24\.[0-9]+\.[0-9]+' | head -1` |
| `upstream_pins` | **4** | 2026-10-14T16:28:40+0800 | `python3 -c "import json,sys;d=json.load(open('/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/build/upstream-pins.json'));print(len(d['pins']))"` |
| `whitelist_rules` | **74** | 2026-10-14T16:28:40+0800 | `grep -c '^!' /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/.gitignore` |

22 条事实。
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录（zreflect/registry.py 的声明行）渲染，**不要手改**。
> 执行面（hooks / CI）读 `registry --run <相位>` —— 相位是声明字段（`runs_at`），不是文件名。

| 闸门 | 相位 | 它挡住什么 | 消费的旋钮 |
|---|---|---|---|
| `check_ab.py`（A/B 闸门） | commit | A/B 同旗标不变式（非 allow 轴差异 = 混淆变量，A/B 作废） | `REFLECT_AB` |
| `check_envfile.py`（env 文件闸门） | commit | 守钩子的 REFLECT_* 载体（旋钮 typo / 指向缺失 / 空值） | `REFLECT_ENV_FILE` |
| `check_facts.py`（事实闸门） | commit | 块一致性 / 裸数字 / 坏引用 | `REFLECT_FACTS`, `REFLECT_DOC`, `REFLECT_NAKED_MIN` |
| `check_facts_replay.py`（复跑闸门） | commit | 台账 cmd 逐字复跑（裸值契约：stdout 必须等于值） | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` |
| `check_instruments.py`（仪器生命周期闸门） | commit | 恒常检测（first_seen）+ 被证伪量法登记 | `REFLECT_INSTRUMENTS`, `REFLECT_INSTRUMENT_DAYS`, `REFLECT_FACTS` |
| `check_invariants.py`（不变量闸门） | commit | 声明式不变量：仓库文件必须/不得含某片段（grep 级） | `REFLECT_INVARIANTS` |
| `check_locks.py`（锁定源闸门） | commit | 锁定源清单（URL + 文件 + sha256 的内容指纹） | `REFLECT_LOCKS` |
| `check_pins.py`（pin 闸门） | commit | 派生树 pin 一致性（stamp commit / dirty / 版本串对读） | `REFLECT_PINS` |
| `check_questions.py`（悬案闸门） | commit | 未结案的问题必须挂一个能跑的结算件 | `REFLECT_QUESTIONS` |
| `check_readme_sync.py`（三语 README 闸门） | commit | 语言版本是同一条断言的三份拷贝：结构互链 + 每次推送同批 | `REFLECT_READMES` |
| `check_retractions.py`（翻案重现检测） | commit | 被推翻的断言不许悄悄回来当现状 | `REFLECT_RETRACTIONS`, `REFLECT_DOCS`, `REFLECT_HISTORY_SECS` |
| `check_stale.py`（陈旧断言检测） | commit | sha 出处 / 退役名 / 测龄 | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` |
| `check_world.py`（world 闸门） | commit | 声明式验证对象：多线仓库共享验证环境的世界对账 | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` |
| `doctor.py`（开工预检 doctor） | start-of-work | 进程 / 端口活性（查会死的东西 ⇒ runs_at=start-of-work，不进 pre-commit） | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` |

14 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = 落一个声明行，这里自动长出来）。
<!-- /AUTO:GATES -->


## 需求 B：**已结案**（2026-10-14）

**判据**：`node test/node/accept-omc-simulate.mjs` → 见台账（`[[omc_wasm32_verdict]]` 与
`[[omc_version_string]]` 同批更新）。实跑 = **10 PASS / 0 FAIL**。

- 模型在 wasm 里**跑完**：`LOG_SUCCESS | The initialization finished successfully`，
  `resultFile=/tmp/BouncingBall_res.mat`。
- 结果 **25,729 字节 MAT4**，从 wasm VFS 取出并落盘宿主（`/tmp/omc-BouncingBall_res.mat`；
  供需求 D 的 Octave 握手）。
- **数据是真物理**（深验）：`h` 从 1.0 按 `der(v)=-g, der(h)=v` 衰减，500 点齐全
  （min −0.9556 / max 1.0000，含 `when h<=0 reinit` 弹跳）。
- 根因与修补全过程：悬案 `.scratch/open-questions/issues/03-simulate-needs-host-solver.md`
  （状态 `resolved`）。

**下一步 = 需求 D**（`.mat` 与 Octave 引擎握手）：结果文件已能落盘，
缺的是"喂进 Octave 引擎 `load` 通 + 数值合理"的端到端与反向断言。

## ★ 下次开工第一件事（2026-10-13 关机前留）

1. **重建**：`bash build/113/build-omc-wasm.sh build`（`--verify` 之后）。
   需求 B 的根因修补**已实测生效**（新 runtime blob `df866d92…`，`env.rt_host_lin_solve`
   导入 **1 → 0**），但产物要在 stage2 收尾后重新 `--verify`。
2. **验收**：`node test/node/accept-omc-simulate.mjs`（现在实测 6 PASS / 3 FAIL —— ③④ 是仿真那几条）。
3. ⚠️ **踩过的坑（别重犯）**：清 stage2 陈旧 blob 时**只删** `rust-target/.../openmodelica_wasm_jit-*/out`
   里那个 `runtime_wasip1_interactive.wasm`，**别 `rm -rf` 整个 `Compiler/wasm-blobs/`** ——
   那目录同时是 liblapack/libc_pic/ModelicaUtilities 的**生产出口**，删了会撞上
   ninja 的复制竞态（`Error copying file …: No such file or directory`）。
4. ⚠️ **用户点令（2026-10-13）**：构建**必须用 ccache**（上游默认也是 ON：`CMakeLists.txt:172`），
   **优先 LLVM 工具**。本批曾图快写 `OM_USE_CCACHE=OFF` —— 已改回 `ON` 并显式
   `-DOM_COMPILER_CACHE=ccache`；下次用 `ccache -s` 验命中率。

## `IllegalPerformance` 线开工（2026-10-14，用户点令第三步）

- **wasm64 卡在上游，两条同时缺**（如实记，不是"还没做"）：
  ① 上游 CMake 无 wasm64 路径（`check-wasm64-upstream.sh` → `NOT-YET`，悬案 02）；
  ② **Rust 侧没有 `wasm64-unknown-unknown` target** ⇒ 编译器主体（Rust cdylib）编不成 wasm64。
  姊妹仓的 `-sMEMORY64=1` 是 Emscripten **C/C++** 路径，**根因不同、不能照搬**。
- **本线先把基线与判据立起来**（新件 `build/113/ilperf-baseline.sh`，4 条自证，只读）：
  产物 74,579,521 字节 / **SIMD 5876 处 + post-MVP 23,451 处**（**已在**，不是待做项）/
  features 九项 / memory 导入导出 0/1。
- **性能候选按姊妹仓 §5 纪律推进**（A/B 差分门 + 变异自证；负判决也是资产；
  **不许改默认档**）：换分配器（有效）/ 换 BLAS（有效，配 IEEE 红线）/
  libm（负判决）/ 热点定位（仪器，不猜）。

## 同页集成（wasm32）+ 产物压缩（2026-10-14，用户点令）

- **★ 同页已实现**：`site/samepage.html` —— 两个 wasm 引擎（omc + Octave）在**同一页面**里跑，
  页内完成 `.mat` 握手（omc 产出 → Octave 读出 `VARS time_2,h,v,der_h_,der_v_,e_2,g` /
  `N 628` / `HMAX 1.0000`）。判据 `sh test/browser/run-samepage.sh` → **8 PASS / 0 FAIL**；
  同页 JS 堆峰值见台账 `[[samepage_heap_peak]]`，两引擎 wasm 合计 `[[samepage_sum_bytes]]`。
- **★ R6 翻案**（`build/retractions.json` 的 `R-R6-1`）：早先"同页当前不可行"是**测量方法的错**
  （base64 把 91MB 放大成 ~122MB JS 字符串）——改用 `WebAssembly.compileStreaming` 后，
  91.4MB 模块 **219ms** 编译完、堆峰值 23–28MB。
- **★ 产物压缩**：`-Oz` 把 web 档 omc **91,423,608 → 74,579,521 字节（−18.4%）**，约 69s，
  导出/导入面逐名不变，两条浏览器验收仍全绿。已接进 `build-omc-wasm.sh`（`WASM_OPT=ON` 时跑）。
  ⚠️ 另一处误判已更正：binaryen 133 **认**上游旗标，早先的失败是我**漏给整套旗标**。
- **wasm64 边界加硬**：不仅上游 CMake 无路径（悬案 02），**Rust 侧也没有 `wasm64-unknown-unknown`
  target** ⇒ 编译器主体编不成 wasm64；姊妹仓的 `-sMEMORY64=1` 是 C/C++ 路径，**不能照搬**。

## 需求 B / E：**均已结案**（2026-10-14）

- **B（页面内端到端）**：判据 `sh test/browser/run-omc-page.sh` → **10 PASS / 0 FAIL**。
  用 **web 档产物**（`MODE=web-release` 构建，见台账 `[[omc_web_wasm_bytes]]` / `[[omc_web_verdict]]`）
  + 本仓站点（`build/promote-site.sh` 受管辖入口发布、`build/serve-coi.py` 带 COOP/COEP 服务）。
  实测：页面内 `loadFile → true`、`simulate` 出 MAT4；判据是**把字节搬到 Node 侧再解析**
  （6 矩阵 / `data_2` 5×628 / `name` 7 列），不是页面自报。B3 反向（语法错模型）给可读错误。
- **E（MATLAB 语义桥）**：判据 `sh test/browser/run-omc-bridge.sh` → **11 PASS / 0 FAIL**（真 Octave 引擎）。
  实测：`omc_simulate_model('BouncingBall')` ⇒ **628×7 数据矩阵**（数值对）；
  未知模型 / 未支持命令**都明确报错**。
- **★ 两处形态与需求书原文不同（都实测逼出来的，记进 §7）**：
  · **R7**（B）：web 档是 wasm-bindgen **ESM** —— `omc_*` 是具名导出，`default` 是**初始化函数**
    （不是模块对象）；且 web 档**没有** `omc-cli.js`（那是 node 档的）⇒ `--verify` 已档位感知。
  · **R8**（E）：桥必须**两段式**（`.m` 提交即返回、宿主驱动）——
    `.m` 侧忙等会与宿主**互等死锁**（实测 Octave 忙 3s 时宿主 evaluate 阻塞 2701ms）；
    `pause()` 在本 build 里更会把 evaluate 挂死。另：两个 wasm 的 FS **互不可见**（桥搬字节）；
    Octave 必须跑站点 **worker 模式**（主线程留给桥）；worker 的 `eval` 返回值**不含结果**
    （取值走 DOM `#output`，大块内容 base64 分块）。

## 需求 D：**已结案**（2026-10-14）—— `.mat` 握手打通

**判据**（三条实跑）：`sh test/browser/run-mat-handshake.sh` → **14 PASS / 0 FAIL**；
`sh test/browser/selftest-mat-bridge.sh` → **8 PASS / 0 FAIL**；
`bash build/113/measure-samepage-cost.sh` → rc=0（D4 的量）。

- **握手点不是 `load`，是语义映射**（实测）：Octave 的 `load` **认** OM 的 MAT4
  （返回 struct：`Aclass`/`name`/`description`/`dataInfo`/`data_1`/`data_2`）但**不产生** `h`/`v` ——
  变量名在 `name` 矩阵的列里、时间序列在 `data_2` 的行里。⇒ 本仓 `bridge/omc_mat_load.m`
  做这层映射（读取 + 名字消毒 + 元信息），并**主动处理**两类真语义：
  `dataInfo` channel 0 = 独立变量 `time`；参数走 `data_1`（channel 1）。
- **输入端可复跑**：`node test/node/produce-result-mat.mjs` 跑真仿真 →
  从 wasm VFS 取件 → 落 `artifacts/BouncingBall_res.mat`（见台账 `[[om_result_mat_bytes]]`）。
- **D4（同页成本）实测 = 当前不可行**（如实记）：wasm 合计
  `[[samepage_sum_bytes]]` 字节；Octave 模块可编（堆 `[[samepage_heap_peak]]`），
  **OM 模块一编译整页崩**。⇒ 悬案 04 `ready-for-human`（惰性/缩产物/分 Worker 三选一，
  留给决策；本仓只做了"量"）。
- **只读纪律**：对姊妹仓**零写入**（只借 harness 的 node_modules 与 8761 站点只读访问）。

## ★ 本次开工修掉的两个坑（2026-10-14，已闭环，留档免得重犯）

1. **stage2 的 `--target install` 曾没落盘**：昨天 `web/` 一包是旧字节、
   `stage2/…/web/pkg-nodejs/` 是新字节（两份"真相"）。今天续建到 install 完成后
   **已验证同步**（产物 sha 与身份证一致，见台账 `[[omc_wasm32_sha]]`）。
2. **漏 blob（我昨天 `rm -rf Compiler/wasm-blobs/` 的后果）**：`libc_pic.wasm` /
   `ModelicaUtilities.wasm` 是 `openmodelica_wasi_libc` 的 build.rs 经 `OMC_WASM_BLOB_OUT`
   汇出的，而 cargo 判定"无需重跑" ⇒ 副本没回来（`Error copying file …: No such file or directory`）。
   **救法**：从该 crate 的 `OUT_DIR` 取回（cargo 缓存还在）。
   **教训**：清产物**只删要删的那个文件**，别删共享输出目录。
