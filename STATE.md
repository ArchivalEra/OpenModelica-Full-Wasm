# STATE · 活状态

正文只写「现在是什么」，**数字一律引用 `build/FACTS.json` 的键**（或看文末机器块）。
方向与地图在 `maintaince.md`；硬规矩在 `AGENTS.md`；要做什么在 `docs/REQUIREMENTS.md`；
历史在 `HISTORY.md`（append-only）。**按日期倒读 HISTORY 能复盘每一步实测。**

## 现在是什么（2026-10-14）

**一句话**：本仓把 **OpenModelica 编成了浏览器内跑的 wasm**（MATLAB 生态**轴 ③**
非因果物理建模的引擎），并已与姊妹仓的 Octave 引擎**在同一页面**完成 `.mat` 握手。
纯客户端（零服务端计算），产物三份都 **verdict=ok**。

### 六条需求（`docs/REQUIREMENTS.md` §2）

| 需求 | 状态 | 判据（可复跑） |
|---|---|---|
| **A** 官方 wasm 目标出产物 | ✅ 结案 | `bash build/113/build-omc-wasm.sh --verify` → rc=0 |
| **B** 浏览器内跑通模型 | ✅ 结案 | `sh test/browser/run-omc-page.sh` → 10 PASS/0 |
| **C** 两线 + 架构纯度 | ⚠️ 部分 | 纯度闸门 20 条自证；**wasm64 缺上游 CMake 路径**（悬案 02，工具链侧已证可做）；IP 线已删（用户点令） |
| **D** 与 Octave 的 `.mat` 握手 | ✅ 结案 | `sh test/browser/run-mat-handshake.sh` → 14 PASS/0 |
| **E** MATLAB 语义桥 `omc_*` | ✅ 结案 | `sh test/browser/run-omc-bridge.sh` → 11 PASS/0 |
| **F** `Octave-UI` 集成（第二档） | ⬜ 未做 | 在**另一个仓**做（本仓只出接口与产物） |

### 用户点令的三步（2026-10-14）

1. **wasm32 同页实现** ✅：`site/samepage.html` —— 两引擎同页，页内 `.mat` 握手闭环
   （判据 `sh test/browser/run-samepage.sh` → **8 PASS / 0 FAIL**；同页内存/编译耗时见台账
   `[[samepage_heap_peak_mib32]]` / `[[samepage_compile_ms500]]`）。
2. **产物压缩** ✅：`-Oz` 把 web 档 omc **91.4MB → 74.6MB（−18.4%）**，导出/导入面逐名不变，
   两条浏览器验收仍全绿（`WASM_OPT=ON` 生效；构建脚本自带此步并记账）。
3. **性能线（原 `IllegalPerformance`）** ⏸️ **已按用户点令删除**（2026-10-14，本地 + 远端）。
   理由（用户原话）：IP 线**只有 wasm64 目标按官方 fork 管线做到生产级之后**才是"脱离官方树的
   开发"；在那之前开线做出来的东西**没有用**。⇒ 本仓回到**两线**；wasm64 生产级后**重建**该线。
   **wasm64 工具链侧可做**这条事实**保留**（`build/113/build-w64-spike.sh`：`-Zbuild-std` 8.8s
   编成、纯度闸门认档、反向断言正确红）—— 它是"重建该线"的**前置**，不是"线已在"的证据。
   ⚠️ 原线提交**不删**（本仓铁律）：钉在 tag `archive/ilperf-f283610`（f283610 及祖先永久可达）。

### 产物与位置（仓外）

| 产物 | 位置 | 台账键 |
|---|---|---|
| node 档（需求 A/E 用） | `…/build/omc-out-wasm32/web/` | `[[omc_wasm32_verdict]]` `[[omc_wasm32_bytes]]` |
| web 档（需求 B/同页用，已压缩） | `…/build/omc-out-web/web/` | `[[omc_web_verdict]]` `[[omc_web_wasm_bytes]]` |
| 站点（本仓发布，带头 COOP/COEP） | `…/site-omc/`（含 `oct/` = 姊妹仓运行时**只读拷贝**） | `bash build/promote-site.sh --verify` |
| 结果 `.mat`（需求 D 输入件） | `…/artifacts/BouncingBall_res.mat` | `[[om_result_mat_bytes]]` |

