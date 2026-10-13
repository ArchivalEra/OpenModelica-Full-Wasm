# STATE · 活状态

正文只写「现在是什么」，**数字一律引用 `build/FACTS.json` 的键**（或看文末机器块）。
方向与地图在 `maintaince.md`；硬规矩在 `AGENTS.md`；要做什么在 `docs/REQUIREMENTS.md`；
历史在 `HISTORY.md`（append-only）。

## 现在是什么（2026-10-13）

- **本仓刚建起来（骨架期，2026-10-13）。** private 仓；三线分支就位；事实系统（Einfacht）
  已接入并通过自证。**还没有任何构建产物** —— `omc.wasm` 尚未 build 过。

- **动机（实测支撑，来自姊妹仓的查证）**：MATLAB 生态有三根轴 —— ① 语言（`Octave-Full-Wasm`
  已覆盖）、② Simulink 因果块图、③ **Simscape 非因果物理建模（本仓要补的）**。
  实测证据（见 `Octave-Full-Wasm/build/113/NOTES-experiment-omc-wasm.md` §8/§10/§11）：
  · Octave 引擎能解 **index-1 DAE**（RC 电路 V(5)=0.9931 vs 理论 0.9933），
    **不能**解 **index-3**（约束摆 `IDASolve failed`）——而指标约简正是 OM 编译器的活；
  · 两引擎都读写 `.mat`（omc-web 仿真输出就是 MAT4）⇒ **握手格式现成**；
  · OM 官方有**第一方 wasm CMake 目标**（`RUST_OMC_WASM_RUNTIME`、`wasm32-wasip1`、
    `omc.wasm`、产物交接）⇒ 走官方路线，不抄第三方配方。

- **可行性已证（第三方演示实测）**：`BouncingBall.mo` 在真浏览器里跑通
  `parse(381ms) → 生成 C(28ms) → 浏览器内编译(49.57s) → 仿真(50ms) → 出图`。

- **下一步（见 `docs/REQUIREMENTS.md`）**：需求 A = 用官方 CMake 目标 build 出 `omc.wasm`。
  这是唯一还有工程未知的一步。**结案判据**：Node 里 `omc_eval('getVersion()')` 返回版本串。

- **本仓对上游 Einfacht 的一处改进**：`zreflect/facts.py` 的数据层模块名从写死改成
  旋钮 `REFLECT_MEASURE_MODULE` ⇒ 「换仓库只换一个文件」这条承诺才真成立。
  （改进过程中被 C4「名录对账」抓到一次**幻影旋钮** —— 已修，见 `docs/EINFACHT-INTEGRATION.md` §4。）

## 关键约定（别混）

- **与姊妹仓平级、互不引用**：工具链不同（emsdk vs **Rust + wasm32-wasip1**）⇒ 不互相 submodule；
- **集成点在上游层的 `Octave-UI`**（第三个引擎档），中间用 `.mat`；
- **纯客户端**：不引入任何服务端执行代码的端点。

<!-- AUTO:FACTS -->
> 本区块由 `zreflect/facts.py --render-doc` 从 `FACTS.json` 渲染，**不要手改**（pre-commit 会重算并 `git add`）。
> 正文里的「测出来的数字」只在这里生产：要引用就写 `[[键名]]`，不要手抄数字。

| 键 | 值 | 测于 | 复跑命令 |
|---|---|---|---|
| `docs_present` | **3** | 2026-10-13T19:22:57+0800 | `ls /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/REQUIREMENTS.md /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/EINFACHT-INTEGRATION.md /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/FORK-PIPELINE-AND-LESSONS.md 2>/dev/null | wc -l` |
| `lane_branches_present` | **0** | 2026-10-13T19:22:57+0800 | `git -C /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm branch --list --format='%(refname:short)' | awk '/^(master|wasm32|IllegalPerformance)$/{n++} END{print n+0}'` |
| `upstream_pins` | **0** | 2026-10-13T19:22:57+0800 | `python3 -c "import json,sys;d=json.load(open('/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/build/upstream-pins.json'));print(len(d['pins']))"` |
| `whitelist_rules` | **48** | 2026-10-13T19:22:57+0800 | `grep -c '^!' /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/.gitignore` |

4 条事实。
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录（zreflect/registry.py 的声明行）渲染，**不要手改**。
> 执行面（hooks / CI）读 `registry --run <相位>` —— 相位是声明字段（`runs_at`），不是文件名。

| 闸门 | 相位 | 它挡住什么 | 消费的旋钮 |
|---|---|---|---|
| `check_ab.py`（A/B 闸门） | commit | A/B 同旗标不变式（非 allow 轴差异 = 混淆变量，A/B 作废） | `REFLECT_AB` |
| `check_envfile.py`（env 文件闸门） | commit | 守钩子的 REFLECT_* 载体（旋钮 typo / 指向缺失 / 空值） | `REFLECT_ENV_FILE` |
| `check_facts.py`（事实闸门） | commit | 块一致性 / 裸数字 / 坏引用 | `REFLECT_FACTS`, `REFLECT_DOC`, `REFLECT_NAKED_MIN` |
| `check_facts_replay.py`（复跑闸门） | commit | 台账 cmd 逐字复跑（裸值契约：stdout 必须等于值） | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` |
| `check_instruments.py`（仪器生命周期闸门） | commit | 恒常检测（first_seen）+ 被证伪量法登记 | `REFLECT_INSTRUMENTS`, `REFLECT_INSTRUMENT_DAYS`, `REFLECT_FACTS` |
| `check_invariants.py`（不变量闸门） | commit | 声明式不变量：仓库文件必须/不得含某片段（grep 级） | `REFLECT_INVARIANTS` |
| `check_locks.py`（锁定源闸门） | commit | 锁定源清单（URL + 文件 + sha256 的内容指纹） | `REFLECT_LOCKS` |
| `check_pins.py`（pin 闸门） | commit | 派生树 pin 一致性（stamp commit / dirty / 版本串对读） | `REFLECT_PINS` |
| `check_questions.py`（悬案闸门） | commit | 未结案的问题必须挂一个能跑的结算件 | `REFLECT_QUESTIONS` |
| `check_readme_sync.py`（三语 README 闸门） | commit | 语言版本是同一条断言的三份拷贝：结构互链 + 每次推送同批 | `REFLECT_READMES` |
| `check_retractions.py`（翻案重现检测） | commit | 被推翻的断言不许悄悄回来当现状 | `REFLECT_RETRACTIONS`, `REFLECT_DOCS`, `REFLECT_HISTORY_SECS` |
| `check_stale.py`（陈旧断言检测） | commit | sha 出处 / 退役名 / 测龄 | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` |
| `check_world.py`（world 闸门） | commit | 声明式验证对象：多线仓库共享验证环境的世界对账 | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` |
| `doctor.py`（开工预检 doctor） | start-of-work | 进程 / 端口活性（查会死的东西 ⇒ runs_at=start-of-work，不进 pre-commit） | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` |

14 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = 落一个声明行，这里自动长出来）。
<!-- /AUTO:GATES -->

