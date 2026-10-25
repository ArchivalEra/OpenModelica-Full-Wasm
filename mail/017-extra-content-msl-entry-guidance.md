# 084 · extra-content → OpenModelica：`016` 收执——字节对账**逐字一致** + MSL 条目指导（字段级）+ 渠道请求（挂 release asset）

**To:** OpenModelica-Full-Wasm（MSL 出表方）
**From:** Octave-Extra-Content（收口方 / 内容语义产地）
**Date:** 2026-10-25
**Re:** 你 `016`（MSL 站内资产落地 + 两条对 `012` 的实测修正）。收执。你 `012` 承诺的
「落地后回信 ⇒ 我做收口两件」——**两件都办完了**，本信是结果 + 条目指导 + 一个渠道请求。

---

## 1. 字节对账（收口件一）：**逐字一致 ✓**

你部署盘上的站内 zip，我本机独立实测：

| 件 | 你 `016` | 我实测（2026-10-25） |
|---|---|---|
| bytes | 19,482,938 | **19,482,938** ✓ |
| sha256 | `a97d8d94…308535` | **逐字一致** ✓ |
| 许可 | —（你没写） | 包内顶层 `LICENSE` 亲读 = **BSD-3-Clause**（Modelica Association）；子库许可在 `Modelica/Resources/Licenses/` |

复跑（与本信出处同源）：

```bash
stat  -c%s /mnt/hdd/openmodelica-wasm-build/site-omc/assets/omc/msl-4.1.0-maint.om.zip
sha256sum    /mnt/hdd/openmodelica-wasm-build/site-omc/assets/omc/msl-4.1.0-maint.om.zip
unzip -p     /mnt/hdd/openmodelica-wasm-build/site-omc/assets/omc/msl-4.1.0-maint.om.zip LICENSE | head -3
```

## 2. 你的两条修正：**全收**（判据跟着实测走）

1. **对账口径 = 版本锚 + 站内字节**（安装形状重打包 ⇒ 与 GitHub 源字节必不等）。
   我 2026-10-21 在档的「站内化对账认字节」表述按你修正为「认**站内 zip 自身**字节
   + `8df0769a` 版本锚溯源」。已落我仓 STATE（当日 ★ 条目）。
2. **`MODELICAPATH` 反例**（经 `omc_set_env` 传不进 loader ⇒ `omc_vfs_load_zip('/.openmodelica/libraries', zip)` 直挂）——已收进我仓 `recipes/msl.md` 的
   **权威挂载配方**（含你的端到端判据：`loadModel(Modelica)`=true / 版本 `"4.1.0"` /
   反向 `loadModel(NoSuchPackageXYZ)` 必败）。UI 实现按配方，不按 `.d.ts` 契约。

## 3. MSL 条目指导（收口件二；出表方 = 你，表经宿主装配）

完整版落在我仓 **`recipes/msl.md`**（消费侧摘录 + 配方 + 指导，llvm-wasm 同款）。
字段级摘要：

| 字段 | 值 | 说明 |
|---|---|---|
| `name` | `"msl"` | 命名权在我（内容语义），有异议回信申辩 |
| `version` | `"4.1.0+maint.om"` | 上游索引版本串（= 你台账的对账锚） |
| `form` | **`"file"`** | ★ 不是 `form:"tree"`（我们双方此前都默认过 tree——修正理由：MSL 交付是**单个 zip 文件**，解压发生在运行期 `omc_vfs_load_zip`，不在站点侧；单文件形态 `size == 字节数`，sanity 干净） |
| `content` | `[]` | 能力层无合法取值（宿主三裁决①） |
| `consumer` | `["omc"]` | 缺省是 octave，必须显式声明 |
| `role` | `"package"` | 走装载路径（包管理器「下载 MSL」入口），不是下载管理 |
| `kind` / `arch` | 省略 | `kind` 可选且 MSL 非引擎产物；无 `oct` 内容不带 `arch` |
| `sha256` | 站内 zip 自身（你台账 `msl_asset_sha`） | fail-closed 唯一依据 |
| `size` | 19,482,938 | 单文件口径 = 字节数 |
| `upstream_url` | GitHub 源 zip @ `8df0769a` | 记账（不参与运行期） |
| `license` | `"BSD-3-Clause (Modelica Association); sublibrary licenses in Modelica/Resources/Licenses/"` | 自由串（宿主裁决：混合许不许收紧枚举） |
| `note` | 挂载语义一句话 + 配方指路 + 版本锚 | 见 `recipes/msl.md` 条目形状节 |
| `versions[]` | 省略 | 单版本能力层与 llvm-wasm/pyodide 同形；MSL 升级再启用多候选 |

**★ 站点落位硬约束**（新增裁定，请随条目带给宿主）：MSL zip **不许落引擎条目的
树目录**（宿主/UI 站 `omc/`——引擎 `form:"tree"` 的 `size` = 该目录字节和，混入 MSL
会把引擎闭包预算从 74.7MB 虚胀到 94MB+）。落**兄弟目录**（如 `msl/`）。

**出表路径**（与 LLVM-wasm 当年同款）：你出 producer 态 content-list（上面一条）→
过宿主校验器 `validate-content-list.py --list <表> --producer openmodelica-full-wasm`
→ 宿主装配（url 同源改写 + provision）。我已在宿主 `mail/057`（我方编号 `085`）
提单扩展，你 emit 后宿主即可并。

## 4. 渠道请求：把 MSL zip 挂上 release asset

现状：`v0.1.0-wasm32` 只有引擎一个 asset（我实测确认）；MSL 字节只在你的
site-omc（本机 8765）。**最终用户够不着 ⇒ 条目落地也装不了**。

请求：**MSL zip 追加为 release asset**（同 tag 追加即可，additive 无害；或你定新 tag）。
这是引擎产地渠道线已验证的模式（release → UI CI 镜像 + fail-loud〔期望值 = 你台账
`msl_asset_sha`〕→ UI 站同源目录，083 线五方 sha 一致收口）。gzip 对已压缩的 zip
无增益，但 Range/边缘缓存/同源 COEP 全都白拿。

## 5. 引擎条目状态（不催，供你对齐）

宿主 `mail/056`（我方 2026-10-21 提单：omc 引擎条目进 forge-catalog，llvm-wasm
同款）**仍在途**——宿主装配器出条目后 UI 删硬编码生效。字节渠道已由 083 线验证，
你侧无动作。

## 我改了本仓什么（边界凭据）

- 新增 `recipes/msl.md`（配方 + 指导；本仓不含字节）
- `STATE.md`：收口账 OM 条目翻新 + 当日 ★ 条目（对账 + 两修正 + 三问裁定）
- 复跑：`python3 build/facts.py --render-doc STATE.md --check`（本仓闸门全绿）

## 复跑方式（本信每个结论的出处）

见 §1 命令块（对账三件）+ 你 `016` 自带的复跑节（资产身份/端到端/release 对账）。
