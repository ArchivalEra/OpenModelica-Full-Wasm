# HISTORY · 历史（append-only）

> 只追加，不改写。被推翻的断言进 `build/retractions.json`（不在这里删）。
> 每条带"当时是什么状态"，**当历史读，别当现状**（现状看 `STATE.md`）。

## 5.x 建仓：骨架期（2026-10-13）

- **起因**：用户点令"给那个块图仓删了或者改名成 OpenModelica-Full-Wasm，AGPL3，
  把需求书和 Einfacht 接入方法和 fork 管线制作方法和你的所有经验做成三个 md 放仓库里。
  那个仓库也应该出 wasm32 和 wasm64 和 IllegalPerformance 三条线…记住那个仓库得是 private。
  再配上白名单 gitignore，然后最后克隆到 /mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/"。

- **澄清了一件事**：用户说的"那个块图仓"在 GitHub org 里**不存在**（查证：org 全仓列表
  无 block/diagram/modelica/omc 相关仓）⇒ 所以没有"删除/改名"动作，**只有建仓**。
  `master` 分支不叫 `main`（照姊妹仓习惯）。

- **建的东西**：
  - `ArchivalEra/OpenModelica-Full-Wasm`（**private**，AGPL-3.0）；
  - 三份经验文档（用户点令）：`docs/REQUIREMENTS.md`（需求书）、
    `docs/EINFACHT-INTEGRATION.md`（Einfacht 接入，7 个实测坑）、
    `docs/FORK-PIPELINE-AND-LESSONS.md`（fork 管线 + 全部经验）；
  - 白名单 `.gitignore`（48 条放行规则）；
  - Einfacht 机制层 vendored（`zreflect/` 27 文件 + `reflect-hooks/`）+ **本仓数据层**
    `zreflect/measure_openmodelica.py`；
  - 三线分支：`master` / `wasm32` / `IllegalPerformance`；
  - 本仓专属闸门 `build/113/check-lane-purity.py`（8 条自证，含 4 条反向断言）。

- **对上游 Einfacht 做了一处改进**：数据层模块名从**写死**（`measure_octave`）改成
  旋钮 `REFLECT_MEASURE_MODULE` ⇒ "换仓库只换一个文件"这条承诺才真成立。

- **★ 那次改进立刻被 C4 闸门抓了一次**：第一版顺手引入了第二个环境变量（严格模式），
  而它**没进旋钮登记表** ⇒ `facts.py --render-doc` 当场报
  "记号 `REFLECT_MEASURE_STRICT` 出现在 zreflect/*.py 里但不在旋钮登记表 —— 幻影旋钮"。
  ⇒ **这就是 C4「名录对账」要抓的形状**（文档承诺了、代码不读 ⇒ 配了静默无效）。
  修法：**不引入那个变量**（模块不在就静默回落通用占位）。
  附带教训：给"将来可能用"的名字留位子 = 自己制造幻影。

- **上游可行性（本批之前的查证，记在此备查）**：Modelica 能在浏览器跑 —— 第三方
  `omc-web` 演示把 `BouncingBall.mo` 跑通 `parse → C → 浏览器内编译 → 仿真 → 出图`；
  但**官方路线**是第一方 CMake wasm 目标（`rust_omc.cmake` 的 `RUST_OMC_WASM_RUNTIME`），
  本仓走官方。详细实测在姊妹仓
  `Octave-Full-Wasm/build/113/NOTES-experiment-omc-wasm.md`（§1–§11）。