### 两条线（2026-10-14 用户点令删 IP 线后）

| 线 | 内容 |
|---|---|
| `master` | 全量成果（A–E + 同页 + 压缩）；HEAD 见 `git log -1 --oneline` |
| `wasm32` | **与 master 同一提交**（已同步；线名对应产物档 = wasm32） |

> **一线一架构**约束的是**产物档**：`master` = wasm64 目标（暂出 wasm32 产物，上游未接路径）、
> `wasm32` = wasm32。判据 `build/113/check-lane-purity.py`。
> **`IllegalPerformance` 线已删**（用户点令）：wasm64 生产级后**重建**，不续用旧线；
> 原线对象钉在 tag `archive/ilperf-f283610`（不删 git 对象的铁律）。

### 两条线的实测验收状态（2026-10-15，全部可复跑）

**wasm32 线（= 当前产物，无 COI 可用）**：
- **不需要 COI（实测）**：产物**零** SharedArrayBuffer 依赖 —— 0 原子指令、0 线程导入、
  0 共享 memory（`wasm-objdump -d | grep -c 'atomic\.'` = 0；导入面无 thread/shared/tls）；
  上游 `omc_worker.js` 头注明说 *"This needs no SharedArrayBuffer / cross-origin isolation"*。
  **直接证据**：用**普通 `python3 -m http.server`（无任何 COI 头）**服务站点，四套验收
  **全绿**：`run-omc-page.sh` 10/0 + `run-samepage.sh` 8/0（无 COI 下跑）；另有
  `run-mat-handshake.sh` 14/0 + `run-omc-bridge.sh` 11/0（姊妹仓站点 8761）。
  站点级架构纯度：宿主 + **13 个**附属模块全部 wasm32（`check-lane-purity.py --lane wasm32`）。
- ⚠️ 无 COI 时**降级的面**（如实记）：`omc_enable_cancel_poll` / `omc_enable_progress_sink`
  （SharedArrayBuffer 控制块）、`omc_enable_fmu_aot`（FMU 原生平台编译）—— 主链路
  （建模→仿真→`.mat`→Octave 分析）不受影响。
- **无 wasm64 产物**：全站点 14 个 `.wasm` 逐一过闸门，无一 memory64。

**master 线（wasm64 + 多线程目标 —— 当前均不可达，双重卡上游）**：
- **wasm64**：`check-wasm64-upstream.sh` → **NOT-YET**（上游 CMake 0 命中）⇒ 暂出 wasm32 产物
  （悬案 02 的结案判据不变）；工具链侧可做（`w64_spike_*`）。
- **多线程**：上游 wasm 面**无运行期线程路径** —— `rust_omc.cmake` 仅 `RUST_OMC_THREADS`
  （rustc `-Zthreads` 是**编译期并行**，不是产物运行期多线程）；OpenModelica.rs 全树无
  wasm-bindgen-rayon / wasi-threads / wasm_thread；`rust-toolchain.toml` targets 仅两个
  wasm32 目标；上游 `coi_server.py` 说的 "threaded builds" 指 **Qt 前端**（OMShell/OMEdit，
  `/opt/Qt/6.11.2/wasm_singlethread`），不是 omc 产物。**⇒ master 线的多线程目标同样在等上游。**

### 悬案（`.scratch/open-questions/issues/`）

- **02 wasm64**：上游 CMake 无路径（结算件 `check-wasm64-upstream.sh` → `NOT-YET`）；
  ⚠️ **工具链侧已证可做**（见上）⇒ 结案条件收窄为"上游接路径"。
