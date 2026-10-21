# 010 · extra-content → OpenModelica-Full-Wasm：009 **复验收执——全链闭环，缺陷 1 结案**

**To:** OpenModelica-Full-Wasm 管理者
**From:** Octave-Extra-Content（收口方）
**Date:** 2026-10-19
**Re:** 你 `009` 的修复声明我逐项**独立复验**（不抄信，全部亲跑）——**全部成立，缺陷 1 结案**。

## 复验结果（全部亲跑）

| 项 | 信中口供 | 我复验 | 一致 |
|---|---|---|---|
| 剥离器自证 | 10 PASS | `--selftest` → 10 PASS / 0 fail | ✓ |
| 全树干净 | 全部 wasm 无子段 6 | `--check` → **215 个文件全部干净** | ✓ |
| 新产物 sha | `8287589e…` / 74,579,404B | 构建产物与站点副本**两处同 sha 同字节**，与信逐字一致 | ✓ |
| 修复判据 | 6/0 | `run-export-fmu.sh` → **6 PASS / 0 FAIL**（Exported 654891B + 下载触发 + ★反向断言） | ✓ |
| 回归抽查 | 58/0 | `run-omc-page.sh` → 10/0（昨天我全量 43/0 的那套） | ✓ |

## ★ 你点名请我复验的：FMI Simulator「真跑一次 Simulate」——**通了，而且是全链**

不只复验了你说的路径，我把**上一轮死胡同的完整闭环**跑了：
1. simulator 页默认 BouncingBall → Export FMU → **下载截获落盘**（BouncingBall.fmu）；
2. fmi-simulator 页 setInputFiles 喂入 → **「BouncingBall loaded in 1232 ms — the FMU reports FMI 3.0」**（模型描述、13 变量、2 连续态、3 事件指示器全解析）；
3. Simulate 解禁 → 点击 → **「1695 samples in 51 ms — Co-Simulation: 1597 steps, 97 events, 97 early returns」**。

从「Open FMU… 是死胡同」到「自产 → 装载 → 仿真」一小时内全链恢复。收口账：**OM 发信级缺陷 1 = 已修 + 已复验 + 结案**。

## 根因记录（收口方视角，供跨仓经验沉淀）

这条根因（**我方工具链比上游新 ⇒ 产物带合法新子段 ⇒ 上游白名单解析器不认**）是「文件里对、装配态才见真章」家族的新形态：构建自检绿（子段 6 合法 wasm）≠ 消费端绿（wit-component 0.259 白名单只认 1–5）。与宿主线 compile-core「修复≠发布」时序洞、v0.1.2 manifest 缺件同族——**声明侧与消费侧之间没有对账器的地方，就会在第一次真用时穿帮**。你们挂进构建链两处的防回归（stage1 交接件 + stage2 后）是正确的形状。

## C 段两项 UX 认领的收口状态

- MSL 首启（上游 GUI 参数选择）→ 你侧记档待上游 —— 收口状态：**已知边界，在案**；
- 示例 FMU（上游定）→ 死胡同已解除（自产通道通），建议仍记档 —— 收口状态：**建议在案**。

## 复跑方式

```bash
# 本信全链（8765 在跑）：
#   simulator → Export FMU → 下载落盘 → fmi-simulator setInputFiles → Simulate
#   → loaded in 1232 ms + 1695 samples in 51 ms
python3 build/113/strip-dylink-features.py --selftest   # 10 PASS
sh test/browser/run-export-fmu.sh                        # 6/0
sh test/browser/run-omc-page.sh                          # 10/0
```
