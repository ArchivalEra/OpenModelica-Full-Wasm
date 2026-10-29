# 生产交付清单 · E 线 MATLAB 语义桥

**给谁读**：宿主 `Octave-Full-Wasm`（站点资产装配方）与 UI 仓（终端消费者）。
**来源**：mail/107（内容仓实测：Octave 产品里 `omc_simulate` / `omc_mat_load` /
`omc_collect` **不存在**——我方验收是「测试运行时注入 + addpath」，不是产品装配）。
**性质**：本文件是**消费者契约**，不是安装脚本。权威文件清单在
`bridge/manifest.json`（机器可读，本仓 `check-bridge-manifest.py` 守着它）。

---

## 1. 交付清单：11 件 `.m` + 1 件宿主侧 `.js`

全部在 `bridge/`，**没有私有外部依赖**（`omc_mat_load` 内部的 `omc_mat_load_*` 是
子函数，同文件内；其余互调见下表）。**11 件全要**——没有可选子集：
`omc_simulate_model` 依赖 `omc_simulate` → `omc_call_internal` → MEMFS 协议；
`omc_simulate_async` / `omc_collect` 是同一协议的另一半入口。

| 层 | 文件 | 作用 |
|---|---|---|
| **对外 API** | `omc_simulate_model.m` | `omc_simulate_model('BouncingBall','stopTime',3.0)` ⇒ 数据矩阵（需求 E2 判据物） |
| | `omc_simulate.m` | 同上，返回 struct（`.time` / `.data` / `.names` / `.samples`） |
| | `omc_getVersion.m` | omc 版本串 |
| | `omc_mat_load.m` | MAT4 → Octave 变量（需求 D 的语义映射；含名字消毒） |
| **两段式传输** | `omc_submit.m` | 提交一条命令，**立即返回** seq（不等待） |
| | `omc_collect.m` | 取回应答；没有就明说 `pending`（不阻塞） |
| | `omc_simulate_async.m` | 仿真专用的两段式原语 |
| | `omc_call_internal.m` | 私有：单步调用+等待（**只在测试夹具里用**，产品驱动请走 submit/collect） |
| **FS 助手** | `omc_fs_write.m` | 宿主 → MEMFS 写数值数组 |
| | `omc_fs_write_b64.m` | 宿主 → MEMFS 写 base64 文本 |
| | `omc_fs_read.m` | MEMFS → 宿主，base64 分块回读 |
| **宿主侧（产品件）** | `omc_bridge.js` | `OmcBridge.serve({omc, writeFile, readFile, intervalMs})` —— 轮询 MEMFS 请求队列并驱动 omc。**三条承重语义已内建**（见下），由 `build/113/check-omc-bridge.mjs` 7 条自证守着 |

## 2. 装配形态 —— **必须写进 MEMFS，不是"铺到站点目录"**（实测定案）

★ 这一条是 2026-10-29 实测澄清的（第一版我写错了，被自己的验收件抓出来）：
把 `.m` 放进站点的 HTTP 目录（`<site>/bridge/`，HTTP 200 可取）**没有任何用** ——
Octave 的 `addpath` 走的是 **MEMFS**，而 MEMFS 根只有
`tmp / home / dev / proc / fonts / src / usr`，站点 HTTP 路径不在其中。
（实测：站点目录铺满 11 件 + `addpath('/bridge')` ⇒ `exist('omc_simulate_model')` 仍 **0**。）

**正确形态**：

```js
// 宿主的装配代码（在 Octave 引擎 boot 之后、首个 omc_* 调用之前）
const M = /* 活跃的 Octave 实例，通常是 window.Module 或 __octaveHosts[0].mod */;
M.FS.mkdir('/bridge');                                  // 幂等：已存在会抛，catch 掉
for (const f of Object.keys(MANIFEST.entries)) {        // 权威清单 = bridge/manifest.json
  M.FS.writeFile('/bridge/' + f, await fetchTextFromYourSite('bridge/' + f));
}
await new Promise(r => M.eval_string("addpath('/bridge');") === 0 && r());
```

**实测判据**（写进 MEMFS 后）：`exist('omc_simulate_model')` = 2/103 ⇒ FOUND；
对照组 `sin` FOUND、假名 MISSING（证明探针有区分力）。**这份实测已通过**。

`.m` 的来源仍由你（宿主）决定：可以从本仓 `bridge/` 直接取（11 件，清单在
`bridge/manifest.json`），也可以按 release asset 渠道取。**但落点必须是 MEMFS。**

**协议路径是写死的**（两侧同名常量，改一处必须改两处）：
`/tmp/omc_req.txt`（请求）/ `/tmp/omc_res.txt`（应答）/ `/tmp/omc_seq.txt`（序号）。
宿主只要保证这三个路径在 Octave 的 MEMFS 里可读写即可。

## 2b. 三条承重语义（宿主 mail/024 §2 要求：放进交付模块，不只留在测试里）

这三条是 `omc_bridge.js` 的**全部难点**，现在是该模块的内建行为（不是测试夹具的私货）：

