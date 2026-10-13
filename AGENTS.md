# AGENTS.md · OpenModelica-Full-Wasm

> **接续先读三份**：`maintaince.md`（**方向与地图**，只指方向不抄数字）+
> `STATE.md`（活状态：现在是什么 + 文末机器块）+
> `docs/REQUIREMENTS.md`（**需求书**：要做什么、每条带验收判据）。
> 三条经验文档在 `docs/`：`EINFACHT-INTEGRATION.md`（事实系统接入）、
> `FORK-PIPELINE-AND-LESSONS.md`（**fork 管线与全部经验**）。
> 黑话看不懂就读 `CONTEXT.md`（术语表）。

## 路径铁律
- 仓库：`/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm`（**本仓，private**）
- 姊妹仓（**只读，绝不改**）：`/mnt/hdd/zcode-projects/Octave-Full-Wasm`（Octave 引擎，平级）
- 上游源码/产物：`/mnt/hdd/openmodelica-wasm-build/`（**待建**）
- **禁止**碰课程仓 `/mnt/hdd/zcode-projects/GONGCHENGSHUXUE20260917`

## 三条不可违背
1. **纯客户端计算**：OpenModelica 恒跑在浏览器 wasm 内 —— 禁止任何服务端执行代码的端点。
2. 不 force-push / 不删 git 对象 / 不改历史；**禁用 `--no-verify`**。
3. **白名单仓库**：新增文件必须同步 `!路径` 进 `.gitignore`，否则 pre-commit 直接拒。
   （本仓是 private，但仍用白名单 —— 黑名单是"忘了就提交"，白名单是"忘了就报错"。）

## 这个仓是什么（与姊妹仓的关系）
`Octave-Full-Wasm` = MATLAB **语言**那一侧的引擎（轴 ① 语言 + 轴 ② Simulink 块图）。
**本仓** = **轴 ③（Simscape 非因果物理建模）**的引擎：Modelica 语言 + 符号化 + 指标约简 +
跨域物理库（MSL）。

**两仓平级、互不引用**：
- 工具链不同（姊妹仓 emsdk 6.0.12；**本仓 Rust + wasm32-wasip1**）⇒ **不互相 submodule**
  （混编是明文禁止的失败模式）；
- **集成点在上游层的 `Octave-UI`**（第三个引擎档），中间用 **`.mat` 握手**。

## 线划分 = 一线一架构（沿用姊妹仓用户点令 2026-10-12）

    master 线              → 产物 wasm64，**只编 wasm64**
    wasm32 线              → 产物 wasm32，**只编 wasm32**
    IllegalPerformance 线  → 性能线（SIMD / 多线程 / 优化库）

**判据可执行**：`python3 build/113/check-lane-purity.py --lane <档> --host <wasm> --mod <目录…>`
（① 宿主 ② 车道模块 ③ 站点**本档专属**目录；错档逐条点名、rc=1）。
**为什么成文**：混编的失败模式是"**两边都建成功、自检全绿、运行期才炸**"
（姊妹仓实测三次）⇒ 必须有可执行的判据，不能靠人眼。

## 验收底线
**开发站点永远是最近一次通过浏览器实测的构建。** 新实验失败**不许**让它退化：
失败就丢弃独立车道目录 + 记档 + 继续下一批。

★ **上站候选必须过「全量」才叫候选**：只跑几个"冒烟套件"就发运，曾在全量里炸
（姊妹仓的教训：唯一大量压 `dlopen` 的套件 71/0→44/27）。⇒ 换产物/改线程数/改 GL/改资源
的批次，进件前必须跑一次**全量**（`PROBES=1`）。

## 事实纪律（每句"现在如此"都要能被复跑的命令证明）
**照抄旧话是文档说假话的唯一来源**。五条（详见 `docs/FORK-PIPELINE-AND-LESSONS.md` §5）：
1. **数值/行为只认实测**，复跑方式写在断言旁边；写不出 ⇒ 只能当历史。
2. **口径搬进代码**，别在文档里手抄命令；**"赋值了但没被引用"的旗标会静默失效**
   ⇒ 改旗标组后必须有**从产物里读出来**的自检。
3. **"能编过 ≠ 能用了"**：碰运行期行为必须**浏览器侧**实测。
4. **断言要能证伪**：新契约至少配一条**反向**断言；行为变了就**翻面**（改断言，不改检查器）。
5. **断言有生命周期：实测 / 推断 / 翻案**：活状态只写实测；推断进 NOTES 并注明结案实验；
   被推翻的进 `build/retractions.json`。

