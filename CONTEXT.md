# CONTEXT.md · 术语表

> 每个词一条**权威定义** + 一行**可跑的复跑证据**（写不出复跑的，不进本表）。

## 本项目相关

**OpenModelica（OM）**
Modelica 语言的开源实现：编译器（`omc`）+ 仿真运行时。**不是** Octave 的插件，
是**平级的另一门语言 + 另一个引擎**。
复跑：`gh api repos/OpenModelica/OpenModelica --jq '{lang:.language,size:.size}'`

**Modelica**
面向对象、**非因果**（方程级）的物理建模语言。与 MATLAB/Octave 的**命令式**语义相反：
Modelica 里写的是方程（`v = der(h)`），求解器负责排序与解 DAE。
复跑：`gh api repos/modelica/ModelicaStandardLibrary/contents/Modelica --jq '.[].name'`

**MSL（Modelica Standard Library）**
Modelica 标准库，覆盖跨域物理域（Electrical/Fluid/Thermal/Mechanics/Magnetic/Blocks…）。
**这是轴 ③ 的实体**（本仓存在的理由）。
复跑：`gh api "repos/modelica/ModelicaStandardLibrary/contents/Modelica" --jq '.[]|select(.type=="dir")|.name'`

**轴 ①②③（本仓与姊妹仓的分工）**
MATLAB 生态的三根轴：① 语言（`.m`/矩阵）、② Simulink 因果块图、③ Simscape 非因果物理建模。
姊妹仓=①+②；**本仓=③**。
复跑：`sed -n '/§8/,/§9/p' /mnt/hdd/zcode-projects/Octave-Full-Wasm/build/113/NOTES-experiment-omc-wasm.md`

**DAE / index-1 / index-3**
微分代数方程。**index-1** 是"代数约束可直接解"的形态（Octave 的 `ode15i`/`Mass` 矩阵能解）；
**index-3** 是带位置约束的机械系统形态，**需要指标约简**（符号处理）才能数值求解。
复跑（姊妹仓实测）：`grep -A8 "index-1" /mnt/hdd/zcode-projects/Octave-Full-Wasm/build/113/NOTES-experiment-omc-wasm.md | head -20`

**指标约简（index reduction）**
把 index-3 的方程**符号化降阶**成 index-1 的过程（Pantelides 算法等）。
**这是 OpenModelica 编译器的核心工作**，Octave（数值语言）没有这层。
复跑：见上条同一处实测（约束摆 `IDASolve failed` ⇒ 缺的就是它）。

**`.mat` 握手**
两引擎的交换方式：OM 仿真产出 `.mat`（MAT4），Octave `load` 读入做后处理。
**两边现成都有的东西**，不是要新造的桥。
复跑：`grep -B2 -A10 "dump MAT4" /mnt/hdd/zcode-projects/Octave-Full-Wasm/build/113/NOTES-experiment-omc-wasm.md`

**`sendExpression` ↔ `omc_eval`（脚本协议）**
OM 对外暴露的通用命令接口。MATLAB 侧客户端 `OMMatlab` 用 `sendExpression` 经 ZeroMQ 连
本地进程；**浏览器官方 wasm 用 `omc_eval`**（直接函数调用）。**同一协议，两个传输层**。
复跑：`gh api "repos/OpenModelica/OpenModelica/contents/OMCompiler/Compiler/OpenModelica.rs/wasm/omc-cli.js" --jq .content | base64 -d | grep -oE 'omc_[a-z_]+' | sort -u`

**`wasm-jit`（官方 wasm 目标）**
OM 的 `--simCodeTarget=wasm-jit`：跳过 C 代码生成，直接产出 wasm 模块加载运行。
⚠️ 求解器覆盖窄（官方原文：1 dense linear solver / Newton / Euler / dassl）。
复跑：`gh api "repos/OpenModelica/OpenModelica/contents/OMCompiler/Compiler/OpenModelica.rs/README.md" --jq .content | base64 -d | grep -A6 'wasm-jit'`

**`RUST_OMC_WASM_RUNTIME`（官方 CMake wasm 目标）**
OM 官方树里的第一方 wasm 构建目标（`OMCompiler/Compiler/.cmake/rust_omc.cmake`）。
本仓走这条，**不是**第三方 emception 配方。
复跑：`gh api "repos/OpenModelica/OpenModelica/contents/OMCompiler/Compiler/.cmake/rust_omc.cmake" --jq .content | base64 -d | grep -cE 'RUST_OMC_WASM'`

**一线一架构（line purity）**
用户点令（2026-10-12）：`master` 线只编 wasm64、`wasm32` 线只编 wasm32。
判据可执行：宿主 / 车道模块 / 站点本档专属目录**三处同档**。
复跑：`python3 build/113/check-lane-purity.py --selftest`

## 事实系统（Einfacht）相关

**Einfacht**
反幻觉事实系统：事实台账 / 翻案台账 / 悬案台账 + 必须能红的闸门。
**机制层** vendored 进 `zreflect/`；**数据层**是本仓的 `measure_openmodelica.py`。
复跑：`sh gates-selftest.sh`

**事实台账（FACTS.json）**
数字的**唯一产地**。每条 = 一个测出来的值 + **复跑命令**（逐字执行）。
**正文不手抄数字**，写 `[[键名]]`。
复跑：`python3 zreflect/check_facts_replay.py`

**翻案台账（retractions.json）**
被推翻的断言登记在册；它**重新出现**时报错。
复跑：`python3 zreflect/check_retractions.py --selftest`

**悬案台账（questions / .scratch/open-questions/issues）**
未结案的问题，每条挂**可跑的结算件**（头部 `**Settling:**`）。写不出结算件的只能降级成 NOTES 里的猜想。
复跑：`python3 zreflect/check_questions.py --selftest`

**闸门自证（`--selftest`）**
每个闸门必须能证明**自己会红**，且三类用例齐备：**正常不报 / 该报的必须报 / 空输入必须报**。
复跑：`sh gates-selftest.sh`

**runs_at / ran·off·failed（C1/C2）**
闸门的**频率是声明字段**（不是文件名里有没有 `check_`）；`off` 与"跑过且通过"**必须可区分**。
复跑：`python3 zreflect/registry.py --run commit`

**幻影旋钮（phantom knob）**
文档/代码承诺了、但**没人登记**的环境变量 ⇒ 用户配了**静默无效**。
C4 的"名录对账"抓这个（本仓建仓时被抓到一次，已修）。
复跑：`python3 zreflect/knobs.py --selftest`

## fork 管线相关

**fork 管线三件套**
① 身份 = `upstream-pins.json`（submodule + commit）；
② 字节 = `upstream-lock.json`（URL + sha256）；
③ 供给 = `provision-upstream.sh`（流进容器 + 写树指纹 stamp）。
复跑：`python3 .githooks/witness-upstream-pin.py --selftest`

**白名单仓库**
`.gitignore` 用 `*` + `!路径`：**默认拒绝一切、逐项放行**。
黑名单是"忘了就提交"，白名单是"忘了就报错"。
复跑：`python3 .githooks/check-whitelist.py`

**受管辖入口（promote 脚本）**
改站点的**唯一合法通道**：必须带 `--dry-run` / `--verify` / `--selftest`，
且带"不许夹带别的改动"的反向断言。
复跑：`sh build/promote-*.sh --selftest`（本仓待建）

**三层 SHA**
产物一致性的三个层次：**磁盘** / **HTTP** / **页面实例化的字节**。不全绿就停。
复跑（姊妹仓形态）：`sh build/check-deploy-sha.sh <站点> <sha> <URL>`