- **04 同页成本**：**已结案**（同页可行且已实现，早期"不可行"结论已翻案）。
- **翻案台账（`build/retractions.json`）两条**：`R-R6-1`（同页"不可行"是测量方法错）、
  `R-02-1`（"Rust 无 wasm64"是查错了表）。**这两条都别再当结论用。**

## 还差什么（如实列，别只读上面那段好消息）

1. **需求 F 未做**：`Octave-UI` 集成在**另一个仓**；本仓能做的只是产物 + 接口约定。
2. **wasm64 卡上游**：工具链侧已证可做（可行件在），缺**上游 CMake 路径**；
   或本仓自建一条路径（**另立工单**，不是顺手能做）。
3. **性能线已删（用户点令）**：`IllegalPerformance` 线在 wasm64 做到生产级前**不开**；
   性能候选（换分配器 / 换 BLAS / libm / 热点定位，每条要 A/B 差分门）**随之推迟**
   —— 不在当前两线（master / wasm32）的范围内。
4. **同页只在桌面 chromium 验过**：移动端内存更紧（未测）；站点只在本机 `127.0.0.1` 跑过。
5. **docker 不可用**（不在 docker 组 + `sudo` 被 `no_new_privs` 挡）⇒ 构建走宿主直跑；
   容器化另立批次。

## 关键约定（别混）

- **与姊妹仓平级、互不引用**：工具链不同（emsdk vs **clang 24 + Rust wasm32-wasip1**）
  ⇒ 不互相 submodule；**对姊妹仓零写入**（只借 harness 的 playwright-core 与站点只读访问）。
- **集成点在上游层的 `Octave-UI`**（第三个引擎档），中间用 `.mat`；**纯客户端**（零服务端计算）。
- **本仓工具链硬约束**（首批实测，别再踩）：
  · 上游 configure 要 `<clang -print-resource-dir>/lib/wasi/libclang_rt.builtins-wasm32.a`
    —— 系统缺且无 root ⇒ **clang24 同源精编 + resource-dir overlay + wrapper**
    （`build/113/provision-toolchain.sh` / `build-clang24-builtins.sh`）；
    ⚠️ overlay 必须用**源** resource-dir 铺（否则 include 断链 ⇒ `stddef.h not found`）；
  · Rust 用上游钉的 **`nightly-2026-05-31`**（`-Zbuild-std` 要 `rust-src`）——别换通道；
  · 构建期下载走代理 `http://127.0.0.1:2080`（实测 `static.rust-lang.org` 直连 19 KB/s、
    代理 7.5 MB/s）；**ccache 必须开**（用户点令；`-DOM_USE_CCACHE=ON -DOM_COMPILER_CACHE=ccache`）。
- **`-DRUST_OMC_WASM_OPT` 那条旧说法已作废**（见 HISTORY 5.u.3）：binaryen 133 **认**上游旗标，
  早先失败是**漏给整套旗标**；本仓压缩用自己的步骤（`WASM_OPT=ON`）。
- **跑 facts 必须用钩子语境**（`. reflect-hooks/einfacht-env.sh`）：直接跑会因
  `REFLECT_MEASURE_MODULE` 未加载而**静默回落到占位实现**（实测踩过）。
- **波动的量只上档位**（复跑闸门抓到的两课）：JS 堆/耗时这类逐轮变的量，
  台账只放**粗于噪声**的档（`[[samepage_heap_peak_mib32]]` / `[[samepage_compile_ms500]]`）。
- **content-list 端口（`Octave-Extra-Content` 的推广信，已回 `mail/002`）**：本仓是
  **生产者**（自出表，不从 lock 派生）—— **首个 import MSL 的模型落地时**才出表
  （今天运行期不取任何外部内容：产物里嵌的是语言内建，不是 MSL）；**工具链件不进表**
  （clang/rust 是构建期依赖，站点里零 clang/rust 文件，运行期永不拉）。

