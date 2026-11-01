# Release · v0.2.0-wasm32（codename handover）

**发布线**：`wasm32`（本仓唯一发布的档；`master` 的 wasm64/多线程目标卡上游 —— 悬案 02）。
**版本身份证**：`build/VERSION.json`（数字不手抄，台账键为准：`build/FACTS.json`）。

## ★ 一句话先说清楚：这个版本**没有**重编引擎

引擎四件产物（`OpenModelicaCompiler_bg.wasm` / `.js` / 两份 `.d.ts`）的字节与 sha256
**与 `v0.1.0-wasm32` 逐字相同**。判据（可复跑）：

```bash
gh api repos/ArchivalEra/OpenModelica-Full-Wasm/releases/tags/v0.1.0-wasm32 \
  --jq '.assets[]|select(.name=="OpenModelicaCompiler_bg.wasm")|.digest'
# ⇒ sha256:8287589e… 与台账 omc_web_wasm_sha 逐字一致
```

**那为什么还是发新版**：`v0.1.0` 以来的变化都在**交付面**，而且改变了对外契约：

| 交付面变化 | 性质 |
|---|---|
| `bridge/omc_bridge.js` 扶正为**产品件**：三条承重语义（`cd` 钉输出目录 / `loadFile` 搬字节 / `simulate` 结果回搬）写进 `dispatch`，并新增 `simulateModel` 一步到位 | 对外接口**新增**能力 |
| `bridge/manifest.json`（12 件机器可读清单）+ `docs/BRIDGE-DELIVERY.md`（装配契约） | 新增消费者契约 |
| `test/browser/accept-omc-bridge-product.mjs` 产品态判据（零注入），并修掉就绪门早 ~400ms 的假红 | 交付判据变了 |
| `build/serve-coi.py` 缓存头 `no-store` → `ETag` + `no-cache`（刷新 74.5 MB → 几百字节） | 站点行为变了 |
| GitRoll 整改：桥改命令表、`samepage.html` 修恒真三元、三份 html 嵌套三元抽取 | 站点/桥代码变了 |

按 semver：**新增对外能力 = minor**，不是 patch。引擎没变这点写在本文开头，免得下一个人
以为要重新验引擎。

## 两个 release（分开发，协议不动）

MSL 是**被装载的数据**、不是引擎 —— `omc_vfs_load_zip` 收一个 zip 就不关心里面是什么。
合发会让「MSL 更新」逼着重传 74.5 MB 的 wasm（内容仓 `mail/033` §2 实测：合发一次要重传
94.1 MB，其中 79% 与 MSL 无关）。

| release | tag | manifest id | entry | asset | 编码 |
|---|---|---|---|---|---|
| **引擎** | `v0.2.0-wasm32` | `OpenModelica-Full-Wasm/v0.2.0-wasm32` | 4 | 55 | zstd / gzip / identity |
| **MSL** | `msl-4.1.0-maint.om` | `OpenModelica-Full-Wasm/msl-4.1.0-maint.om` | 1 | 5 | identity |

两个 tag **互不引用**；`forge-catalog.json` 是它们唯一的汇合点（升级 MSL = 发新 tag，
catalog 的 `url` 指到新 tag 前缀，旧 tag 永远还在）。

**MSL 只有 identity 是故意的**：zip 是已压格式，再压一遍省不到 1%（内容仓 `mail/033` §3.1），
生成器的 `PRECOMPRESSED` 判定自动只出 identity。

**MSL 的 sha 必须是站内那份**：`[[msl_asset_bytes]]` / `[[msl_asset_sha]]` 是**安装形状**
（`Modelica/package.mo` 在顶层）；上游 GitHub archive 是仓库快照形状（顶层带 hash 目录），
字节与 sha 都不同。拿错那份，客户端装不上。

## 验收（每条都可复跑）

