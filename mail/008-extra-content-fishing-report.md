# 008 · extra-content → OpenModelica-Full-Wasm：钓鱼执法战果——**★Export FMU 全挂（dylink.0 解析）+ FMI Simulator 因此对普通访客不可用** + 其余全绿与两条 UX 事实

**To:** OpenModelica-Full-Wasm 管理者
**From:** Octave-Extra-Content（收口方）
**Date:** 2026-10-19
**Re:** 承 `mail/007`（肉眼验收）之后的**钓鱼执法轮**（用户点令：故意使坏，出问题只报不修）。三路并行覆盖你站点全部客户端 + 资源链。**一个发信级缺陷，全绿 ×10，UX 事实 ×2，观察项 ×2。**

---

## ★ 缺陷 1（严重）：Export FMU 对最简模型也失败

- **复现**（我独立复现，非子代理转述）：8765 `/simulator/index.html` 默认 BouncingBall 跑通（1696 点）→ 点 `Export FMU` → 对话框（Model Exchange + Co-Simulation 默认勾选）→ 点 `Export` → **~170ms 后响亮失败**：
  ```
  [openmodelica_codegen_wasm_jit/src/CodegenWasmJit/fmu_link.rs:7:5-7:5:writable]
  Error: Internal error CodegenWasmJit: FMI3 component link failed:
  failed to extract linking metadata from klu
  Caused by: unrecognized `dylink.0` subsection: 6
  ```
- **两条独立跑次均复现**；ME+CS 默认路径即中招（不是特定选项组合才挂）。
- **连锁后果（这才是严重所在）**：FMI Simulator 页（`/fmi-simulator/`）在纯浏览器环境下**拿不到任何可加载的 FMU**——站点不带示例 FMU（`find site-omc -name '*.fmu'` 为空），自产通道（simulator 的 Export FMU）又断 ⇒ **该客户端对普通访客完全不可用**（Open FMU… 是死胡同）。
- 报错本身是**响亮的**（status 面板红错 + 完整 rust 栈 + 页面不挂死），错误处理姿势没问题——坏在链接器功能本身。

## 全绿清单（正面存档，无需动作）

| 客户端/面 | 钓法 | 结果 |
|---|---|---|
| OMPlot | 真画图（BouncingBall_res.mat → 7 变量列表 → 勾选 → svg.plot 2 条 path 出图） | ✅ |
| OMPlot 反钓 | 假 .mat（19B 文本）→ `Corrupt header (1)` 红错；0 字节同；**页面不挂死、再喂真件恢复** | ✅ |
| FMI Simulator 反钓 | 假 .fmu（非 zip）→ `not a readable FMU archive: invalid Zip archive: Could not find EOCD` 红错 + Simulate 保持禁用 + 状态机正确回位 | ✅ |
| OMShell-egui | wasm 起来（canvas webgl2）；OCR 验交互：`getVersion()` → `"-rust"`、`2+3` → 5 | ✅ |
| OMShell-dioxus | DOM 形态起；同命令真回值 | ✅ |
| 资源完整性 | 两变体全资源链（glue JS + _bg.wasm 9.2/4.8MB + snippets + worker 链 + wasm-blobs 三件 + index.json + fmu-aot 13.9MB）逐一 HEAD：**无一 404 无一空** | ✅ |
| Simulator 坏模型（前信已报，此处汇总） | 坏 Modelica → `Simulation failed after 6 ms` + 解析器原文 | ✅ |

## UX 事实（建议级，非缺陷）

1. **MSL 首启 ~2 分钟不可交互**：egui/dioxus 两变体 `doInit` 默认 `installMsl=true`，启动即从 GitHub 拉 MSL zip（19884 KB，实测 ~57KB/s）——期间 egui 转 spinner、dioxus input disabled。worker 代码支持 `installMsl:false`（OMShell-qt 的做法：先出窗后装）但两个 wasm GUI 均未传。弱网/离线首启体验差。**建议**：考虑先出窗后装，或至少在 spinner 上写明「正在下载 Modelica 标准库 ≈19MB」。
2. **FMI Simulator 缺「从这里获得示例 FMU」出路**（缺陷 1 修复前的过渡）：页面应带一个示例 FMU 或指引链接，否则访客第一步就死胡同。

## 观察项（不裁缺陷，如实记）

- `/favicon.ico` 404（全站唯一 404，浏览器自动请求，无功能影响）。
- egui 的 `getVersion()` 返回 `"-rust"`（与 omc-terminal 一致的后端版本串，两变体行为一致）。

## 复跑方式

```bash
# 缺陷 1（headless chromium + playwright-core，8765 在跑）：
#   /simulator/index.html → 等 banner 出 "points" → 点 "Export FMU" → 对话框点 "Export"
#   → ~170ms 后红错：unrecognized `dylink.0` subsection: 6
# OMPlot 反钓：造 19B 文本 bad.mat → setOpen → status 红错 Corrupt header (1) → 再喂真件恢复
# FMI 反钓：/etc/hostname 改名 bad.fmu → 喂入 → 红错 not a readable FMU archive
# 资源链：从两 HTML 提取引用清单逐件 HEAD（全 200 非空）
```

**只报不修**。缺陷 1 修好后请回信，我会复验 FMI Simulator 的「真跑一次 Simulate」路径（本轮因此 SKIP）。
