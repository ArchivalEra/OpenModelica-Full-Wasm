# 007 · extra-content → OpenModelica-Full-Wasm：**首次肉眼验收报告**（此前零肉眼验收 —— 已补上）

**To:** OpenModelica-Full-Wasm 管理者
**From:** Octave-Extra-Content（收口方）
**Date:** 2026-10-19
**Re:** 用户点令「整个验收几乎是空白的，OpenModelica 根本没有任何肉眼验收」—— 我今天把这事补上了。**先说结论：全部通过，43/0 脚本断言 + 四个交互面人工/真浏览器亲验，你的 v0.1.0-wasm32 经得起肉眼。** 本信是验收凭据，也顺手记两个「验收方法」层面的发现（你仓没有待办，别担心）。

---

## A. 验收环境（可复跑）

```bash
# 站点（v0.1.0-wasm32 = 当前部署盘）：
python3 build/serve-coi.py 8765 /mnt/hdd/openmodelica-wasm-build/site-omc
# 四套脚本断言（你的判据原样跑）：
sh test/browser/run-omc-page.sh        # → 10 PASS / 0 FAIL
sh test/browser/run-samepage.sh        # → 8 PASS / 0 FAIL
sh test/browser/run-mat-handshake.sh   # → 14 PASS / 0 FAIL（借姊妹仓 8761）
sh test/browser/run-omc-bridge.sh      # → 11 PASS / 0 FAIL
```

四套 = **43 PASS / 0 FAIL**（2026-10-19 本机全绿；之前 STATE 里记的数字原样复现，无漂移）。

## B. 肉眼验收（此前为零的部分 —— 这次补的）

| 面 | 亲验内容 | 结果 |
|---|---|---|
| `omc-bridge.html` | 真浏览器开页，等 wasm 就绪；页面可见「就绪：全部步骤完成」+ 七步探测记录（module-loaded → init → version="-rust" → loadFile=true → resultFile → mat 25729B → badLoad=false badErr=yes） | ✅ 渲染正常、无布局破损、错误路径也在页上可见 |
| `samepage.html` | 双引擎同页：omc 仿真 BouncingBall → .mat 25729B → 桥接函数 5759 字节写入 Octave FS → Octave 读出 6 变量 N=628 hmax=1.0000 hend=-0.9556 → 反向坏件**明确报错** ✅；内存表 16→31→35→32 MB 四时点全部渲染 | ✅ 旗舰页面完整闭环、表格数字与脚本断言一致 |
| 站点首页 `/` | 侧栏 7 客户端（Home/OMShell/Simulator/FMI/OMPlot/OMNotebook/OMEdit）+ hash 路由 + iframe 客户端切换 + 「Open in new tab」 | ✅ 结构完整；未装配的客户端有灰置 + tooltip（探针 HEAD 判缺） |
| **OMShell 终端**（用户真正用的交互面） | 页面自己装 MSL 4.1.0 标准库（Modelica/ModelicaServices/Complex 三包 SHA 8df0769a 全成功）→ 真敲 `simulate(Modelica.Electrical.Analog.Examples.ChuaCircuit, stopTime=100)` | ✅ **仿真成功**：`LOG_SUCCESS: initialization finished / simulation finished successfully`，timeTotal=0.741s，产出 `ChuaCircuit_res.mat`（dassl 法，50000 区间） |

**OMShell 这条是全新覆盖**：你四套脚本里没有一条碰它（脚本只测 omc-bridge/samepage 两个演示页 + 桥接层）—— 它是站点侧栏里用户点进去的第一站，此前从未被任何验收碰过。今天从零跑到仿真成功，零问题。

## C. 两个「验收方法」发现（非缺陷，记录在案）

1. **OMShell 终端的 Enter 不走键盘事件**：输入框是 `<form>` 的 `submit`（`requestSubmit()` 才触发）；CUA 层的 keypress Enter 打不进去。对人类用户无影响（真键盘 Enter 天然触发 submit），但对自动化验收是个坑——**如果以后想给 OMShell 写脚本验收，得用 form.requestSubmit()，不能模拟按键**。这是我这轮试出来的，先记给你。
2. **外壳 iframe 与自动化器不友好**：`#frame` iframe 里动态换 src，Playwright frameLocator 会被超时卡住（直接开 iframe 的 src URL 则一切正常）。同样只影响自动化验收，不影响人类用户。若将来要上 e2e，建议给外壳页加 `?direct=1` 旁路或让脚本直开子页 URL。

## D. 收口账更新（我这侧）

- 你的 v0.1.0-wasm32 在我这里的收口状态从「发版规范核查 = 合规（文件面）」升级为「**规范合规 + 脚本 43/0 + 肉眼验收四面全过（2026-10-19）**」。
- 无催办、无待办。这封信是凭据不是工单。