| 判据 | 命令 | 结果 |
|---|---|---|
| 官方目标构建 | `bash build/113/build-omc-wasm.sh --verify` | verdict=ok |
| 页面内建模→仿真→`.mat` | `sh test/browser/run-omc-page.sh` | 10 PASS / 0 FAIL（无 COI 实测） |
| 与 Octave `.mat` 握手 | `sh test/browser/run-mat-handshake.sh` | 14 PASS / 0 FAIL |
| 语义桥 `omc_*`（注入式） | `sh test/browser/run-omc-bridge.sh` | 11 PASS / 0 FAIL |
| 语义桥**产品态**（零注入） | `sh test/browser/run-omc-bridge-product.sh <已装配站点>` | 9 PASS / 0 FAIL |
| 两引擎同页 | `sh test/browser/run-samepage.sh` | 8 PASS / 0 FAIL（无 COI 实测） |
| Node 侧 | `sh test/node/run.sh test/node/accept-omc-getversion.mjs` | 9 PASS / 0 FAIL |
| **release v4 端到端（引擎）** | `sh test/browser/run-accept-release-v4.sh <BASE> zstd` | 27 PASS / 0 FAIL |
| | 同上 `gzip` / `identity` | 各 27 PASS / 0 FAIL |
| **release v4 端到端（MSL）** | `sh test/browser/run-accept-release-v4.sh <BASE> identity` | 12 PASS / 0 FAIL |
| 清单一致性（bridge） | `python3 build/113/check-bridge-manifest.py` | 12 件逐件 bytes/sha 对上 |

release 端到端验的是**信里要求的八条**：asset 名扁平无斜杠 / 数量与 manifest 一致 /
每块 sha 与 manifest 一致 / 每块能独立解码 / 拼接后 == `bytes` 且 sha == `sha256` /
校验器全绿 / 浏览器 8 并发拉全部拼 / **0 Range · 0 条件请求 · 0 自定义头**。

一条实测教训写进套件注释：**分片的每块是独立压缩帧**，拼接后用单次解压只解出第一帧
（实测 `got=5242880` 而不是完整 74.5 MB）⇒ 必须**逐块解压再拼**。

## 产物与指纹（值以台账 `build/FACTS.json` 为准）

| 产物 | 台账键（字节 / sha256） |
|---|---|
| web 档 `omc/OpenModelicaCompiler_bg.wasm`（浏览器用，已 `-Oz`） | `[[omc_web_wasm_bytes]]` / `[[omc_web_wasm_sha]]` |
| node 档 `pkg-nodejs/OpenModelicaCompiler_bg.wasm`（E/Node 用） | `[[omc_wasm32_bytes]]` / `[[omc_wasm32_sha]]` |
| JS 胶水件 `omc/OpenModelicaCompiler.js` | `[[omc_web_js_bytes]]` / `[[omc_web_js_sha]]` |
| MSL 站内 zip（安装形状） | `[[msl_asset_bytes]]` / `[[msl_asset_sha]]` |

## 已知边界（如实记）

- **无 COI 时降级的增强面**：`omc_enable_cancel_poll` / `omc_enable_progress_sink` /
  `omc_enable_fmu_aot`（要 SharedArrayBuffer 控制块）；主链路不受影响。
- **wasm64 / 多线程未发**：上游 `rust_omc.cmake` 无 wasm64 路径、无运行期线程路径
  （`RUST_OMC_THREADS` 是编译期并行）。上游接路径后按悬案 02 翻面。
- **引擎 boot 在弱网下很慢**：64 Mbit 中位数 `[[omc_boot_64mbit_p50_bucket]]` ms 档、
  4.8 Mbit 约 `[[omc_boot_slow_ms_bucket]]` ms 档 ⇒ UI 必须给进度与取消，不能裸等待。
- **同页只在桌面 chromium 验过**；移动端未测。
- **桥的 `.m` 必须在 MEMFS**：铺站点 HTTP 目录**不产生效果**（实测：铺满 11 件 + addpath
  ⇒ `exist()` 仍 0）。装配形态见 `docs/BRIDGE-DELIVERY.md` §2。

## 复跑（一切数字的出处）

```bash
bash build/113/build-omc-wasm.sh --verify
sh test/browser/run-omc-page.sh
sh test/browser/run-samepage.sh
python3 build/113/check-lane-purity.py --lane wasm32 --host <site>/omc/OpenModelicaCompiler_bg.wasm --mod <site>/**/*.wasm…

# release v4（两个 release 都要验）
sh test/browser/run-accept-release-v4.sh <引擎 release BASE> zstd
sh test/browser/run-accept-release-v4.sh <MSL release BASE> identity
```
