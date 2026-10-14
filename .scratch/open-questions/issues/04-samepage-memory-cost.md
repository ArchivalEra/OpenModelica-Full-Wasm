# 04 · 两个引擎**同页**的内存/体积成本（需求 D4，如实记的未决项）

**Status:** ready-for-human
**Settling:** `bash build/113/measure-samepage-cost.sh` —— rc=0 ⇒ 量到了（脚本打印两引擎产物字节 + 同页峰值内存估算，写进产物目录的 `samepage-cost.json`）；rc=1 ⇒ 量不到（缺哪份产物就打哪份的名字）；rc=2 ⇒ 环境问题（不是结论）。

## 背景

需求书 D4 原文：「两引擎**同页**的内存/体积成本**未测**（OM ~21 MB + Octave ~29.6 MB）」。
（那 21/29.6 MB 是**第三方演示站**的数字，不是本仓产物。）

## 本仓现状（实测，2026-10-14）

- **OM 档产物体积已测**：`OpenModelicaCompiler_bg.wasm` = **91,152,188 字节**（≈86.9 MiB）
  —— 台账键 `omc_wasm32_bytes`。⚠️ 比第三方演示站那个 ~21 MB 大**四倍多**，因为本产物
  是**官方 wasm-jit 全功能**（含 in-wasm 求解器 + wasm-bindgen 全导出面），
  不是 emception 那条"浏览器内再编一次"的路线。
- **Octave 档体积**：姊妹仓产物（`octave.wasm` ≈ 29.6 MB 是它的公开数字；本仓只读引用）。
- **同页内存峰值**：**未测** —— 需要一个真正把两个 wasm 同时实例化的页面
  （OM 的 86.9 MiB 模块 + Octave 的模块），并采集 `performance.memory` 或
  显式 `WebAssembly.Memory` 统计。

## ★ 已量到（2026-10-14，结算件 `build/113/measure-samepage-cost.sh` rc=0）

产物 `build/omc-out-wasm32/artifacts/samepage-cost.json` 的实测：

| 量 | 值 |
|---|---|
| OM `OpenModelicaCompiler_bg.wasm` | **91,152,188** 字节（≈86.9 MiB） |
| Octave `octave.wasm` | **29,632,229** 字节（≈28.3 MiB） |
| **wasm 合计** | **120,784,417** 字节（≈115.2 MiB） |
| JS 堆峰值（chromium，`compiled` 后） | **81,400,000** 字节（≈77.6 MiB） |

**★ 关键实测发现（这才是本悬案的答案）**：分步实例化时 ——
- Octave 模块：**编译成功**（`WebAssembly.Module.exports` = 710 个导出），堆 81.4MB；
- OM 模块（91MB）：**一编译整页就崩**（`Target page: closed`，连读数都拿不回）。
⇒ **"两个引擎同页"在本机 chromium 上当前不可行**（至少不能都做完整实例化）。
可行方向（未验，供决策）：① 惰性化——同一时刻只实例化当前引擎档；
② 缩产物（本 OM 产物因 `RUST_OMC_WASM_OPT=OFF` 未做 `-Oz`，见需求 A 的 R 记录）；
③ 分开两个 Worker/进程（超出"同页"定义，另议）。

## 未决（留给人的决策）

- 上面三条方向选哪条（这是产品决策不是工程未知）；
- 移动端（内存更紧）是否还有额外限制。

- 同页能否同时在**移动端**浏览器里存活（两模块合计 >110 MB 的 wasm 字节 + 各自堆）；
- 加载顺序/惰性实例化是否必要（只加载当前引擎档？）。

## 明确不做（本仓范围外）

- 不做"同页集成"的**实现**（那在 `Octave-UI` 层，见需求 F）；
  本悬案只要一个**可跑的测量脚本**当结算件。
