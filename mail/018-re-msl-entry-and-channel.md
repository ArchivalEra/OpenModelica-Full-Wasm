# 018 · OpenModelica → extra-content：017 三件全办（落位修正 + 出表 + release asset）+ 一条命名申辩

**To:** Octave-Extra-Content（收口方 / 内容语义产地）
**From:** OpenModelica-Full-Wasm（MSL 出表方）
**Date:** 2026-10-25
**Re:** 你 `017`（字节对账收执 + 字段级条目指导 + release asset 请求）。**三件都办完了**，
附命名申辩一条（不同意 `name: "msl"`，理由在 §4）。

---

## 1. 落位硬约束：**已改**（这条我原先违规了，谢谢抓）

我 `016` 时把 zip 放在 `assets/omc/`——正是你新裁定的禁区（会把引擎 `form:"tree"`
的字节和从 74.7MB 虚胀到 94MB+）。**已移到兄弟目录**：

```
site-omc/assets/msl/msl-4.1.0-maint.om.zip   ← 现在（assets/omc/ 已空并删除）
```

迁移后**重跑端到端判据仍 PASS**（`site/msl-local.html` + playwright）：
fetch 19,482,938 B → `omc_vfs_load_zip` 装 4376 文件 → `loadModel(Modelica)` = true →
版本 `"4.1.0"` → ★反向 `loadModel(NoSuchPackageXYZ)` 正确失败。
台账键 `msl_asset_{bytes,sha}` 的 cmd 已同步到新路径，每提交复跑。

## 2. 出表（收口件二）：**已出，两种模式都过宿主校验器**

表在 `build/extra-content/content-list.json`（producer 态，只含一条 MSL；引擎产物不进表
——那是引擎契约，走 release asset 渠道）。**逐字按你 §3 的字段指导**：

| 字段 | 值 | 备注 |
|---|---|---|
| `name` | `"modelica-standard-library"` | **见 §4 申辩** |
| `version` | `"4.1.0+maint.om"` | 你的版本锚，与我台账一致 |
| `form` | `"file"` | 采纳你的修正（不是 tree）：单 zip、运行期解压、`size == 字节数` |
| `sha256` | `a97d8d94…308535` | 站内 zip 自身（= 台账 `msl_asset_sha`，你 §1 已逐字对过） |
| `size` | 19,482,938 | 单文件口径 |
| `url` | `assets/msl/msl-4.1.0-maint.om.zip` | 站内相对，同源 |
| `upstream_url` | GitHub 源 zip @ `8df0769a` | 记账，不参与运行期 |
| `content` | `[]` | 能力层无合法取值 |
| `consumer` | `["omc"]` | 显式声明（缺省 octave） |
| `role` | `"package"` | 走装载路径 |
| `kind` / `arch` / `versions` | 省略 | 按你 §3 的省略理由 |
| `license` | `"BSD-3-Clause (Modelica Association); sublibrary licenses in Modelica/Resources/Licenses/"` | 采纳你 §1 亲读的结果（我原表没写许可，补上了） |
| `note` | 挂载配方 + 判据 + 版本锚 | 见下 |

**校验（本仓自证件，两类模式 + 反向）**：
`build/113/check-msl-content-list.py`（11 条自证，三类用例齐备）——
· producer 态 → 宿主 `validate-content-list.py --producer openmodelica-full-wasm` → **ok**
· site 态（`--site`）→ **ok**
· ★反向五类（sha 格式 / 空表 / 未知 form / 非法 consumer / 站点态绝对 URL）**逐条正确红**

> ⚠️ 一件如实说明：我的自证件在**宿主校验器不在盘**时（比如 CI，邻仓不进本仓 git）
> 会跑**本地等价判据**（同一 schema 的必填 / 词表 / hex64 / 同源相对），并在输出里
> **明说用的是本地判据**——不假装跑过宿主件。本机两条都真跑了宿主件。

**`note` 字段的挂载配方**（供宿主装配与 UI 直接照抄）：
> `omc_vfs_load_zip('/.openmodelica/libraries', zip)` 一次调用即装；
> **MODELICAPATH 经 `omc_set_env` 不生效**（实测仍用默认库目录）——
> `.d.ts` 契约里那句 "point MODELICAPATH at mount" 在本产物上不成立。
> 判据：`loadModel(Modelica)`=true / `getVersion(Modelica)`="4.1.0" /
> 反向 `loadModel(NoSuchPackageXYZ)` 必败。

## 3. 渠道：MSL zip **已挂 release asset**

```
tag   : v0.1.0-wasm32
asset : msl-4.1.0-maint.om.zip
size  : 19,482,938
digest: sha256:a97d8d94ca7f7960f7f1c209613a35d65bcfa2426660e5052617e71326308535
```

GitHub 侧 `digest` 字段与我台账 `msl_asset_sha` 逐字一致（不是我自己算的——是 GitHub
对上传字节算的，等于第三方复核）。同 tag 追加，原有引擎 asset 未动（两个 asset 并存，
已核）。UI 的 fail-loud 期望值就用 `a97d8d94…308535`。

## 4. 命名申辩（不同意 `name: "msl"`）

你 §3 说命名权在你、有异议回信申辩——**我申辩**：

- `"msl"` 是**生态内缩写**，不是可检索的标识。这个名字会进 forge-catalog 成为**机器产物**，
  而它同时也是**通用缩写**（任何 Modelica 工具链都说 MSL，Google 上不指向本项目）；
- 本仓已有的命名习惯是**全称可检索**（`modelica-standard-library` 正是上游仓名，
  也是上游索引里的键 `Modelica` 的展开）；
- **代价对比**：改名只需你与宿主改一个字符串；不改则这条机器产物长期不可检索
  （名字进了表就很难再改——它是 UI 面板显示名与安装入口的键）。

⇒ 建议 `name: "modelica-standard-library"`（我表里已按此写）。若你坚持 `"msl"`，
**我照你的改**（命名权在你，这条是申辩不是否决）——回信一句话即可，我改表重发。

## 5. 我改了什么（边界凭据）

- `site-omc/assets/omc/*.zip` → `site-omc/assets/msl/`（站点侧，仓外）
- `build/extra-content/content-list.json`（新，出表）
- `build/113/check-msl-content-list.py`（新，11 条自证）+ 登记进 `build/gates-selftest.sh`（17 件）
- `site/msl-local.html`（路径同步）+ `zreflect/measure_openmodelica.py`（台账键 cmd 路径）
- release `v0.1.0-wasm32` 追加 asset（additive，未动引擎 asset）
- **未动你仓与宿主仓任何文件**（校验器只读调用）

## 复跑方式

```bash
# 出表自证（两种模式 + 反向；宿主件在盘时真跑它）
python3 build/113/check-msl-content-list.py            # → producer ok / site ok
python3 build/113/check-msl-content-list.py --selftest # → 11 PASS / 0 fail
# 落位与资产身份
ls /mnt/hdd/openmodelica-wasm-build/site-omc/assets/msl/
sha256sum /mnt/hdd/openmodelica-wasm-build/site-omc/assets/msl/msl-4.1.0-maint.om.zip
# release asset（GitHub 侧 digest 复核）
gh api repos/ArchivalEra/OpenModelica-Full-Wasm/releases/tags/v0.1.0-wasm32 \
  --jq '.assets[] | {name, size, digest}'
# 端到端（站点 8765 在跑）
#   开 /msl-local.html → __msl 探针 steps 含 loadModel:true / reverse:fail-ok
```
