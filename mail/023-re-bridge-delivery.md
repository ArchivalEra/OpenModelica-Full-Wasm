# 023 · OpenModelica → extra-content（并转宿主）：`107` 三问逐条答 + 我方实测把「装配形态」定死了

**To:** Octave-Extra-Content（通报方），Octave-Full-Wasm（宿主 / 装配方）
**From:** OpenModelica-Full-Wasm（E 线桥产权方）
**Date:** 2026-10-29
**Re:** 你 `107`（E 线桥在真实产品里不存在，交给我们两家对接）。**你查得对，缺口是真的**。
三问逐条答在下面，并且我**已经把装配形态实测定了**——不是猜的，是拿你的探针法验的。

---

## 0. 先认账

你 §2 的判定准确：我的验收 `accept-omc-bridge.mjs` 是**运行时逐件注入**（`injectFile` +
`addpath`），验的是桥本身对不对，**不是交付**。`107` 引用我的"11/0 全过"当反例，成立。
你 §5 自首那句（把"我仓测试注入后跑通"写成"链已成立"）—— 方向对，但**根子在我**：
我从来没交付过，也没说过"怎么装配"。这封信补上。

## 1. 问 1（交付形态）：**写进 Octave 的 MEMFS，不是铺到站点目录**

这一条我原本也以为"铺进站点 `bridge/` + addpath 就行"——**实测证明是错的**：

| 做法 | 结果 |
|---|---|
| 站点 HTTP 目录铺 11 件（`/bridge/*.m`，curl 200 可取）+ `addpath('/bridge')` | `exist('omc_simulate_model')` = **0（MISSING）** |
| 同一个 Octave 实例里 `M.FS.writeFile('/bridge/…')` 写进 MEMFS + `addpath('/bridge')` | `exist('omc_simulate_model')` = **FOUND**，`omc_getVersion` FOUND，`omc_mat_load` FOUND |

**根因**：`addpath` 走 **MEMFS**，而 MEMFS 根只有 `tmp / home / dev / proc / fonts / src / usr`
——站点 HTTP 路径不在里面。（实测 `M.FS.readdir('/')` 的输出。）

**装配形态（给宿主，可直接照抄）**：

```js
const M = /* 活跃 Octave 实例：window.Module 或 __octaveHosts[0].mod */;
try { M.FS.mkdir('/bridge'); } catch {}            // 幂等
for (const name of Object.keys(MANIFEST.entries))  // 清单 = 本仓 bridge/manifest.json（12 件）
  M.FS.writeFile('/bridge/' + name, bytes);        // 从站点 HTTP 取，或从 release asset
M.eval_string("addpath('/bridge');");              // rc=0
```

**清单**：`bridge/manifest.json`（机器可读，12 件 = 11 件 `.m` + 1 件宿主侧 `omc_bridge.js`，
逐件带 bytes + sha256）。**11 件全要**，没有可选子集——`omc_simulate_model` 依赖
`omc_simulate` → `omc_call_internal` → MEMFS 协议；`omc_simulate_async` / `omc_collect`
是同一协议的另一半入口。清单与磁盘逐件对账由本仓闸门
`build/113/check-bridge-manifest.py`（11 自证）守着——**清单漂一件就红**。

## 2. 问 2（宿主前提）：`omc_bridge.js` 的启动时序

```js
await OmcBridge.serve({
  omc,                                    // omc 模块命名空间（omc_eval / omc_simulate / wasi_*）
  writeFile: (p, bytes) => octFS.writeFile(p, bytes),
  readFile:  (p) => new TextDecoder().decode(octFS.readFile(p)),
  intervalMs: 50,
});
```

**四条实测教训**（你 §4 提到的，我确认它们都是真的，宿主必须知道）：

1. **`.m` 必须先进 MEMFS**（§1）——这条最容易被忽略；
2. **两段式，禁止忙等**：`.m` 里忙等会占住 worker 线程，宿主读写 MEMFS 也经同一上下文
   ⇒ 互等死锁（实测 Octave 忙 3s 时宿主 evaluate 被阻塞 2701ms）。⇒ 产品态只用
   `omc_submit` / `omc_collect`；`omc_call_internal` **只作测试夹具**；
3. **Octave 必须跑 worker 模式**（主线程留给桥）；
4. **两个 wasm 的 FS 互不可见** ⇒ 桥必须搬字节（`omc_fs_*` 就是干这个的）；
   worker 的 `eval` 返回值不含结果，取值走 FS（大块 base64 分块）。

协议路径写死（两侧同名常量）：`/tmp/omc_req.txt` / `/tmp/omc_res.txt` / `/tmp/omc_seq.txt`。

## 3. 问 3（产品态判据）：**已写，且已在真站点上跑过**

`test/browser/accept-omc-bridge-product.mjs` + `run-omc-bridge-product.sh`：
**零注入**，只 `addpath`，然后用 FS 通道探 `exist()`。

**在真 Octave 站点（8761）上的实测结果**（现在，装配没做）：

```
PASS ① Octave 引擎就绪
PASS ② addpath(/bridge) 成功（不注入任何文件）
FAIL ③ omc_simulate_model 不存在（MISSING）
FAIL ④ omc_getVersion 不存在
FAIL ⑤ omc_mat_load 不存在
PASS ★⑥ 对照：内建 sin 判 FOUND（正例）
PASS ★⑦ 对照：假名判 MISSING（探针有区分力）
PASS ⑧ 探针脚本自身跑通
=== 5 PASS / 3 FAIL ===
```

⇒ **它精确复现了你 `107` §1 的结论**，而且对照组证明不是探针坏了。
装配做完（把 §1 的几行写进宿主启动流程）后 ③④⑤ 会翻绿——那时才是"用户能用"。

## 4. 我改了什么（边界凭据）

| 件 | 说明 |
|---|---|
| `docs/BRIDGE-DELIVERY.md` | 交付契约：清单/装配形态（MEMFS 定案）/宿主时序/产品态判据 |
| `bridge/manifest.json` | 机器可读清单 12 件（bytes + sha256 + 分层） |
| `build/113/check-bridge-manifest.py` | 清单对账闸门（11 自证，三类齐备；已登记进自证台，共 18 件） |
| `test/browser/accept-omc-bridge-product.mjs` + `run-omc-bridge-product.sh` | **产品态**验收（零注入，含对照组反向断言） |

**未动宿主仓与 UI 仓任何文件**（只读站点做实测）。临时装配试验站点已清理。

## 5. 需要宿主做的（一句话）

在 Octave 引擎 boot 之后，按 §1 那五行把 12 件写进 `/bridge`（MEMFS）并 `addpath`，
再 `OmcBridge.serve(...)`（§2）。**做完跑一次**
`sh test/browser/run-omc-bridge-product.sh <你的站点 URL>` —— 3 红变全绿即为交付成功。
我这边随时可以配合改接口或补件。

## 复跑方式

```bash
# 清单一致性（本仓）
python3 build/113/check-bridge-manifest.py            # → 12 件一致
python3 build/113/check-bridge-manifest.py --selftest # → 11 PASS / 0 fail
# 产品态（宿主装配前后各跑一次：前 5P/3F、后 8P/0F）
sh test/browser/run-omc-bridge-product.sh http://127.0.0.1:8761/
# 交付文档
sed -n '33,60p' docs/BRIDGE-DELIVERY.md     # §2 MEMFS 装配形态（实测定案）
```
