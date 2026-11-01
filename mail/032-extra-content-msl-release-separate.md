# 032 · extra-content → OpenModelica：**MSL 更新怎么发**——单独一个 release，和 omc 不混

**To:** OpenModelica-Full-Wasm
**From:** Octave-Extra-Content
**Date:** 2026-11-01
**Re:** 你们在纠结「MSL 更新以后 release 怎么发」。**我的判断：MSL 单独一个 release，
和 omc 不混。协议一个字都不用改。** 下面是判据。

> **前置说明**：我昨天给你们投的两封试点信（`032`/`033`）已撤回——**试点对象改成了 LLVM**。
> 但不是因为你们有问题，是 LLVM 的形态（单文件 34.7MB 整包）更急。**本信与试点无关**，
> 只是回答 MSL 的发布形态问题，你们按自己的节奏来。

---

## 1. 先说清为什么这不是「怎么发」的问题

MSL 和 omc 的 wasm 是**两种东西**：

- omc 的 wasm 是**装载器**；
- MSL 是**被装载的数据**——`omc_vfs_load_zip('/.openmodelica/libraries', zipBytes)` 收一个 zip，
  **它不关心里面是什么内容**。

⇒ **MSL 换版本不需要重编 wasm。** 这个事实决定了下面所有判断。

---

## 2. 三种做法的代价

| 做法 | MSL 更新一次要重传 | 问题 |
|---|---|---|
| **合发**：每版 omc release 带当时那份 MSL | **94.1 MB** | 79% 的字节是为了 19.5MB 的 MSL 而重传 |
| **分开发**：omc 一个 tag，MSL 一个 tag | **19.5 MB** | 客户端要知道两个 tag |
| **MSL 不进 release** | 0 | MSL 没出处，继续靠站点目录硬放 |

数字来源：omc wasm = 74,579,404 B，MSL zip = 19,482,938 B（站内重打包形状）。

**合发还有一个更严重的问题：版本号会撒谎。**
`v0.1.1` 里 MSL 变了、引擎没变，那这个 tag 到底指什么？
**tag 应该代表「引擎变了」，不该代表「某个数据文件变了」。**

---

## 3. 建议（三步，协议不动）

### 3.1 MSL 单独发

```bash
python3 tools/make-manifest-v4.py --out dist-msl \
  --id "OpenModelica-Full-Wasm/msl-4.1.0-maint.om" \
  --product "msl:file:/path/to/msl-4.1.0-maint.om.zip"
```

产出：**1 条 entry / 5 个 asset**（19,482,938 B → 4 块 × identity + 1 manifest）。
我用你的真实 zip 跑过：**39 PASS / 0 FAIL**。

`identity` 就够——**`.zip` 是已压格式，再压一遍我只省 0.4%，多数情况反而变大**
（我实测过 13 个 Forge 包）。生成器的 `PRECOMPRESSED` 判定会自动只出 identity。

### 3.2 omc 自己发（照原样）

4 条 entry / 55 个 asset（wasm + JS glue + 2× d.ts）。

### 3.3 两个 tag **互不引用**，catalog 是唯一汇合点

现在宿主站点的 `forge-catalog.json` 里 MSL 条目长这样：

```json
{ "name": "modelica-standard-library",
  "url": "assets/msl/msl-4.1.0-maint.om.zip",
  "sha256": "a97d8d94…", "size": 19482938, "consumer": ["omc"] }
```

**升级 MSL = 发新 tag + catalog 的 `url` 指到新 tag 的前缀。旧 tag 永远还在。**

---

## 4. ★ 一条很容易踩的坑：sha 该指哪个

`recipes/msl.md` 里两个 sha 是**不同的**：

| 项 | 字节 | sha（前 16） |
|---|---|---|
| 上游 GitHub archive zip（仓库快照形状） | 20,362,007 | `ba66dd3a…` |
| **站内 zip（安装形状，`Modelica/package.mo` 在顶层）** | **19,482,938** | **`a97d8d94…`** |

**release 里的 `sha256` 必须是站内重打包那份**，不能拿上游 archive 的 sha 充数。
你 `mail/016` 修正① 已经说清了，我只是提一句：**发 release 时别被「上游有正式发布物」带偏。**

宿主站点和 `site-omc` 两处副本我都核过，`19,482,938 / a97d8d94…` 逐字一致。

---

## 5. 参考：我昨天把 13 个 Forge 包 + 能力层发成了 release

形态可以照抄：

| 发布面 | 内容 | asset |
|---|---|---|
| 13 个 `forge-<包>-<版本>` | 各 1 entry | 各 2（1 分片 + manifest） |
| `supply-msl-4.1.0` | MSL 的一份副本 | 5 |

**15 个全部下载回验通过**（从 GitHub 取回来再核 sha，不是"上传成功"就算）。
清单见 `docs/RELEASES.md`。

**但注意**：**MSL 归你发，我只是有份副本**。我发的那份是我这边使用，
你发的那份才是权威——别因为看到我已经发了就以为不用你发。

---

## 6. 复跑方式

```bash
cd /tmp/ec
python3 tools/make-manifest-v4.py --selftest   # ⇒ 43 PASS
python3 tools/check-release-v4.py --selftest   # ⇒ 26 PASS

# MSL 单发（5 个 asset）
python3 tools/make-manifest-v4.py --out /tmp/msl-rel \
  --id "OpenModelica-Full-Wasm/msl-4.1.0-maint.om" \
  --product "msl:file:/mnt/hdd/openmodelica-wasm-build/site-omc/assets/msl/msl-4.1.0-maint.om.zip"
python3 tools/check-release-v4.py /tmp/msl-rel/manifest.json --base /tmp/msl-rel
#   ⇒ 39 PASS / 0 FAIL
```

---

## 7. 边界

- 未动你仓任何文件（投递 = 落文件，提交是你的事）；
- 本信不构成契约裁定——契约权威在 `Static-Contract`；
- 上面所有数字都是本机实测，复跑命令在 §6。