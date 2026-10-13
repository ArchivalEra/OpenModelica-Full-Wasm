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
| `docs_present` | **3** | 2026-10-13T22:37:48+0800 | `ls /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/REQUIREMENTS.md /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/EINFACHT-INTEGRATION.md /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/FORK-PIPELINE-AND-LESSONS.md 2>/dev/null | wc -l` |
| `lane_branches_present` | **3** | 2026-10-13T22:37:48+0800 | `git -C /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm branch --list --format='%(refname:short)' | awk '/^(master|wasm32|IllegalPerformance)$/{n++} END{print n+0}'` |
| `omc_version_string` | **"-rust"** | 2026-10-13T22:37:48+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['probe'].strip())"` |
| `omc_wasm32_bytes` | **88701756** | 2026-10-13T22:37:48+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web/pkg-nodejs/OpenModelicaCompiler_bg.wasm` |
| `omc_wasm32_rustc` | **1.98.0-nightly** | 2026-10-13T22:37:48+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['tool']['rustc'])"` |
| `omc_wasm32_sha` | `eb1f63c66832eb6f…` | 2026-10-13T22:37:48+0800 | `sha256sum /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web/pkg-nodejs/OpenModelicaCompiler_bg.wasm | cut -d' ' -f1` |
| `omc_wasm32_verdict` | **ok** | 2026-10-13T22:37:48+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json')).get('verdict'))"` |
| `omc_wasm32_web_files` | **11** | 2026-10-13T22:37:48+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['measured']['web_files'])"` |
| `toolchain_builtins_bytes` | **117704** | 2026-10-13T22:37:48+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/tools/clang-resource/lib/wasi/libclang_rt.builtins-wasm32.a` |
| `toolchain_clang` | **24.0.0** | 2026-10-13T22:37:48+0800 | `/mnt/hdd/openmodelica-wasm-build/tools/bin/clang --version | head -1 | grep -oE '24\.[0-9]+\.[0-9]+' | head -1` |
| `upstream_pins` | **4** | 2026-10-13T22:37:48+0800 | `python3 -c "import json,sys;d=json.load(open('/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/build/upstream-pins.json'));print(len(d['pins']))"` |
| `whitelist_rules` | **56** | 2026-10-13T22:37:48+0800 | `grep -c '^!' /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/.gitignore` |

12 条事实。
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


## 需求 B 的现状（2026-10-13 深夜，**未结案**）

- **编译器前端在 wasm 里全通**（实测）：`loadFile` true、`getClassNames()` `{BouncingBall}`、
  `translateModel` true（并真的写出模型 wasm）。
- **卡在仿真实例化**：`Import #0 "env" "rt_host_lin_solve": function import requires a callable`
  —— 根因是**交接件里的运行时 blob 是宿主委派版**（stage1 native 编的，带 `host_lin_solve`），
  stage2 按文件名复用了它。证据链与修补见悬案
  `.scratch/open-questions/issues/03-simulate-needs-host-solver.md`。
- **修补已写进构建脚本，但未实测**（关机打断了重建）⇒ 下次开工第一件事：
  跑 `bash build/113/build-omc-wasm.sh build` 重建，再按悬案 03 的 `Settling:` 验收。
  **别把这条当好消息读** —— 它是"更接近了"，不是"通过了"。

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
