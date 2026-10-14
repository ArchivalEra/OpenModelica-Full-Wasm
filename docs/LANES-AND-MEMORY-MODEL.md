# 内存架构与分支线经验（2026-10-14，来自姊妹仓 Octave-Full-Wasm 的实测）

> **性质**：经验集 + 判据表。**本仓需求 C（三线）的直接参考材料** —— 姊妹仓把"一线一架构"
> 从三条事故里立成了机器判据，本仓照它的形状写即可。
> **来源**：`Octave-Full-Wasm` 实测**三次混编事故** + 完整的两档产物/四格站点实践。
> **每条命令都可复跑；每条事故都附真实报错原话。**

---

## §0 一句话

**"一线一架构"不是规矩癖，而是因为混编的失败模式是
"两边都建成功、自检全绿、运行期才炸"** —— 而这种错**极难从现象倒推原因**（§2 三次实测）。

---

## §1 两个档的判据（别猜，两条命令能量）

| | wasm32 | wasm64 |
|---|---|---|
| 指针宽度 | 32 bit | 64 bit |
| 单模块内存上限 | 4 GiB | 极大（姊妹仓实测 **5 GiB / 8 GiB 都真分配成功**） |
| 宿主形态 | 导出 memory | **导入** memory（实测 `imports_mem=1, exports_mem=0`） |

```bash
# ① 权威读数（容器内；本仓用 Rust/wasm-ld，同理可用 wasm-tools 或 llvm-readobj）
llvm-readobj --file-headers <wasm> | grep -E "Arch:|AddressSize"
# ② 浏览器/Node 侧（memory 是导入还是导出）
node -e "const m=new WebAssembly.Module(require('fs').readFileSync(process.argv[1]));
console.log('imp',WebAssembly.Module.imports(m).filter(i=>i.kind==='memory').length,
'ex',WebAssembly.Module.exports(m).filter(e=>e.kind==='memory').length)" <wasm>
```

---

## §2 ★ 三次实测事故（照抄本仓会踩的方式，逐条看）

### 事故 1 · 链接期就炸（最好的一种）
```
ida.c.o: wasm32 object file can't be linked in wasm64 mode
```
⇒ **链里混进了另一档的目标文件**。姊妹仓因此整批挂了 `__ode15__`（链了 wasm32 版 sundials）。

### 事故 2 · 加载器只给一句，而它与"缺符号"极像
```
incorrect architecture (wasm32 vs wasm64)          ← 架构错
Cannot read properties of undefined (reading 'value')  ← 缺符号
```
**两者混在一个日志里 ⇒ 没人能一眼看出是哪种**。

### 事故 3 · 最坏：全绿然后运行期炸
**宿主与模块都"建成功"、构建自检全绿**，运行期才报：
```
TypeError: tlsInitFunc is not a function
```
根因：**用 wasm32 的 sysroot 编 wasm64 模块** ⇒ 产物没有 `_emscripten_tls_init` ⇒ 拒载。

**共同教训**：
> **"建成功" ≠ "同档"**；且"不同档"的报错**有三种形态**，两种像"缺符号"。
> ⇒ **必须有机器判据**，不能靠人看日志。

---

## §3 判据：架构纯度闸门（本仓 C2 照这个形状写）

姊妹仓的实现（`build/113/check-lane-purity.py`）**三条判据 + 两条纪律**：

**三条判据**（逐条 fail-closed）：
1. 宿主 wasm 的 `Arch` == 车道声明的档（**用工具读，不猜**）；
2. 该车道的模块目录里**每个**模块同档（**0 个也算未通过** —— 零值守卫）；
3. 站点**本档专属**目录里的模块同档。

**两条纪律**（都是实测换来的）：
- **反向断言必须有**：喂一个错档产物 ⇒ **必须红**（自证里做，证明判据不是恒真）；
- **别把"基础档"目录喂进去**：多档站里基础档目录**合法地装着另一档**的模块，
  查了必假红 —— 姊妹仓实测在一个四格站上产生 **44 处假报**。

**对本仓的翻译**：本仓没有 `.oct` 那种"按档编的模块"，但**有等价物** ——
`omc.wasm` 自身 + 任何按档编的 side 产物（如 SUNDIALS/KLU 归档、wasm-jit runtime）。
判据同形：**宿主 / 各档产物 / 站点的档专属目录三处同档**。

---

## §4 ★ 与本仓特殊处直接相关：**上游不支持 wasm64**（需求 C 的 R1）

