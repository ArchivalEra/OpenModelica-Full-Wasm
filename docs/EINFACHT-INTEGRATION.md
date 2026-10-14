# Einfacht 接入方法（2026-10-13）

> **性质**：操作手册。把 [Einfacht](https://github.com/ArchivalEra/Einfacht)（反幻觉事实系统）
> 接进一个新仓库的**完整步骤**，含**踩过的坑**。
> **来源**：`Octave-Full-Wasm` 的实际接入（2026-10-09 采纳重构版，2026-10-10 追平上游 C1–C5）。
> 本文的所有"坑"都是那两次接入**实测踩到**的，不是推测。

---

## §0 Einfacht 是什么（一句话）

**让 agent 的每句「现在如此」都能被复跑证明。** 三块：

| 块 | 作用 |
|---|---|
| **事实台账** `FACTS.json` | 数字的**唯一产地**；每条事实旁写**复跑命令**，闸门每次提交逐字执行 |
| **翻案台账** `retractions.json` | 被推翻的断言登记在册 —— 它**重新出现**时报错 |
| **悬案台账** `questions/`（或 `.scratch/open-questions/issues/`） | 未结案的问题，每条挂**可跑的结算件** |

**机制层**（`zreflect/` + `reflect-hooks/` + `gates-selftest.sh`）**从上游 vendored**，
**数据层**（`zreflect/measure_<项目>.py`）是本仓自己的 —— **换仓库只换那一个文件**。

---

## §1 目录布局（接进来会长这样）

```
<repo>/
├── zreflect/                     # ← 机制层：从 Einfacht 上游拷，除 measure_* 数据层
│   ├── facts.py / ledger.py / gate.py / registry.py / render.py / runner.py / guard.py …
│   ├── check_facts.py / check_facts_replay.py / check_retractions.py / check_questions.py
│   ├── check_readme_sync.py / check_stale.py / check_pins.py / check_locks.py / check_envfile.py …
│   └── measure_<项目>.py         # ★ 本仓数据层：唯一"换仓库要改"的文件
├── reflect-hooks/                # ← git hooks（core.hooksPath 指这里）
│   ├── Einfacht.env              # ★ 旋钮的唯一可复现来源
│   ├── Einfacht.env.example
│   ├── einfach-env.sh            # 加载 env
│   ├── install.sh                # git config core.hooksPath reflect-hooks
│   ├── pre-commit                # 提交相位
│   └── pre-push                  # 推送相位（三语 README 判据在这里）
├── gates-selftest.sh             # ← 闸门自证台（每个闸门必须能证明自己会红）
├── build/FACTS.json              # ← 事实台账
├── build/retractions.json        # ← 翻案台账
├── questions/                    # ← 悬案（或 .scratch/open-questions/issues/）
├── STATE.md                      # ← 活状态（正文 + 文末 AUTO:STATE 机器块）
└── doctor.json                   # ← 开工预检（可选）
```

---

## §2 接入步骤（照抄，逐步可验）

### 步骤 1 · vendor 机制层
从 Einfacht 上游取 `zreflect/*.py` + `reflect-hooks/*` + `gates-selftest.sh`，
**但排除 `zreflect/measure_*.py` 里上游自己的数据层**，换成自己的 `measure_<项目>.py`。

### 步骤 2 · 写本仓数据层 `zreflect/measure_<项目>.py`
这是**唯一**要写的文件。它定义 `measure()`：把本仓"量到的事实"收集成 dict，
每条 `fact(value, cmd, ...)` 的 **`cmd` 必须是能跑的裸命令**（见 §4 坑 3）。

### 步骤 3 · 配旋钮 `reflect-hooks/Einfacht.env`
```sh
export REFLECT_FACTS="build/FACTS.json"
export REFLECT_DOC="STATE.md"
export REFLECT_DOCS="STATE.md,AGENTS.md,README.md,README.zh.md,README.de.md,CONTEXT.md"
export REFLECT_READMES="README.md,README.zh.md,README.de.md"     # 三语同批判据
export REFLECT_HISTORY_SECS="5,9,10"
export REFLECT_RETRACTIONS="build/retractions.json"
export REFLECT_QUESTIONS=".scratch/open-questions/issues"
```
**⚠️ 行尾不能写 `#` 注释**（§4 坑 1）。

### 步骤 4 · 装 hooks
```sh
sh reflect-hooks/install.sh      # = git config core.hooksPath reflect-hooks
```
**不装 = 一套没人执行的闸门，而日志一切正常**（§4 坑 4）。

### 步骤 5 · 首次生成台账 + 机器块
```sh
python3 zreflect/facts.py --render-doc STATE.md   # 生成/刷新 AUTO:STATE 机器块
```

### 步骤 6 · 自证
```sh
sh gates-selftest.sh    # 平台闸门自证（含跨仓库可配置性反向断言）
```

---

## §3 三条纪律（上游 C1–C5 带来的，本仓已采纳）

| 纪律 | 含义 |
|---|---|
| **C1 谓词 = 声明，不是文件名** | 执行面读 `registry --run <相位>`，**不再 glob `check_*.py`**。频率是声明字段 `runs_at="commit"\|"start-of-work"`。名字不再承重 ⇒ "孤儿"概念消失。平台模块也声明自己：`MODULE = module_meta(名, 一句话, selftest=True/False)` |
| **C2 off 与"跑过且通过"必须可区分** | `gate.off()` 打 `OFF:` 标记（rc 仍 0），执行面聚合 `ran / off / failed`。**"全绿"不许把"没跑"算进去** |
| **C4 "必须一致"的要配对账器** | 声明旋钮 ⊆ 实读旋钮、登记表 ⊆ 三语 README 配置表、夹具改名集唯一产地。**没有对账器的"必须一致" = 迟早不一致** |

---

## §4 ★ 实测踩过的坑（照抄会踩，逐条避开）

### 坑 1 · `Einfacht.env` 行尾的 `#` 注释会被并进值里
`export X="v"  # 注释` —— sh **只在单词开头**才把 `#` 当注释 ⇒ 值变成
`build/upstream-lock.json"   # 本仓…` ⇒ 闸门拿着这个去找文件 ⇒ 报"不存在"。
**注释只能单独成行。**

### 坑 2 · "配置了就必须存在"的旋钮，**不能全局配**
`REFLECT_LOCKS` / `REFLECT_PINS` / `REFLECT_INSTRUMENTS` / `REFLECT_DOCTOR` 这类，
全局配 ⇒ `gates-selftest.sh` 的**跨仓库夹具**（临时目录，没有那些文件）里 FATAL ⇒
误报"名字写死在代码里"（实测：`REFLECT_INSTRUMENTS`）。
**⇒ 一律内联传给需要它的那次调用**（见 `reflect-hooks/pre-commit`）。

### 坑 3 · `cmd` 必须是**裸命令**，且真能跑
台账里每条事实的 `cmd`，复跑闸门会**逐字执行**并把 stdout 与台账比对。
- 写成**中文散文** ⇒ rc=127（`Octave-Full-Wasm` 实测：两条事实第一次就是这么写的）；
- 输出**多于一个值** ⇒ 不符（stdout 只能打值本身）。
**判据**：`check_facts_replay.py` 绿 = 每条 `cmd` 逐字复跑、stdout 与台账一致。

### 坑 4 · hooks 不装 = 闸门从未生效
机制躺在仓库里、`git config core.hooksPath` 没指过去 ⇒ 提交一路畅通，
**而日志一切正常**。这正是"部署了 ≠ 在跑"的教训族。⇒ 接入后**立刻验**：
`git config core.hooksPath` 有值，且故意提交一个坏件看它**是否真红**。

### 坑 5 · 闸门自证是硬需求，不是加分
`Octave-Full-Wasm` 实测：约 20 个检查器里**只有 1 个**能证明自己会红；
"收集-断言"式闸门在**输入消失时静默变绿**（三处站点同时缺 `VERSION` ⇒ parity 报"完全一致"；
`declared == {}` ⇒ `verdict:"ok"`；`glue-selftest` `0/0` 算全过）。
⇒ **每个闸门必须带 `--selftest`**，且三类用例齐备：**正常不报 / 该报的必须报 / 空输入必须报**。
新增本仓专属闸门**必须**在 `gates-selftest.sh` 名单里登记 —— **名单外的闸门 = 没人盯着的闸门**。

### 坑 6 · `render.prose_of` 只豁免一对 AUTO 标记会假红
正文扫描时，`<!-- AUTO:x -->…<!-- /AUTO:x -->` 标记对**全部**要豁免（不止自己写的那对）。
实测：只豁免一对 ⇒ `AUTO:STATE` 里的机器行（如交付包字节数 `91,155,710`）被当正文扫，
尾组 `710` 撞上 `exported_functions=710` ⇒ 假红。⇒ 用正则豁免**所有** AUTO 对。

### 坑 7 · 重测会改值时必须显式 `--accept-changes`
`facts.py` 重测若发现值变了，会 **FATAL 拒绝写台账**（"未经接受的改口"）。
逐条确认变化是**实测**出来的之后，`--accept-changes=k1,k2` 放行。
**别养成"看见 FATAL 就 --accept-changes"的习惯** —— 那等于关掉这道闸。

---

## §5 复跑命令（验证接入成功）

```sh
# 平台层（执行面唯一产地）
python3 zreflect/facts.py --render-doc STATE.md --check    # 机器块新鲜
python3 zreflect/registry.py --run commit                  # ran/off/failed 三档
sh gates-selftest.sh                                       # 平台闸门自证
# 本仓专属层
python3 .githooks/check-whitelist.py                       # 白名单覆盖
python3 zreflect/check_facts_replay.py                     # 每条 cmd 逐字复跑
```

---

## §6 与本仓（OpenModelica-Full-Wasm）的对应

本仓的 `zreflect/measure_openmodelica.py` 是**数据层**。它要量的第一批事实（对应 `docs/REQUIREMENTS.md`）：

> ⚠️ **这个表 2026-10-14 起改为"实际在用的键"**（旧版是建仓期的"建议"表，两处已过时：
> 键名抄了 `omc.wasm` —— 产物真名是 `OpenModelicaCompiler_bg.wasm`，见 REQUIREMENTS §7 R2；
> 且写了"三线" —— 性能线已按用户点令删除，现为两线）。
> **键的唯一产地 = `build/FACTS.json`**（`python3 zreflect/facts.py --render-doc STATE.md` 渲染）；
> 下表只是分类导览，**加键/改键以数据层代码为准**。

| 键（实际） | 量什么 | 出处 |
|---|---|---|
| `omc_wasm32_sha` / `omc_wasm32_bytes` | node 档产物 sha / 字节（**路径从产物身份证读出**，不猜文件名） | `omc-out-wasm32/omc.build.json` |
| `omc_web_wasm_sha` / `omc_web_wasm_bytes` | web 档产物 sha / 字节（需求 B 用的那份） | `omc-out-web/web/omc/*_bg.wasm` |
| `omc_wasm32_verdict` / `omc_web_verdict` | 产物身份证 verdict（只有 ok 才可部署） | `omc.build.json` |
| `lane_branches_present` | 两线分支齐备数（一线一架构） | `git branch --list` + awk |
| `w64_spike_bytes` / `w64_spike_gate_rc` | wasm64 可行件（重建性能线的前置） | `artifacts/w64-spike.json` |
| `samepage_*` | 同页成本（**波动量只上档位**，见 STATE 的关键约定） | `artifacts/samepage-cost.json` |

**⚠️ 数字一律引用台账键，正文不手抄** —— 这是 Einfacht 的第一条规矩。
