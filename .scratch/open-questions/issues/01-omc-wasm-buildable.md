# 01 · 官方 CMake wasm 目标能不能在本机 build 出 omc.wasm

**Status:** resolved
**Settling:** `bash build/113/build-omc-wasm.sh --verify` —— **rc=0（已实跑，2026-10-13 22:31）**。

## ★ 结案（2026-10-13）

- **产物**：`/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web/`
  （`pkg-nodejs/OpenModelicaCompiler_bg.wasm` 88,701,756 字节 + `omc-cli.js` + `wasm-blobs/`），
  身份证 `omc.build.json` **verdict=ok**。
- **判据实跑**：`node omc-cli.js 'getVersion()'` → `"-rust"`（Rust 版 omc 的版本串；构建树无
  git tag ⇒ 走上游 `SOURCE_REVISION=unknown` 降级路径，非空即通过）；
  `test/node/accept-omc-getversion.mjs` 9 PASS / 0 FAIL（含反向断言）；
  `check-lane-purity.py --lane wasm32 --host … --mod ×3` → OK。
- **超出判据的旁证**（如实记，不吹）：`wasi_write_file` 写入 `BouncingBall.mo` 后
  `loadFile` → **true**、`getClassNames()` → **{BouncingBall}** ⇒ 编译器前端全通；
  `simulate()` 停在运行期要宿主 JS 回调（`rt_host_lin_solve`）——**那是需求 B 的活**。
- **代价/限制（如实记）**：`RUST_OMC_WASM_OPT=OFF`（本机 binaryen 与上游旗标不兼容）⇒
  产物**未经 -Oz 优化**、偏大（88.7 MB）；要缩小需装兼容的 binaryen。

## 背景

OpenModelica 官方主仓有第一方 wasm 构建目标（`OMCompiler/Compiler/.cmake/rust_omc.cmake`：
`RUST_OMC_WASM_RUNTIME`、`wasm32-wasip1` 交叉编、`omc.wasm`、产物交接、`wasm-jit` 运行时）。
**这是本仓唯一还有工程未知的一步**。

## 已查证（不是猜）

- 官方目标存在且是 CMake 原生（`RUST_OMC_WASM_RUNTIME` 13 处引用）；
- 需要 Rust + `wasm32-wasip1` target + wasi-libc + wasm-ld（官方注释明说）；
- 本机现状：rastc 1.98.1 / cargo / cmake 4.3.4 / ninja 都在，
  **但没有 `wasm32-wasip1` target**（要 `rustup target add`）；
- 官方 releases **没有预编译 wasm 产物**（只有 `-src-with-submodules.zip`）⇒ 必须自己 build。

## 2026-10-13 首批实测更新（本工单推进中）

- **开关与模式**（读源码得来）：`-DOM_OMC_WASM=ON`（根 `CMakeLists.txt:115-118`，FORCE 打开
  Rust 模式）+ `-DRUST_OMC_WASM_MODE=node-release`（`rust_omc.cmake:1923-1946`）；
  产物 = `OpenModelicaCompiler_bg.wasm` 落 `<build>/OMCompiler/Compiler/web/pkg-nodejs/`；
  官方跑法 `node wasm/omc-cli.js 'getVersion()'`（`OpenModelica.rs/README.md:9-10`）。
- **必须两步链**（本仓实测 + 官方 CI 佐证）：一步式配方缺
  `SimulationRuntime/c/RuntimeSources.mo`（wasm 模式跳过整个 SimulationRuntime 生成它，
  而 mmtorust 源表引用它）⇒ stage1 native configure 生成 → stage2 wasm 包。详见
  `docs/REQUIREMENTS.md` §7 R3。
- **不需要 OMBootstrapping**（R4）：Rust 模式在 `Compiler/CMakeLists.txt:66-71` 直接 `return()`。
- **wasm64 上游零支持**（R1）⇒ 首批产物是 **wasm32**；`master` 线的 wasm64 目标转悬案
  `.scratch/open-questions/issues/02-wasm64-unsupported.md`。
- **环境现实**：本机 docker 不可用（不在 docker 组 + sudo 被 no_new_privs 挡）⇒ 宿主直跑；
  工具链 = clang 24（用户点令）+ 同源精编 wasm32 builtins + Rust nightly-2026-05-31。

## 未决

- 构建时长与磁盘占用（脚本会记进产物身份证与台账）。
- 官方 wasm 目标的**求解器覆盖**（第三方路线实测只有 Euler/RK/dassl；官方路线待实测 —— 本批不测）。
