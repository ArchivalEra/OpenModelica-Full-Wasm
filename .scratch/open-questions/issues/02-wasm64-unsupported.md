# 02 · master 线要的 wasm64：上游没有（需求书 C1 与实测冲突）

**Status:** ready-for-agent
**Settling:** `bash build/113/check-wasm64-upstream.sh` —— rc=0 ⇒ 上游已有 wasm64 支持
（**结案**：master 线可开始出 wasm64 产物）；rc=1 ⇒ 仍无支持（悬案继续，这是"还没到"不是失败）；
rc=3 ⇒ 上游树不在（环境问题，不是结论）。

## 背景

需求书 C1（沿用姊妹仓用户点令 2026-10-12）写：`master` 线 → 产物 **wasm64**，只编 wasm64。
2026-10-13 首批构建（需求 A）前实测：**上游 OpenModelica 的 wasm 面零 wasm64 支持**。

## 已查证（不是猜）

- `OMCompiler/Compiler/.cmake/rust_omc.cmake`（2312 行）grep `wasm64`：**0 命中**
  （同期 `wasm` 命中 469 次，管道有效）；`memory64` 5 处命中全是 **`memory64: false`** 的显式关闭；
- 上游 `rust-toolchain.toml` targets 只钉 `wasm32-unknown-unknown` + `wasm32-wasip1`；
  `.cargo/config.toml` 只有这两个 target section；
- 上游 GitHub code search `wasm64 repo:OpenModelica/OpenModelica` → total_count=0；
- **旁证（C 侧能编，卡在上游）**：本仓 clang 24 实测 `--target=wasm64-unknown-unknown -c` **通过**
  ⇒ 硬件/工具链不是瓶颈，缺的是上游 CMake 目标与 Rust target 面。

## 未决

- 上游何时（或是否）会加 wasm64 —— 无法预测；结算件每次跑都会如实报（加支持即翻面）。
- **本仓替代路线**：`wasm32` 线先出产物（官方唯一支持档）；`IllegalPerformance` 线的
  性能工作（SIMD/多线程/优化库）不依赖 wasm64，可先行。