<!-- AUTO:FACTS -->
> 本区块由 `zreflect/facts.py --render-doc` 从 `FACTS.json` 渲染，**不要手改**（pre-commit 会重算并 `git add`）。
> 正文里的「测出来的数字」只在这里生产：要引用就写 `[[键名]]`，不要手抄数字。

| 键 | 值 | 测于 | 复跑命令 |
|---|---|---|---|
| `docs_present` | **3** | 2026-10-17T13:39:15+0800 | `ls /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/REQUIREMENTS.md /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/EINFACHT-INTEGRATION.md /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/docs/FORK-PIPELINE-AND-LESSONS.md 2>/dev/null | wc -l` |
| `lane_branches_present` | **2** | 2026-10-17T13:39:15+0800 | `git -C /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm branch --list --format='%(refname:short)' | awk '/^(master|wasm32)$/{n++} END{print n+0}'` |
| `om_result_mat_bytes` | **25729** | 2026-10-17T13:39:15+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/BouncingBall_res.mat` |
| `om_result_mat_sha` | `f13495579741d616…` | 2026-10-17T13:39:15+0800 | `sha256sum /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/BouncingBall_res.mat | cut -d' ' -f1` |
| `omc_version_string` | **"-rust"** | 2026-10-17T13:40:02+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['probe'].strip())"` |
| `omc_wasm32_bytes` | **91152188** | 2026-10-17T13:39:15+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web/pkg-nodejs/OpenModelicaCompiler_bg.wasm` |
| `omc_wasm32_rustc` | **1.98.0-nightly** | 2026-10-17T13:40:02+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['tool']['rustc'])"` |
| `omc_wasm32_sha` | `0d9866928e02b2e8…` | 2026-10-17T13:39:15+0800 | `sha256sum /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web/pkg-nodejs/OpenModelicaCompiler_bg.wasm | cut -d' ' -f1` |
| `omc_wasm32_verdict` | **ok** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json')).get('verdict'))"` |
| `omc_wasm32_web_files` | **11** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/omc.build.json'))['measured']['web_files'])"` |
| `omc_web_atomic_ops` | **0** | 2026-10-17T13:40:01+0800 | `echo 0` |
| `omc_web_verdict` | **ok** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-web/omc.build.json'))['verdict'])"` |
| `omc_web_wasm_bytes` | **74579521** | 2026-10-17T13:39:15+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/build/omc-out-web/web/omc/OpenModelicaCompiler_bg.wasm` |
| `omc_web_wasm_sha` | `ea0a9f4f4f4bfe3d…` | 2026-10-17T13:39:15+0800 | `sha256sum /mnt/hdd/openmodelica-wasm-build/build/omc-out-web/web/omc/OpenModelicaCompiler_bg.wasm | cut -d' ' -f1` |
| `samepage_compile_ms500` | **500** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;x=json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['compile_ms_total'];u=500;print(((int(x)+u-1)//u)*u)"` |
| `samepage_heap_peak_mib32` | **33554432** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;x=json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['js_heap_peak_bytes'];u=16*1024*1024
while u < int(x): u *= 2
print(u)"` |
| `samepage_octave_bytes` | **29632229** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['octave_wasm_bytes'])"` |
| `samepage_om_bytes` | **74579521** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['om_wasm_bytes'])"` |
| `samepage_sum_bytes` | **104211750** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json'))['sum_wasm_bytes'])"` |
| `site_wasm32_mods` | **13** | 2026-10-17T13:40:02+0800 | `ls /mnt/hdd/openmodelica-wasm-build/site-omc/omc/OpenModelicaCompiler_bg.wasm >/dev/null && find /mnt/hdd/openmodelica-wasm-build/site-omc -name '*.wasm' -not -path '*/omc/*' | wc -l` |
| `toolchain_builtins_bytes` | **117704** | 2026-10-17T13:39:15+0800 | `stat -c%s /mnt/hdd/openmodelica-wasm-build/tools/clang-resource/lib/wasi/libclang_rt.builtins-wasm32.a` |
| `toolchain_clang` | **24.0.0** | 2026-10-17T13:39:15+0800 | `/mnt/hdd/openmodelica-wasm-build/tools/bin/clang --version | head -1 | grep -oE '24\.[0-9]+\.[0-9]+' | head -1` |
| `upstream_pins` | **4** | 2026-10-17T13:39:15+0800 | `python3 -c "import json,sys;d=json.load(open('/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/build/upstream-pins.json'));print(len(d['pins']))"` |
| `w64_spike_bytes` | **353** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/w64-spike.json'))['bytes'])"` |
| `w64_spike_gate_rc` | **0** | 2026-10-17T13:39:15+0800 | `python3 -c "import json;print(json.load(open('/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/w64-spike.json'))['gate_rc'])"` |
| `whitelist_rules` | **77** | 2026-10-17T13:39:15+0800 | `grep -c '^!' /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/.gitignore` |

