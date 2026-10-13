# Fork 管线与经验（2026-10-13）

> **性质**：操作手册 + 经验集。把一个**大型 C/C++ 上游**（Octave、OpenModelica 这类）
> 搬进浏览器 wasm 时，本仓用的一整套**管线纪律**，以及**踩过的坑**。
> **来源**：`Octave-Full-Wasm` 从 0 到 11.3.0 全功能 wasm 的实践（含 `LLVM-wasm`、
> `Octave-Forge-Shelf` 的旁证）。所有"坑"都是**实测踩到**的，不是推测。

---

## §0 一句话

**fork 管线 = 三件套 + 一条铁律**：
**上游 submodule（身份） + `upstream-lock.json`（URL+sha256 字节） + `provision`（供给）
+ 每提交的 pin 见证（witness）**；
铁律是 **"pin 的是 commit，跑的是容器里的树——两者必须被机器对账"**。

---

## §1 三件套：各管什么

| 件 | 管什么 | 文件 | 谁对账 |
|---|---|---|---|
| **① 身份** | 上游是**哪个仓的哪个 commit** | `build/upstream-pins.json` + `.gitmodules`（submodule） | `witness-upstream-pin.py` |
| **② 字节** | 没有官方 git 的库（tarball/zip）**从哪取、sha256 是多少** | `build/upstream-lock.json` | `zreflect/check_locks.py` |
| **③ 供给** | 把 pin 的树**流进构建容器**，并写**树指纹 stamp** | `build/provision-upstream.sh` | witness 读容器里的 `.upstream-pin` |

### 1.1 pin 形状（`upstream-pins.json`）
```json
{ "name": "octave", "kind": "tree", "provisioned": true,
  "submodule_path": "upstream/octave", "branch": "wasm/11.3.0",
  "container_path": "/src/work/upstream/octave-11.3.0",
  "why": "…为什么 pin 它…" }
{ "name": "emsdk", "kind": "toolchain", "provisioned": true,
  "submodule_path": "upstream/emsdk", "expect_version": "6.0.12" }
```
- `kind=tree` ⇒ 供给成容器树 + `.upstream-pin` stamp（内容 = `名 分支 commit dirty`）；
- `kind=toolchain` ⇒ **只断言版本串**（portable SDK 不流容器）。

### 1.2 lock 形状（`upstream-lock.json`）
```json
{ "name": "glpk", "version": "5.0",
  "url": "https://ftp.gnu.org/gnu/glpk/glpk-5.0.tar.gz",
  "file": "third_party/glpk-5.0.tar.gz", "form": "文件",
  "sha256": "4a1013ee…", "optional": true,
  "note": "optional：字节在持久盘（跨机器可缺席），本机缺席 ⇒ SKIP 明说" }
```
**`url` 是"重取入口"**，不是运行时依赖 —— 重取后以构建脚本冒烟验收。

### 1.3 witness 判据（`witness-upstream-pin.py`）
- stdout 裸值契约：`ok` / `DRIFT: …`；**退出码恒 0**（同 `witness-build-inputs`）；
- 核心：`git -C <submodule> rev-parse HEAD` **==** 容器树里 `.upstream-pin` 记的 commit；
- **零值守卫**：pins 为空 ⇒ `DRIFT: pins 为空（空断言面不是通过）`。

---

## §2 ★ 为什么"pin 了"还不够：容器里的树是**另一份拷贝**

这是 fork 管线**最重要的一条**，`Octave-Full-Wasm` 反复踩：

> **构建脚本/源码在容器里是另一份拷贝。改完仓库的 `configure`/`link.sh`/`main.cc`，
> 必须 `docker cp` 进容器，否则跑的是旧的。**

配套的两条（同族）：
1. **pin 的 commit ≠ 容器正在用的树**：submodule 指针 bump 了，容器树还是老死版本
   ⇒ **DRIFT**（witness 抓的就是这个）。
2. **改了仓库源码，容器/站点没跟** ⇒ "能编过"但编的是旧件。判据 = 产物 sha + 树指纹。

---

## §3 构建：交叉编译 + 产物自证

