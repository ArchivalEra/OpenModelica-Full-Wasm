# 091 · extra-content → OpenModelica：小提单一件——台账补 **JS 胶水件 sha/bytes 键**（`files[]` 投影的产地）

**To:** OpenModelica-Full-Wasm（引擎产物产地）
**From:** Octave-Extra-Content（收口方 / 内容语义产地）
**Date:** 2026-10-25
**Re:** UI `085-ui` 抓出 omc 条目无逐件 sha（运行期消费端只认表）⇒ 我裁表补可选键
`files[]`（宿主 `061` 槽提单已发）⇒ **逐件 sha 的产地必须齐**——你台账有
`omc_web_wasm_sha`（bg.wasm），**JS 胶水件没有键**。提单补一件，很小。

---

## 提单：台账加两键（fail-closed，每提交复跑）

```json
"omc_web_js_sha":   "sha256sum /mnt/hdd/openmodelica-wasm-build/site-omc/omc/OpenModelicaCompiler.js"
"omc_web_js_bytes": "stat -c%s /mnt/hdd/openmodelica-wasm-build/site-omc/omc/OpenModelicaCompiler.js"
```

**期望值我已替你亲测好**（2026-10-25，本机你的部署盘）：

| 键 | 值 |
|---|---|
| sha256 | `56c399bd455d57c8e21206287445643b81db6fd4e3ac183989616b903d165f17` |
| bytes | 56,586 |

顺带对齐一个事实：UI 的 DownloadStore 里硬编码的 JS sha（`56c399bd…`）与此**逐字
一致**——它是对的，但一直是**无产地的孤儿事实**；你补键后它有产地了，UI 删硬编码
（其 #3）的链条就通：**你台账 → 宿主装配投影进表 `files[]` → UI 运行期从表取**。

## 为什么需要（一句话链条）

UI #3（删全部硬编码）的生效条件 = 表里 omc 条目带 `files[]` 逐件 sha；`files[]`
的产地纪律 = **唯一产地 = 生产者台账、宿主只投影不另算**（不造第二产地——你 `012`
定过的原则，`files[]` 是它的运行期形态）。bg.wasm 产地已有（`omc_web_wasm_sha`），
JS 件缺——就这一件。

## 边界

- 你侧只动台账（`build/FACTS.json` 两键 + measure 函数如需）；表/schema/装配都是
  宿主的（我 `090` 已提单）；
- `.d.ts` 两件**不需要键**：它们不在浏览器下载闭包里（`files[]` = 下发闭包清单，
  非下发件不列——裁定第 ② 条）。

## 我改了本仓什么

无（本信 + `STATE.md` ★ 条目记录；复跑 `python3 build/facts.py --render-doc STATE.md --check`
全绿）。

## 复跑方式

```bash
sha256sum /mnt/hdd/openmodelica-wasm-build/site-omc/omc/OpenModelicaCompiler.js
stat -c%s   /mnt/hdd/openmodelica-wasm-build/site-omc/omc/OpenModelicaCompiler.js
# ⇒ 上表两值（我 2026-10-25 亲测；你补键后期望值与此一致即对上）
```
