# Release · v0.1.0-wasm32（codename first-light）

**发布线**：`wasm32`（本仓当前唯一发布的档；`master` 线的 wasm64/多线程目标卡上游
——悬案 02，结算件 `build/113/check-wasm64-upstream.sh` → NOT-YET）。
**版本身份证**：`build/VERSION.json`（数字不手抄，台账键为准：`build/FACTS.json`）。

## 这个版本是什么

OpenModelica 官方 CMake wasm 目标（`OM_OMC_WASM=ON`，Rust 路线）编出的浏览器端
Modelica 引擎 —— **纯客户端计算**（零服务端执行端点），wasm32 档，**不需要 COI 头**
（产物 0 原子指令 / 0 线程导入 / 0 共享 memory ⇒ 普通静态托管即可跑）。

已含能力（六条需求里的 A/B/D/E + 同页 + 压缩）：

| 能力 | 验收判据（可复跑） |
|---|---|
| 官方目标构建出产物 | `bash build/113/build-omc-wasm.sh --verify` → verdict=ok |
| 浏览器内建模→仿真→`.mat` | `sh test/browser/run-omc-page.sh` → 10/0（**无 COI 实测**） |
| 与 Octave 引擎 `.mat` 握手 | `sh test/browser/run-mat-handshake.sh` → 14/0 |
| MATLAB 语义桥 `omc_*` | `sh test/browser/run-omc-bridge.sh` → 11/0 |
| 两引擎同页 | `sh test/browser/run-samepage.sh` → 8/0（**无 COI 实测**） |
| Node 侧 | `sh test/node/run.sh test/node/accept-omc-getversion.mjs` → 9/0 |

## 产物与指纹（值以台账 `build/FACTS.json` 为准）

| 产物 | 台账键（字节 / sha256） |
|---|---|
| web 档 `omc/OpenModelicaCompiler_bg.wasm`（浏览器用，已 `-Oz` 压缩） | `omc_web_wasm_bytes` / `omc_web_wasm_sha` |
| node 档 `pkg-nodejs/OpenModelicaCompiler_bg.wasm`（E/Node 用） | `omc_wasm32_bytes` / `omc_wasm32_sha` |

上游 pin：`openmodelica` @ `cbff5eb7`（master）、`omcompiler-3rdparty` @ `ae7e482a`
（同 stamp，`witness-upstream-pin.py` 每提交核对）。工具链：clang 24.0.0（55ea1f4）
+ rustc 1.98.0-nightly（nightly-2026-05-31）。

## 架构纯度

一线一架构：全站点（宿主 + 13 附属 wasm 模块）**全部 wasm32**，无任何 wasm64 产物
（`build/113/check-lane-purity.py --lane wasm32` → OK）。

## 已知边界（如实记）

- **无 COI 时降级的增强面**：`omc_enable_cancel_poll` / `omc_enable_progress_sink` /
  `omc_enable_fmu_aot`（要 SharedArrayBuffer 控制块）；主链路不受影响。
- **wasm64 / 多线程未发**：上游 `rust_omc.cmake` 无 wasm64 路径、无运行期线程路径
  （`RUST_OMC_THREADS` 是编译期并行）。上游接路径后按悬案 02 翻面。
- **MSL 不在产物里**：产物嵌的是语言内建（`ModelicaBuiltin.mo` 系）；首个 import MSL 的
  模型落地时才按 content-list 端口出表（见 `mail/002`）。
- **同页只在桌面 chromium 验过**；移动端未测。

## 复跑（一切数字的出处）

```bash
bash build/113/build-omc-wasm.sh --verify          # verdict=ok
sh test/browser/run-omc-page.sh                    # 10/0（可换无 COI 服务实测）
sh test/browser/run-samepage.sh                    # 8/0
python3 build/113/check-lane-purity.py --lane wasm32 --host <site>/omc/OpenModelicaCompiler_bg.wasm --mod <site>/**/*.wasm…
```
