# MSL · 4.1.0+maint.om（安装形状 zip）

**独立 release**：与引擎分开（`v0.2.0-wasm32`）。理由见下。

## 为什么不和引擎混

MSL 是**被装载的数据**、不是引擎 —— `omc_vfs_load_zip('/.openmodelica/libraries', zipBytes)`
收一个 zip 就**不关心里面是什么内容**。所以 MSL 换版本**不需要重编 wasm**。

合发会有两个问题（内容仓 `mail/033` §2 实测）：

| 做法 | MSL 更新一次要重传 |
|---|---|
| 合发（每版引擎 release 带当时那份 MSL） | **94.1 MB**（79% 与 MSL 无关） |
| **分开发（本做法）** | **19.5 MB** |

更严重的是**版本号会撒谎**：`v0.1.1` 里 MSL 变了、引擎没变，那个 tag 到底指什么？
tag 应该代表「引擎变了」，不该代表「某个数据文件变了」。

## 内容

- **1 条 entry / 5 个 asset**（manifest + 4 块 × identity）
- **只出 identity 是故意的**：zip 已是压格式，再压一遍省不到 1%（内容仓实测 13 个包）；
  生成器的 `PRECOMPRESSED` 判定自动只出 identity。
- 逐块 5 MiB 切片，8 并发拉、逐块 sha、拼回原 zip。

## 形状很重要：这是**安装形状**，不是上游 archive

| | 字节 | sha256 |
|---|---|---|
| 上游 GitHub archive（**仓库快照**，顶层带 hash 目录） | 20,362,007 | `ba66dd3a…` |
| **本 release（安装形状，`Modelica/package.mo` 在顶层）** | 19,482,938 | `a97d8d94…` |

拿上游那份直接 mount ⇒ `loadModel` 找不到包（实测）。必须用本 release 这份。

## 消费方式

```bash
# 拉 manifest → 按 chunks[].file 逐字取块（不拼名字）→ 拼接 → 校验 sha256
# → 解出 zip → omc_vfs_load_zip('/.openmodelica/libraries', zipBytes)
```

`forge-catalog.json` 是唯一汇合点：升级 MSL = 发新 tag，catalog 的 `url` 指到新 tag 前缀；
**旧 tag 永远还在**（release 不可变是这个契约的地基）。

## 验收（可复跑）

```bash
sh test/browser/run-accept-release-v4.sh <本 release BASE> identity /mnt/hdd/openmodelica-wasm-build/site-omc/assets/msl
# ⇒ 12 PASS / 0 FAIL（含：逐块 sha / 拼回全局 sha / 与源产物逐字一致 /
#    ★ 0 Range · 0 条件请求 · 0 自定义头）
```
