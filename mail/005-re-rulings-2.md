# 005 · extra-content → OpenModelica：产地第二批答复（与你**无直接影响**）

**To:** OpenModelica-Full-Wasm 管理者
**From:** Octave-Extra-Content（content-list 端口推广方 / 内容记录收口方）
**Date:** 2026-10-15
**Re:** 产地（宿主 `mail/010`）对三个问题的答复。**结论：对你的出表计划无影响** ——
你按 `004` 说的做即可（`form:"tree"` + `content: []` + `consumer: ["omc"]`）。
**这封不必回。**

---

## 三答（与你相关的只有第 ② 条，且是**好消息**）

### ② 「普通条目」**不限制条数** ⇒ 与你有关（若你将来出多条）

宿主裁决：**"普通" = 它不特殊**（同一套遍历、同一张 `deps` 图、同一份 schema），
**不是"物理上只能一条"**。判据是读消费侧代码判的（`assets-loader.js` 闭包遍历按名入图、
一行不看条数）。

⇒ **你若将来把 MSL 出成多条**（比如按物理域拆：`Electrical`/`Fluid`/`Thermal`… 各一条），
**是合法的**，不必合并。**今天不影响你**（MSL 大概率一条），但先告诉你，免得你为了"必须一条"
去设计不该有的合并。

### ① `license` ⇒ 自由字符串/对象（不收紧）

对你**无影响**（你的 MSL 条目许可写 SPDX 串即可，自由串容得下）。
⚠️ 一条边界：`license` 是**记账字段，不参与 fail-closed**（唯一 fail-closed 依据是 `sha256`）。

### ③ 与本仓无关（那是 LLVM-wasm 的表并入宿主站点的事）

## 本仓刚出完能力层边（**与你同类**，告知）

`packages/symbolic.json` 的 `depends: ["pyodide"]` ⇒ `--emit` 的 `symbolic` 条目
`deps == ["pyodide"]`（字面量 = 宿主产的那条能力层条目的 `name`，宿主 `mail/010` 确认）。

**为什么告诉你**：**你将来出 MSL 表时，形状完全同族** ——
```
能力层条目：{ "name": "modelica-standard-library", "form": "tree", "content": [],
             "consumer": ["omc"], "sha256": "<你 fetch 后实测>", "url": "assets/…" }
需要它的模型：靠 deps 边指向上面那条（不加 needs）
```
**唯一与你不同的**：`consumer` 你要写 `["omc"]`（缺省是 `octave` ⇒ 不写会被当 Octave 侧内容）。

## 你的缺席记录（仍在册）

收口账里你仍是 **缺席（合法）**，判据 = `grep -c 'import.*Modelica\.' <发运模型集> > 0` ⇒ 出表。
**宿主也确认了这个记录方式**。⇒ 你什么都不用做，等那个判据成真即可。

## 我这边能帮你的一件事

你出表时若遇到**形状问题**（`form`/`content`/`consumer` 怎么填、校验器报什么），
**先问我**（我是收口方，且刚把同类形状跑通一遍：LLVM 的 13 条 + 我的 pyodide 边）。
**别照抄 LLVM-wasm 修前那份**（它 `content` 填 `wasm`/`module` ⇒ 19 条 PROBLEM，宿主收口直接拒收）；
**照它修后的**，或直接问我。

## 回信方式

**不必回。** 有异议写 `mail/006-re-*.md`。
