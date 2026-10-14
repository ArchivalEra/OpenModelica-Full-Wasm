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

## ★★ 2026-10-14（同日）**更正**：Rust 侧**能**编 wasm64 —— 我上一条查错了地方

> **错在哪**：我写"Rust 侧没有 wasm64 target"，依据是 **`rustup target list`** ——
> 那是**"可安装"列表**，**不是编译器内置目标表**。
>
> **实测（可行件 `build/113/build-w64-spike.sh`，5 条自证）**：
> · `rustc --print target-list | grep wasm64` → **`wasm64-unknown-unknown` 在内**；
> · 裸编报 `can't find crate for core`（该目标无预编译 std）；
> · **`cargo build --target wasm64-unknown-unknown -Zbuild-std=core,alloc`** ⇒
>   **8.8 秒编出 wasm64 产物**；Node 实例化成功（`add64(2n,3n)=5` —— 参数是 BigInt
>   正是 64 位地址空间的特征）；
> · **本仓纯度闸门认出档 = wasm64**（memory64 标志判据），且 **wasm32 产物喂 wasm64 档
>   正确地红了**（反向断言 rc=1）。
>
> ⇒ **更正后的结论**：wasm64 在**工具链侧可做**（`-Zbuild-std` 就够了）；
> 缺的只是**上游 CMake 路径**（`rust_omc.cmake` 0 命中 wasm64）——
> 即"上游还没把它接进构建系统"，**不是"编不出来"**。
>
> **本悬案的结案条件因此收窄为一条**：上游 CMake 出现 wasm64 路径（② 已由本仓可行件证明可行）。

## ★ 2026-10-14 我上一条**错误**的证据（保留作教训）：以为 Rust 侧没有 wasm64 target

- `rustup target list`（稳定通道与 `nightly-2026-05-31` 都查了）**没有 `wasm64-unknown-unknown`**
  ⇒ OM 编译器主体（`libopenmodelica_compiler` 是 **Rust cdylib**）**无法编成 wasm64**。
- 对照姊妹仓（`doc/LANES-AND-MEMORY-MODEL.md` §4）：它能出 wasm64 是因为
  **Emscripten 有 `-sMEMORY64=1`（C/C++ 路径）** —— 本仓是 **Rust + CMake** 目标，
  **根因不同、不能照搬**。
- ⇒ 本悬案的结案条件因此要**两条同时满足**：① 上游 CMake 有 wasm64 路径（本仓结算件查的这条）；
  ② **Rust 侧出现 `wasm64-unknown-unknown`（或等价的 memory64 目标）**。
  （结算件 `check-wasm64-upstream.sh` 目前只查 ①；等 ① 翻面时把 ② 一并纳入。）

## 未决

- 上游何时（或是否）会加 wasm64 —— 无法预测；结算件每次跑都会如实报（加支持即翻面）。
- **本仓替代路线**：`wasm32` 线先出产物（官方唯一支持档）；`IllegalPerformance` 线的
  性能工作（SIMD/多线程/优化库）不依赖 wasm64，可先行。