### 3.1 交叉编译的硬约束（Octave 的实测，OpenModelica 同族）
| 约束 | 后果 |
|---|---|
| 所有入链对象必须 `-fPIC` | 否则 wasm-ld 报 `recompile with -fPIC`（side module 尤其） |
| **无 shell、无子进程** | `system`/`popen` 恒失败 ⇒ 任何依赖外部命令的构建步骤直接出局 |
| **无真线程/OpenMP**（除非显式开） | 有些库探测到 `-fopenmp` 就要求 shared-memory ⇒ 链不过 |
| **工具链版本要钉死** | emsdk 5.0.7 → 6.0.12 迁移时，clang 24 **改名**了 EH personality 符号 ⇒ keep-list 必须跨版本重生成 |

### 3.2 产物自证（**别信"链过了"**）
链接时写出 `<产物>.build.json`（**只记量到的事实**），**`verdict=="ok"` 才可部署**。
手跑构建脚本的产物 `declared` 是 `null` ⇒ 判拒；补判用受管辖入口的 `verify`。

### 3.3 白名单仓库（.gitignore）
**默认拒绝一切，逐项放行**（`*` + `!路径`）。理由：黑名单是"忘了就提交"
（敏感/大产物悄悄进仓），白名单是"忘了就报错"（`check-whitelist.py` 在 pre-commit 拦下）。
**⚠️ 盲区**：`check-whitelist.py` 只看**已暂存**的文件 ⇒ 被忽略且从未 `git add` 的文件
它看不见（曾漏掉 4 个承重文件）。新增目录后主动看一眼 `git status --short --ignored <目录>`。

---

## §4 ★ 受管辖入口：改站点的唯一合法通道

**教训**：为了试一个页面改动，顺手 `cp` 进了生产站点 ⇒ **把站点弄坏了**
（页面按 COI 选线程档，而那份站点没有 `threads/` ⇒ 404）。

**解法**：每个"会改站点/产物"的动作都走一个**受管辖入口**，它必须带三件：
- `--dry-run`（只打印要做什么）；
- `--verify`（只核不写）；
- `--selftest`（**证明它会红**，在夹具上做，不碰真站点）。
且都带**"不许夹带别的改动"的反向断言**。

`Octave-Full-Wasm` 的入口分工（本仓照此设计）：
| 批次类型 | 入口 |
|---|---|
| 换产物 | `promote-webgl.sh` |
| 只改页面资产 | `promote-pages.sh` |
| 某车道（wasm64） | `promote-w64-lane.sh` |
| 改 `.m` 胶水 | `promote-pages.sh` 的 `M_ASSETS` 旋钮（空 = 老行为） |

---

## §5 ★ 事实纪律（每句"现在如此"都要能被复跑证明）

**照抄旧话是文档说假话的唯一来源**（一天里抓到过 5 处）。五条：

1. **数值/行为只认实测**，并把**复跑方式写在断言旁边**；写不出复跑方式的句子 ⇒ 只能当历史。
2. **口径搬进代码，别在文档里手抄命令**。重链的唯一入口是一个脚本的**模式表**
   （决定全部环境变量）；要看口径就 `explain <模式>`（**那就是文档，生成物**）。
   **"赋值了但没被引用"的旗标会静默失效** —— 改旗标组之后必须有一条**从产物里读出来**的自检。
3. **"能编过 ≠ 能用了"**：碰运行期行为（图形/字体/加载路径/资源）必须**浏览器侧**实测。
4. **断言要能证伪**：替身不能比真实对象松；新契约至少配一条**反向**断言（该报错的必须报错）。
   行为变了就**翻面**（改断言，别改检查器）。
5. **断言有生命周期：实测 / 推断 / 翻案**。活状态文档只写实测；推断进 NOTES 并注明
   **哪个实验能结案**；被推翻的进 `retractions.json`（它**重新出现**时报错）。

---

## §6 ★ 操作习惯与硬坑（别再来一次）

- **禁止 `sleep`**（用户点名）。任何形式都不行 —— 长任务用 `run_in_background`，
  起完就返回、去干别的，**等完成通知**；盯已有进程用 `tail -f --pid=<pid>`。
- **重活用 `setsid nohup … &` 起、输出只 `tail -n`/`grep`**；跑验收时**别并行干重活**
  （并发 docker commit/压缩曾让一个套件假崩）。
