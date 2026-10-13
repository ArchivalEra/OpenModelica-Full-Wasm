# 第三方组件与许可（THIRD-PARTY-NOTICES）

> 本仓**骨架期**（2026-10-13 建仓），**尚未引入任何上游源码**。本文件先立骨架：
> 把**将要引入的**第三方逐条记明许可，等真正 vendor/submodule 进来时逐条核。
> **纪律**：任何新上游进仓前，先在这里加一条 + 核对 `spdx`，否则视为未完成引入。

## 本仓

| 组件 | 许可 | 说明 |
|---|---|---|
| 本仓自有代码 | **AGPL-3.0-or-later** | 见根 `LICENSE` |

## 计划引入的上游（待核）

| 组件 | 上游 | 许可（上游声明） | 状态 |
|---|---|---|---|
| **OpenModelica** | `github.com/OpenModelica/OpenModelica` | **AGPLv3 / OSMC-PL 双选**（`OSMC-License.txt`） | 待引入（submodule） |
| OMCompiler-3rdParty | `github.com/OpenModelica/OMCompiler-3rdParty` | 逐库核（含 SUNDIALS/KLU/UMFPACK/Lis 等） | 待引入（**与 OM SHA 同动**） |
| OMBootstrapping | `github.com/OpenModelica/OMBootstrapping` | 同上 | 待引入（**与 OM SHA 同动**） |
| Modelica Standard Library | `github.com/modelica/ModelicaStandardLibrary` | 逐版核（MSL 用 OSMC-PL/CC 类） | 待引入（lock） |
| wasi-libc | `github.com/WebAssembly/wasi-libc` | Apache-2.0 WITH LLVM-exception（含例外） | 待引入（工具链） |
| Einfacht（事实系统机制层） | `github.com/ArchivalEra/Einfacht` | 见上游 `LICENSE` | **已 vendored**（`zreflect/` + `reflect-hooks/`） |

## ⚠️ 核许可是引入的**前置条件**，不是事后补的记录

- OpenModelica 的 **AGPLv3/OSMC-PL 双选**与本仓 AGPL-3.0 **兼容**（这条已核，是本仓选它的
  前提之一）；
- 但 **OMCompiler-3rdParty 里是逐库许可**（SUNDIALS=BSD-3、KLU/UMFPACK=LGPL/GPL 系…）
  ⇒ **vendor 前逐库列明**，别只抄一句"跟 OM 一样"。

## 复跑（核对上游许可声明）

```bash
gh api "repos/OpenModelica/OpenModelica/contents/OSMC-License.txt" --jq .content | base64 -d | head -12
gh api repos/OpenModelica/OpenModelica --jq '.license'
gh api repos/modelica/ModelicaStandardLibrary --jq '.license'
gh api repos/WebAssembly/wasi-libc --jq '.license'
```