1. **`cd`**：omc 的仿真输出目录**跟着 cwd 走**——不先 `cd` 到确定目录，`resultFile` 为空（实测）；
2. **`loadFile` 必须搬字节**：路径是 Octave 侧的，omc 是**另一个 wasm**，它的 VFS 里没有
   那个文件（实测 `wasi_path_open → -1`）⇒ 从 Octave MEMFS 读出、写进 omc VFS，再 loadFile；
3. **`simulate` 结果要回搬**：`.mat` 在 omc 的 VFS ⇒ 读出写回 Octave MEMFS，回 `MAT <path>`。

承重语义放在**代码里**（`dispatch()` 的注释与实现），并由
`build/113/check-omc-bridge.mjs`（7 条自证，含反向：未知命令必须拒绝）每提交复跑——
所以它不会因为改一次桥就悄悄丢掉。

## 3. 宿主前提：`omc_bridge.js` 的启动时序

```js
// 必须在 omc（引擎）就绪之后，且 Octave 引擎实例的 FS 已可访问之后：
await OmcBridge.serve({
  omc,                                  // omc 模块命名空间（有 omc_eval / omc_simulate / wasi_*）
  writeFile: (p, bytes) => octFS.writeFile(p, bytes),
  readFile:  (p) => new TextDecoder().decode(octFS.readFile(p)),
  intervalMs: 50,                       // 轮询粒度
});
```

**引擎句柄怎么拿（ESM 形态，宿主 mail/027 §3 实测纠正）**：本仓 web 档产物是
wasm-bindgen **ESM**，**没有** Emscripten 那套全局工厂（`createOpenModelicaCompiler` /
`OpenModelicaCompiler` / `createOmc` 三个都不存在）。真实形态：

```js
// omc/OpenModelicaCompiler.js
export { initSync, __wbg_init as default };
export function omc_init / omc_eval / omc_abi / omc_request_cancel / omc_enable_*
// 初始化：default({ module_or_path }) —— module_or_path 传站点上的 _bg.wasm URL
```

⇒ 用动态 `import()`，**说明符必须是绝对 URL**（相对串报
`Failed to resolve module specifier`）。拿到的命名空间就是 `serve()` 要的 `omc`。

四条实测教训（**宿主必须知道，否则会重踩**，全部来自
`test/browser/accept-omc-bridge.mjs` 的架构注释与实测）：

0. **`.m` 必须写进 MEMFS**（见 §2；HTTP 目录不算）——这一条最容易被忽略。
1. **两段式，不许忙等**：Octave 的 `.m` 里忙等会占住 worker 线程，而宿主读写 MEMFS
   也要经同一上下文 ⇒ **两边互等死锁**（实测：Octave 忙 3s 时宿主 evaluate 被阻塞
   2701ms）。所以产品态**只用 `omc_submit` / `omc_collect`**（`omc_call_internal`
   只作测试夹具的同步参考，产品里会死锁）。
2. **Octave 必须跑 worker 模式**（主线程留给桥）。
3. **两个 wasm 的 FS 互不可见** ⇒ 桥必须搬字节（`omc_fs_*` 就是干这个的）。
4. **worker 的 `eval` 返回值不含结果** ⇒ 取值走输出通道 / FS，大块用 base64 分块。

## 4. 产品态验收判据（`107` §4 第 3 问的答案）

现在的判据是「测试注入后能跑」——**不够**。产品态判据（**不做任何注入**）：

```matlab
% 前提：只有站点装配（bridge/ 已在 addpath 上），没有任何 test harness 注入
omc_getVersion()                                    % ⇒ 非空版本串
r = omc_simulate_model('BouncingBall', 'stopTime', 3.0);
size(r.data)                                        % ⇒ 628×N（N = 变量数）；r.time 单调
```

反向断言（可证伪）：未装配时同一句必须失败（`undefined` 或明确的"omc 未就绪"），
不许静默返回空矩阵。

**本仓提供**：`test/browser/accept-omc-bridge-product.mjs` —— 只做 `addpath`、不做注入，
跑上面两句。它红了就是装配没做对（与本仓 `accept-omc-bridge.mjs` 的注入式验收互补：
那个验桥本身，这个验交付）。

## 5. 谁做什么（分工）

| 方 | 动作 |
|---|---|
| **本仓（OM）** | 出 11 件 `.m` + `omc_bridge.js` + 本文档 + 机器可读清单；维护产品态验收件 |
| **宿主** | 站点装配（把 `bridge/` 铺进 Octave 站点）+ 启动 `OmcBridge.serve()`（时序见 §3） |
| **UI** | 终端 fallback 调 `omc_simulate`（它已按 `016` 的设计输入写了；装配到位后即可用） |

## 6. 复跑

```bash
# 清单一致性（本仓闸门；缺件/多件/哈希漂移都红）
python3 build/113/check-bridge-manifest.py --selftest
python3 build/113/check-bridge-manifest.py
# 产品态验收（需要宿主已装配；未装配时应当红 —— 那正是它的用处）
#   sh test/browser/run-omc-bridge-product.sh <已装配的 Octave 站点 URL>
```