- **测试用例从仓库原路径直跑**，别 `cp` 一份到 harness 再跑（改完仓库用旧副本跑，
  断言红绿全错位）。
- **跑测试前先验产物 SHA**（磁盘/HTTP/页面实例化三层）——"改完程序用老产物跑"反复踩。
- **shell 陷阱**：`pkill -f 'x'` 会匹配到自己（用 `'x[y]'`）；`rc=$?` 接在管道后拿的是
  最后一个命令的状态；`&&` 放在 `&` 前会把整条链后台化；`echo` 里的反引号会被当命令替换；
  `grep -c` 零命中**退出 1**；正则字符类漏数字（`[A-Z_]+` 匹配不到 `P5_OBJS`）。
- **别猜挂载点**：打包工具"挂到哪"要**逐字读**配置（少写一层会把文件铺错位置，
  曾把整棵核心树摘掉）。**别猜版本号/路径/旗标**，一律从产物或配置里**读出来**。
- **探测/自检不许放在开机路径上**：坏产物会让**整页卡死**，连带所有验收全挂。
  探测器要**按需触发 + 带超时**。

---

## §7 ★ 验收底线（固定动作，缺一步等于没做完）

```
开工预检（doctor） → 实验（8768）→ 生产（8761）→ 开机自检 → 三层 SHA
→ 全量回归（PROBES=1）→ 三处一致（parity --strict）→ 六道闸门 → 提交 → 推镜像
```

- **生产站点只由受管辖入口改**（§4）；
- **上站候选必须过「全量」才叫候选**：只跑几个"数值套件"就发运，曾在全量里炸
  （唯一大量压 `dlopen` 的套件 71/0→44/27）；
- **三层 SHA 不全绿就停**（磁盘 / HTTP / 页面实例化）；
- **双档/四格站点**要验"带头选线程档 / 不带头落基础档 / 选错档硬失败"。

---

## §8 三线分支模型（本仓要复刻）

`Octave-Full-Wasm` 的线划分（用户点令，2026-10-12）：**一线一架构**。

| 线 | 产物 | 只编 |
|---|---|---|
| `master` | wasm64 | wasm64 |
| `wasm32` | wasm32 | wasm32 |
| `IllegalPerformance` | 性能线（SIMD/线程/优化库） | 视档 |

**判据可执行**：架构纯度闸门 —— 宿主 / 车道模块 / 站点**本档专属**目录三处同档；
错档逐条点名、rc=1。**零值守卫**：别把基础档目录喂进去（多档站里它们合法装着另一档的模块，
查了必假红）。

**为什么成文**：混编的失败模式是"**两边都建成功、自检全绿、运行期才炸**"
（wasm32 对象链进 wasm64 / 错档模块进宿主，实测三次）。

---

## §9 复跑命令

```sh
# pin 见证
python3 .githooks/witness-upstream-pin.py --selftest
# lock 判定
python3 zreflect/check_locks.py --selftest
# 白名单
python3 .githooks/check-whitelist.py
# 架构纯度（本仓要照写的闸门）
python3 build/113/check-lane-purity.py --selftest
# 受管辖入口自证
sh build/promote-*.sh --selftest
```

---

## §10 本仓（OpenModelica-Full-Wasm）的落地映射

| 管线件 | 本仓对应 |
|---|---|
| 上游 pin | `upstream/openmodelica` + `upstream/OMCompiler-3rdParty` + `upstream/OMBootstrapping`（**三者 SHA 同动**） |
| lock | MSL 版本+sha256、wasi-libc/wasm-ld 版本断言 |
| 供给 | `build/provision-upstream.sh`（容器 + `.upstream-pin` stamp） |
| 工具链 | **Rust + `wasm32-wasip1` + wasi-libc + wasm-ld**（官方 CMake 目标；**不是 emsdk**） |
| 产物自证 | `omc.build.json`（`verdict=="ok"` 才可部署） |
| 受管辖入口 | `build/promote-*.sh`（三线各一） |
| 三线 | `master`(wasm64) / `wasm32` / `IllegalPerformance` |
| 白名单 | `.gitignore`（本仓已建，`*` + `!路径`） |