## 批次收尾（固定动作，缺一步等于没做完）
★ **开工预检**：每批先跑环境检查（`doctor`）—— 不过就**不开工**。
★ **开发站点只由受管辖入口改**（`build/promote-*.sh`，三件必备 `--dry-run`/`--verify`/`--selftest`，
  且带"不许夹带别的改动"的反向断言）。实验只写独立站点目录。
★ **服务方式**：wasm 多线程档**必须带头**起（`Cross-Origin-Opener-Policy: same-origin` +
  `Cross-Origin-Embedder-Policy: require-corp`）—— 普通 `python3 -m http.server` 发不了这两个头
  ⇒ 线程档**静默**落回基础档（不报错）。
★ **三层 SHA**（磁盘 / HTTP / 页面实例化）不全绿就停 ——"改完程序用老产物跑"是反复踩的坑。
★ **全量回归**（`PROBES=1`）→ **三处一致**（开发站 / 生产站 / 仓库镜像 `--strict`）→ 六道闸门
  → 提交 → 推镜像。

## 提交前（事实系统 = Einfacht 平台 + 本仓专属闸门）
```bash
# 平台层（**执行面唯一产地**；别 glob、别手写清单）：机器块 + 闸门 + 自证
python3 zreflect/facts.py --render-doc STATE.md --check   # 机器块新鲜
python3 zreflect/registry.py --run commit                 # ran/off/failed 三档
sh gates-selftest.sh                                      # 平台闸门自证
# 本仓专属层：白名单 + pin 见证 + 一致性 + 架构纯度
python3 .githooks/check-whitelist.py
python3 .githooks/witness-upstream-pin.py
python3 zreflect/check_facts_replay.py                    # 每条 cmd 逐字复跑
python3 build/113/check-lane-purity.py --selftest
sh build/gates-selftest.sh                                # 本仓专属闸门自证台
```
**★ 闸门自证**：每个闸门必须带 `--selftest`，三类用例齐备：
**正常不报 / 该报的必须报 / 空输入必须报**。新增本仓专属闸门**必须**在
`build/gates-selftest.sh` 名单里登记 —— **名单外的闸门 = 没人盯着的闸门**。
⚠️ **闸门有盲区**：`check-whitelist.py` 只看**已暂存**的文件 ⇒ 新增目录后主动看一眼
`git status --short --ignored <目录>`。

## 操作习惯与硬坑（踩过的，别再来一次）
- ★ **禁止使用 `sleep`**（用户点名）。任何形式都不行。
  **长任务用 `run_in_background: true` 起**（后台任务没有超时），起完就返回、去干别的、
  **等完成通知**；盯已有进程用 `tail -f --pid=<pid>`。
  **已经后台化的任务绝不重跑**（重跑 = 双倍工作 + 两份打架的日志）。
- **重活用 `setsid nohup … &` 起、输出只 `tail -n`/`grep`**；跑验收时**别并行干重活**。
- **测试用例从仓库原路径直跑**，别 `cp` 一份到 harness 再跑（改完仓库用旧副本，断言全错位）。
- **跑测试前先验产物 SHA**（三层）。
- **容器里的构建脚本/源码是另一份拷贝**：改完仓库必须同步进容器，否则跑的是旧的。
- **别猜挂载点/版本号/路径/旗标** —— 一律从产物或配置里**读出来**。
- **探测/自检不许放在开机路径上**：坏产物会让**整页卡死**。探测器按需触发 + 带超时。
- **shell 陷阱**：`pkill -f 'x'` 会匹配自己（用 `'x[y]'`）；`rc=$?` 接管道后拿的是最后一个
  命令的状态；`&&` 放在 `&` 前会把整条链后台化；`echo` 里的反引号会被当命令替换；
  `grep -c` 零命中**退出 1**；正则字符类漏数字。
- 结论只认**产物**：`sha256sum`、日志目录、探针输出；不认印象。

## Agent skills

### Issue tracker
工单是本仓的 markdown 文件，在 `.scratch/open-questions/issues/NN-*.md` 下 —— **本地 tracker**。
每条挂**可跑的结算件**（头部 `**Settling:**` 行）。见 `docs/agents/issue-tracker.md`。

### Triage labels
五个规范角色写成工单头部 `**Status:**` 行（`needs-triage` / `needs-info` / `ready-for-agent` /
`ready-for-human` / `wontfix`）。`wontfix` **不是删除**。见 `docs/agents/triage-labels.md`。

### Domain docs
单上下文：根 `CONTEXT.md`。见 `docs/agents/domain.md`。
