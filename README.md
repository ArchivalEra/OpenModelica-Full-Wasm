# OpenModelica-Full-Wasm

[![readme-sync](https://img.shields.io/github/actions/workflow/status/ArchivalEra/OpenModelica-Full-Wasm/readme-sync.yml?branch=master&style=flat-square)](https://github.com/ArchivalEra/OpenModelica-Full-Wasm/actions/workflows/readme-sync.yml)
[![facts](https://img.shields.io/github/actions/workflow/status/ArchivalEra/OpenModelica-Full-Wasm/facts.yml?branch=master&style=flat-square)](https://github.com/ArchivalEra/OpenModelica-Full-Wasm/actions/workflows/facts.yml)
[![python](https://img.shields.io/badge/python-3.13%2B-blue?style=flat-square)](.github/workflows/facts.yml)
[![toolchain](https://img.shields.io/badge/clang24%20%2B%20Rust%20nightly-toolchain-informational?style=flat-square)](build/113/provision-toolchain.sh)
[![upstream](https://img.shields.io/badge/OpenModelica-cbff5eb7-informational?style=flat-square)](build/upstream-pins.json)
[![engine](https://img.shields.io/badge/Modelica-engine-orange?style=flat-square)](docs/REQUIREMENTS.md)
[![lane](https://img.shields.io/badge/wasm32-lane-blue?style=flat-square)](STATE.md)
[![COI](https://img.shields.io/badge/COI-not%20required-success?style=flat-square)](STATE.md)
[![facts](https://img.shields.io/badge/Einfacht-powered-purple?style=flat-square)](https://github.com/ArchivalEra/Einfacht)

[English](README.md) · [中文](README.zh.md) · [Deutsch](README.de.md)

OpenModelica（Modelica 编译器 + 仿真运行时）编译成 WebAssembly，跑在浏览器里。纯客户端计算，没有服务端执行端点。

姊妹仓：[Octave-Full-Wasm](https://github.com/ArchivalEra/Octave-Full-Wasm)（MATLAB 语法那一侧的引擎）· 事实系统：[Einfacht](https://github.com/ArchivalEra/Einfacht)

## 为什么有这个仓

MATLAB 生态有三根轴：

| 轴 | 是什么 | 谁覆盖 |
|---|---|---|
| ① | MATLAB 语言（`.m` / 矩阵语义） | Octave-Full-Wasm |
| ② | Simulink（因果块图） | Octave-Full-Wasm 引擎 + 一个 JS 前端 |
| ③ | Simscape（非因果物理建模：电/流体/热/机械…） | 本仓 |

第 ③ 轴姊妹仓给不了：Octave 是数值/命令式语言，没有"符号化 + 指标约简 + DAE"那套机器。实测（姊妹仓页面）：Octave 能解 index-1 DAE（RC 电路 V(5)=0.9931，理论 0.9933），解不了 index-3（约束摆 IDASolve failed）——而指标约简正是 OpenModelica 编译器的核心工作。两个引擎是接力，不是重复。

## 两个引擎怎么配合（同一个 `.mat` 通道）

```
OpenModelica 档：方程级物理建模（符号化 + 指标约简 + MSL 物理库）
                        │ 仿真
                        ▼
                 xxx_res.mat（MAT4）
                        │
Octave 档：load → 数值求解 + 控制/信号/统计 + 矩阵语言 → 画图/分析
```

这与 MATLAB 里"Simscape 建模、MATLAB 分析"是同一个分工，只是用两个 wasm 引擎实现，中间用 `.mat`（OM 仿真输出就是 MAT4；Octave 读写 `.mat` 实测全通）。

## 走官方路线

OpenModelica 官方主仓有第一方 wasm 构建目标（`OMCompiler/Compiler/.cmake/rust_omc.cmake`）。本仓照这条走：上游 submodule + 自己交叉编 + 同源托管。工具链是 Rust + wasm32-wasip1（姊妹仓是 emsdk，两边不互相 submodule）。

## 两条线（一线一架构）

```
master              → 产物 wasm64（上游未接路径，暂出 wasm32 产物）
wasm32              → 产物 wasm32，只编 wasm32
```

判据：`python3 build/113/check-lane-purity.py`（宿主 / 模块 / 站点本档专属目录三处同档，错档逐条点名，喂错档必须红）。

性能线 IllegalPerformance 已按用户点令删除（2026-10-14）：wasm64 按官方 fork 管线做到生产级之后才值得脱离官方树的开发；原线对象钉在 tag `archive/ilperf-f283610`，wasm64 生产级后重建。两条线内容已同步，`git diff master wasm32 --stat` 应为空。

当前发布 v0.1.0-wasm32（版本身份证 `build/VERSION.json`，发布说明 `docs/RELEASE-v0.1.0-wasm32.md`）。

## 状态

每条需求带可复跑判据，当前全绿（过程细节在 `HISTORY.md` 与 `.scratch/open-questions/issues/`）：

| 需求 | 判据 | 结果 |
|---|---|---|
| A 官方 wasm 目标出产物 | `bash build/113/build-omc-wasm.sh --verify` | verdict=ok |
| B 浏览器内跑通模型 | `sh test/browser/run-omc-page.sh` | 10 PASS / 0 FAIL |
| C 两线 + 架构纯度 | `python3 build/113/check-lane-purity.py --selftest` | 24 PASS / 0 fail |
| D 与 Octave 的 `.mat` 握手 | `sh test/browser/run-mat-handshake.sh` | 14 PASS / 0 FAIL |
| E MATLAB 语义桥 `omc_*` | `sh test/browser/run-omc-bridge.sh` | 11 PASS / 0 FAIL |
| 同页集成（双引擎一页面） | `sh test/browser/run-samepage.sh` | 8 PASS / 0 FAIL |
| MSL 站内资产（离线装库，mail/016） | `site/msl-local.html`（8765 站点） | MSL-LOCAL PASS |
| MSL 出表（producer 态 content-list） | `python3 build/113/check-msl-content-list.py` | producer ok / site ok |
| JS 胶水件产地（`files[]` 投影） | 台账 `omc_web_js_sha` / `omc_web_js_bytes` | 30 条事实逐字复跑 |
| E 线桥交付（产品态，零注入） | `sh test/browser/run-omc-bridge-product.sh <URL>` | 装配前 5 PASS/3 FAIL（缺口），装配后 8/0 |
| 桥产品件语义（三条承重） | `node build/113/check-omc-bridge.mjs` | 7 PASS / 0 fail |
| Export FMU（外部验收抓到的缺陷，已修） | `sh test/browser/run-export-fmu.sh` | 6 PASS / 0 FAIL |

- 产物：web 档 74.6 MB（`-Oz` 后，sha 见台账 `omc_web_wasm_sha`）；无 COI 依赖（0 原子指令 / 0 线程导入，普通 http.server 就能服务）。
- 同页"不可行"的旧结论已翻案（测量方法错，见 `build/retractions.json`）；Export FMU 的缺陷根因是本仓 clang24 比上游 CI 新、写的 `dylink.0` 子段 6 上游链接器不认，修法 = `build/113/strip-dylink-features.py` 剥离并挂进构建链。
- wasm64 的边界：工具链侧可做（`build/113/build-w64-spike.sh`，8.8 秒编成），缺的是上游 CMake 路径（`rust_omc.cmake` 0 命中 wasm64）——等上游接，不是编不出来。
- 下一步：需求 F（Octave-UI 集成）。

## 事实系统

数字的唯一产地是 `build/FACTS.json`；文档正文不手抄数字，写 `[[键名]]`；每条事实带复跑命令，闸门每次提交逐字执行；每个闸门必须能证明自己会红（`sh gates-selftest.sh`）。一条实战教训：波动的观测量（JS 堆、耗时）不能以原值进台账，要取粗于噪声的量级档并在 `cmd` 里做同样的取整，逐字复跑才稳定。

## 文档地图

| 文件 | 内容 |
|---|---|
| `docs/REQUIREMENTS.md` | 需求书：要做什么，每条带实测现状 + 验收判据 |
| `docs/EINFACHT-INTEGRATION.md` | Einfacht 接入方法（含 7 个实测坑） |
| `docs/FORK-PIPELINE-AND-LESSONS.md` | fork 管线与全部经验 |
| `docs/LANES-AND-MEMORY-MODEL.md` | 内存架构与分支线经验（三次混编事故、纯度闸门判据） |
| `maintaince.md` | 方向与地图 |
| `STATE.md` | 活状态（文末机器块由台账渲染） |
| `AGENTS.md` | 给 agent 的硬规矩 |
| `CONTEXT.md` | 术语表 |
| `HISTORY.md` | 历史（append-only） |
| `mail/` | 跨 agent 通信收件箱（四仓集群的往来记录，规矩见 `mail/README.md`） |

## 许可

AGPL-3.0-or-later（见 `LICENSE`）。上游 OpenModelica 是 AGPLv3 / OSMC-PL 双选，与本仓兼容；上游第三方库各自许可见 `THIRD-PARTY-NOTICES.md`。
