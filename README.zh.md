# OpenModelica-Full-Wasm

[English](README.md) · [中文](README.zh.md) · [Deutsch](README.de.md)

**OpenModelica**（Modelica 编译器 + 仿真运行时）→ **WebAssembly**，跑在浏览器里，
**纯客户端计算、无服务端执行端点**。

> 🔒 本仓是 **private**。姊妹仓 [`Octave-Full-Wasm`](https://github.com/ArchivalEra/Octave-Full-Wasm)
> 是**平级**的另一半（那个跑 MATLAB 语法那一侧）。

---

## 为什么有这个仓（一句话）

MATLAB 生态有**三根轴**：

| 轴 | 是什么 | 谁覆盖 |
|---|---|---|
| ① | MATLAB **语言**（`.m` / 矩阵语义） | `Octave-Full-Wasm` |
| ② | **Simulink**（因果块图） | `Octave-Full-Wasm` 引擎 + 一个 JS 前端 |
| ③ | **Simscape**（**非因果物理建模**：电/流体/热/机械…） | **本仓** |

第 ③ 轴姊妹仓**天然给不了**：Octave 是数值/命令式语言，没有"符号化 + 指标约简 + DAE"那套机器。
**实测证据**（姊妹仓 8761 页面实测）：Octave 能解 **index-1 DAE**（RC 电路 `V(5)=0.9931`，
理论 `0.9933`），但**解不了 index-3**（约束摆 `IDASolve failed`）—— 而指标约简
**正是 OpenModelica 编译器的核心工作**。两个引擎是**接力**，不是重复。

## 两个引擎怎么配合（同一个 `.mat` 通道）

```
OpenModelica 档：方程级物理建模（符号化 + 指标约简 + MSL 物理库）
                        │  仿真
                        ▼
                 xxx_res.mat（MAT4）
                        │
Octave 档：load → 数值求解 + 控制/信号/统计 + 矩阵语言 → 画图/分析
```

这与 MATLAB 里 **"Simscape 建模、MATLAB 分析"** 是**同一个分工**，只是用两个 wasm 引擎实现，
中间用 `.mat` 而不是共享内存。`.mat` 握手**两边现成都有的东西**（OM 仿真输出就是 MAT4；
Octave 读写 `.mat` 实测全通）。

## 走官方路线（不是第三方配方）

OpenModelica **官方主仓**有第一方 wasm 构建目标（`OMCompiler/Compiler/.cmake/rust_omc.cmake`）：
`RUST_OMC_WASM_RUNTIME`、`wasm32-wasip1` 交叉编、`omc.wasm`、产物交接、`wasm-jit` 运行时。
⇒ **本仓照这条走** —— 也就是"上游 submodule + 自己交叉编 + 同源托管"，
**与 `Octave-Full-Wasm` 是同一种仓库**（区别只在工具链：本仓 **Rust + wasm32-wasip1**）。

## 三条线（一线一架构）

    master              → 产物 wasm64，只编 wasm64
    wasm32              → 产物 wasm32，只编 wasm32
    IllegalPerformance  → 性能线（SIMD / 多线程 / 优化库）

判据 = `python3 build/113/check-lane-purity.py`（宿主 / 模块 / 站点本档专属目录三处同档；
错档逐条点名、rc=1；反向断言：喂错档必须红）。

## 事实系统（Einfacht，反幻觉）

数字的**唯一产地**是 `build/FACTS.json`；文档正文**不手抄数字**，写 `[[键名]]`；
每条事实旁写**复跑命令**，闸门每次提交逐字执行。每个闸门必须**能证明自己会红**
（`sh gates-selftest.sh`）。

## 文档地图

| 文件 | 内容 |
|---|---|
| `docs/REQUIREMENTS.md` | **需求书**：要做什么，每条带实测现状 + 验收判据 |
| `docs/EINFACHT-INTEGRATION.md` | **Einfacht 接入方法**（含 7 个实测坑） |
| `docs/FORK-PIPELINE-AND-LESSONS.md` | **fork 管线 + 全部经验**（怎么搬上游、怎么维护） |
| `maintaince.md` | 方向与地图 |
| `STATE.md` | 活状态（+ 文末机器块） |
| `AGENTS.md` | 给 agent 的硬规矩 |
| `CONTEXT.md` | 术语表（每词一条定义 + 一行复跑证据） |
| `HISTORY.md` | 历史（append-only） |

## 现行状态

**骨架期**（2026-10-13 建仓）：三线分支就位、事实系统已接入并通过自证；
**还没有任何构建产物**（`omc.wasm` 尚未 build）。下一步见需求书 **需求 A**。

## 许可

**AGPL-3.0-or-later**（见 `LICENSE`）。
上游 OpenModelica 是 **AGPLv3 / OSMC-PL 双选** —— 与本仓兼容。
上游第三方库各自许可见 `THIRD-PARTY-NOTICES.md`。

## 文件清单（自动）

<!-- AUTO:FILES -->
<!-- /AUTO -->