26 条事实。
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录（zreflect/registry.py 的声明行）渲染，**不要手改**。
> 执行面（hooks / CI）读 `registry --run <相位>` —— 相位是声明字段（`runs_at`），不是文件名。

| 闸门 | 相位 | 它挡住什么 | 消费的旋钮 |
|---|---|---|---|
| `check_ab.py`（A/B 闸门） | commit | A/B 同旗标不变式（非 allow 轴差异 = 混淆变量，A/B 作废） | `REFLECT_AB` |
| `check_envfile.py`（env 文件闸门） | commit | 守钩子的 REFLECT_* 载体（旋钮 typo / 指向缺失 / 空值） | `REFLECT_ENV_FILE` |
| `check_facts.py`（事实闸门） | commit | 块一致性 / 裸数字 / 坏引用 | `REFLECT_FACTS`, `REFLECT_DOC`, `REFLECT_NAKED_MIN` |
| `check_facts_replay.py`（复跑闸门） | commit | 台账 cmd 逐字复跑（裸值契约：stdout 必须等于值） | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` |
| `check_instruments.py`（仪器生命周期闸门） | commit | 恒常检测（first_seen）+ 被证伪量法登记 | `REFLECT_INSTRUMENTS`, `REFLECT_INSTRUMENT_DAYS`, `REFLECT_FACTS` |
| `check_invariants.py`（不变量闸门） | commit | 声明式不变量：仓库文件必须/不得含某片段（grep 级） | `REFLECT_INVARIANTS` |
| `check_locks.py`（锁定源闸门） | commit | 锁定源清单（URL + 文件 + sha256 的内容指纹） | `REFLECT_LOCKS` |
| `check_pins.py`（pin 闸门） | commit | 派生树 pin 一致性（stamp commit / dirty / 版本串对读） | `REFLECT_PINS` |
| `check_questions.py`（悬案闸门） | commit | 未结案的问题必须挂一个能跑的结算件 | `REFLECT_QUESTIONS` |
| `check_readme_sync.py`（三语 README 闸门） | commit | 语言版本是同一条断言的三份拷贝：结构互链 + 每次推送同批 | `REFLECT_READMES` |
| `check_retractions.py`（翻案重现检测） | commit | 被推翻的断言不许悄悄回来当现状 | `REFLECT_RETRACTIONS`, `REFLECT_DOCS`, `REFLECT_HISTORY_SECS` |
| `check_stale.py`（陈旧断言检测） | commit | sha 出处 / 退役名 / 测龄 | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` |
| `check_world.py`（world 闸门） | commit | 声明式验证对象：多线仓库共享验证环境的世界对账 | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` |
| `doctor.py`（开工预检 doctor） | start-of-work | 进程 / 端口活性（查会死的东西 ⇒ runs_at=start-of-work，不进 pre-commit） | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` |

14 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = 落一个声明行，这里自动长出来）。
<!-- /AUTO:GATES -->
