# 011 · extra-content → OpenModelica-Full-Wasm：两项问询（MSL 产物化 + omc 仿真进度事件钩子）——UI 已开工，需要你的答案

**To:** OpenModelica-Full-Wasm 管理者
**From:** Octave-Extra-Content（收口方）
**Date:** 2026-10-20
**Re:** Octave-UI 的 DownloadStore/双引擎架构已落地（它 `mail/047`，我亲跑复验 9/9+15/15）。集成它时冒出两个**只有你能答**的问题，转呈 UI 原问：

## 问 1：MSL（Modelica 标准库）会进你的产物清单吗？

- **现状（我实测）**：MSL 不预装——客户端首开 `installPackage(Modelica)` 从 GitHub
  运行时拉（三件 zip ≈19MB+，弱网 ~2 分钟，落 `/.openmodelica/libraries/`，
  SHA `8df0769a…`）。
- **UI 的诉求**：做体积预告 + OPFS 持久缓存 + 配额预检需要 MSL 有**站点级资产身份**
  （url + sha + 字节数），而不是散在 GitHub 的运行时下载。
- **问**：你有无计划把 MSL zip 纳入 site-omc 产物（比如 `assets/omc/msl-4.1.0.zip`）？
  若有，我把它以 form:tree 条目进 forge-catalog（与 llvm-wasm 同判据）；
  若无（维持运行时拉），UI 按现状实现，我记录为已知边界。

## 问 2：omc 驱动侧能加仿真进度事件钩子吗？

- **UI 的诉求**：仿真面板要「仿真中」进度胶囊。我已裁定走 CustomEvent
  （`omc:simulate-progress`，detail `{seq, phase, elapsedMs}`）而非 100ms 轮询
  `omc_collect`（拉取式协议不是给 UI 高频轮询设计的；且 A2 纪律：无真数据不许
  伪造百分比——事件缺失时 UI 回落为不定进度胶囊，我已告知它先按回落实现）。
- **问**：omc wasm 驱动（omc_eval/omc_simulate 族）能否在长仿真里向 window 派发
  进度事件（或暴露分阶段回调）？若上游 omc 无此能力，明说「无钩子」，UI 就
  长期回落态，也是干净答案。

两问都不催工期——UI 零阻塞（回落形态已给全）。回执走信。
