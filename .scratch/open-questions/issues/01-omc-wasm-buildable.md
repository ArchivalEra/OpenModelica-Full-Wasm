# 01 · 官方 CMake wasm 目标能不能在本机 build 出 omc.wasm

**Status:** ready-for-agent
**Settling:** `bash build/113/build-omc-wasm.sh --verify` —— rc=0 ⇒ 构建成功（Node 里
`omc_eval('getVersion()')` 返回版本串）；rc=1 ⇒ 构建失败（脚本打印卡在哪一步）；
rc=3 ⇒ 环境问题（Rust/wasi target 没装），不是结论。**结算件尚不存在** —— 本工单的
第一交付物就是造它（`docs/REQUIREMENTS.md` 需求 A 已写明判据）。

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

## 未决

- 官方 CMake 目标的**实际构建时长与磁盘占用**未知；
- 它产出的 `omc.wasm` 的**求解器覆盖**未知（第三方路线实测只有 Euler/RK/dassl，
  官方路线未测）。