姊妹仓能编 wasm64 是因为 **emscripten 支持 `-sMEMORY64=1`**；
**本仓的工具链是 Rust + `wasm32-wasip1`**（官方 CMake 目标），而：

- 上游 `rust_omc.cmake` grep `wasm64` = **0 命中**（同 `wasm` 469 命中）；
- 全仓 code search `wasm64 repo:OpenModelica/OpenModelica` = **0**；
- ⇒ **`master` 线暂出 wasm32 产物**（官方唯一支持档），悬案 + 结算件已建（见本仓 `.scratch/`）。

**这份经验里最有用的部分因此是**：
1. **"一线一架构"在只有一档可达时依然成立** —— 线仍然分开（产物不同、验收不同），
   只是其中一条暂缺 arm ⇒ **悬案挂结算件**（上游加支持即翻面），而不是"先混着编"。
2. **混编禁令与档可达性无关**：即使两条线都出 wasm32，也**不许**把 x86-64 或其它架构的
   预编译件（如随系统带的 `.so`）混进去 —— 那正是事故 1–3 的形状。

> ⚠️ 姊妹仓的一条**否定经验**也值得记：**它自己的 clang 24 能编
> `--target=wasm64-unknown-unknown -c`（通过）**，但**上游 CMake 没有这条路径** ⇒
> "工具链能做" ≠ "上游支持"。判据要写在**上游仓**上（本仓的结算件就是干这个的）。

---

## §5 性能线该怎么切（`IllegalPerformance` 这类分支）

> ⚠️ **2026-10-14 本仓现状（用户点令）**：性能线 `IllegalPerformance` **已删除** ——
> 它**只有 wasm64 目标按官方 fork 管线做到生产级之后**才是"脱离官方树的开发"（用户原话）。
> ⇒ 本节记的**怎么切**这门知识**保留**（重建该线时照用），但**本仓现在没有这条线**。

**判据先行**：任何"更快"的分支都要有 **A/B 差分门**（**同旗标** + 变异自证），
否则你量的是"改了之后"而不是"因为改了"。

姊妹仓实测**封口**的四类（避免本仓重走）：
| 方向 | 结论 |
|---|---|
| 换分配器（mimalloc） | **有效**（已采纳，交错 3 轮取中位） |
| 换 BLAS（OpenBLAS） | **有效**（已采纳 + IEEE 逐位红线） |
| libm 标量替换 | **负判决**（wasm 无标量 FMA ⇒ 拿不到收益） |
| 热点余下部分 | 全在**语言自身源码**里（仪器定位，不猜） |

**两条纪律**：
- **负判决也是资产**（记下来，下一个 agent 不用重走；姊妹仓有 `retractions.json` 专门管翻案）；
- **性能线不许改默认档**：它是候选线，**发运是产品决定**（姊妹仓原话：
  "我绝对不允许 IllegalPerformance 作为强制的新分支"）。

**对本仓的直接含义**：OM 的性能线（SIMD / 多线程 / 优化求解器）应当**独立成线、独立验收**，
且**默认线保持不变**；每条候选都要有 it 自己的 A/B 判据。

---

## §6 多档站点长什么样（姊妹仓的四格，本仓将来同形）

```
<站点>/
├── octave.{js,wasm,data}      # 基础档（wasm32）
├── threads/                   # 线程档（wasm32 + shared memory）
├── w64/                       # wasm64 + 线程
├── w64-base/                  # wasm64 无线程
├── lanes.js                   # 档清单（页面按此择档）
└── assets/{oct,oct-threads,oct-w64,…}/   # ★ 每档专属模块目录（判据 3 查这里）
```

**页面怎么择档**（决定"用户在什么环境拿到哪一档"）：
- **带 COI 头**（`COOP: same-origin` + `COEP: require-corp`）⇒ 可选**线程档**；
- **不带 COI** ⇒ 只能选**无线程档**（共享内存需要跨源隔离）；
- **选错档 ⇒ 硬失败**（不静默降级）—— 这条要**专门测**（反向断言）。

---

## §7 复跑命令

```bash
# 架构纯度闸门（姊妹仓的现役件；6 条自证）
python3 build/113/check-lane-purity.py --selftest
# 读某产物的档（权威读数）
llvm-readobj --file-headers <wasm> | grep -E "Arch:|AddressSize"
# 姊妹仓的档身份台账（现值以台账为准，别手抄）
python3 build/facts.py show w64_wasm64
python3 build/facts.py show threads_shared_memory
# 本仓 wasm64 可达性结算件（悬案 02）
bash build/113/check-wasm64-upstream.sh
```
