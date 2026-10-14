# 03 · 需求 B：simulate() 在 wasm 里跑不起来（宿主要求 `rt_host_lin_solve` 回调）

**Status:** resolved
**Settling:** `bash build/113/build-omc-wasm.sh --verify && node test/node/accept-omc-simulate.mjs` —— rc=0 ⇒ A（模型在 Node 里跑完并产出 `.mat`，需求 B 结案）；rc=1 ⇒ B（仍失败，脚本打印卡在哪一层）；rc=2 ⇒ C（产物目录不在，环境问题不是结论）

## ★ 结案（2026-10-14）

`node test/node/accept-omc-simulate.mjs` → **10 PASS / 0 FAIL**。实跑证据：
- 仿真跑完：`messages` 含 `LOG_SUCCESS | info | The initialization finished successfully`；
  `resultFile = "/tmp/BouncingBall_res.mat"`；
- 结果真产出：25,729 字节，**MAT4**（首矩阵类型码 51 + 4×11 `Aclass` + `imagf=0`，
  与上游 `openmodelica_mat_writer/src/lib.rs:405-413 write_mat_header` 精确一致），
  已落盘宿主供需求 D 用；
- **数据是真物理**（深验）：`h` 从 1.0 起按 `der(v)=-g, der(h)=v` 衰减，500 点齐全
  （min −0.9556 / max 1.0000 —— 含 `when h<=0 reinit` 的弹跳）；
- 产物新 sha：`OpenModelicaCompiler_bg.wasm` = **91,152,188** 字节
  （比修复前 88.7MB 大：多了 in-wasm 求解器）。

**关键复跑命令**：`node test/node/accept-omc-simulate.mjs`（判据住在探针里，含反向用例）。

## 现象（2026-10-13 实测）

- `loadFile` → **true**、`getClassNames()` → **{BouncingBall}**、`translateModel` → **true**
  （并真的写了 `/tmp/BouncingBall.wasm`，`wasi_path_open → 5` = 有效 fd）⇒ **编译器前端全通**。
- `omc_simulate('BouncingBall', 3.0, 500, 1e-6, 'dassl', '')` → 失败，报文逐字：
  ```
  wasm-jit simulation failed: wasm engine error: Start(RuntimeError { source: Js(Trap {
    inner: Js(Message("WebAssembly.Instance(): Import #0 \"env\" \"rt_host_lin_solve\":
    function import requires a callable
  ```
  ⇒ **实例化模型模块时**缺一个宿主函数。

## 根因（已定位，逐字证据）

1. 模型模块 import `env.rt_host_lin_solve`；它的**服务者**应当是"运行时 wasm"。
2. 运行时 wasm 有两个变体（`openmodelica_wasm_jit/build.rs:1768-1775` 判据原文）：
   ```rust
   let native = std::env::var("CARGO_CFG_TARGET_ARCH").as_deref() != Ok("wasm32");
   let wasmer = std::env::var("CARGO_FEATURE_ENGINE_WASMER").is_ok();
   let inwasm_driver = std::env::var("CARGO_FEATURE_INWASM_DRIVER").is_ok();
   let mut features = match (native && !wasmer, inwasm_driver) {
       (true, false) => "host_lin_solve,host_log",                    // ← native 默认：甩给宿主
       (true, true)  => "session,inwasm_solve,host_lin_solve,host_log",
       (false, _)    => "session,inwasm_solve,host_log",              // ← web：在 wasm 内求解
   };
   ```
   ⇒ **native 宿主那一支带 `host_lin_solve`**（把稀疏线性求解委派给宿主原生求解器）；
   **web 那一支带 `inwasm_solve`**（用 rsparse 在 wasm 内解）。
3. 本仓两步链里，交接件 `blobs/runtime_wasip1_interactive.wasm` 是 **stage1（native 宿主）**
   编的，stage2 **按文件名直接复用**它（`build.rs:1983 prebuilt_in`；stage2 的 stamp 实测写着
   `prebuilt:<该文件>`）。
4. **实测指纹**（三层一致，可复跑）：
   - stage1 的 stamp = `…:host_lin_solve,host_log,primme`（native 那一支）；
   - 交接件与 web 包里的那份 **sha256 相同**（`1f89fef3fd1e18e1…`）；
   - 用 `wasm-objdump -x` 数 `env.rt_host_lin_solve`：**stage2 那份 = 1 次 import**
     （而单独用 `--no-default-features --features session,inwasm_solve,host_log` 编的对照件 = **0 次**）。
5. 断链点：Node/浏览器宿主**没有**原生稀疏求解器 ⇒ 那个 import 无人可填 ⇒ 实例化即 Trap。

## 已做的修补（2026-10-13，随本工单提交）

`build/113/build-omc-wasm.sh`：stage1 结束后，把那个宿主委派版 blob **移出交接件**
（改名成非 `.wasm` 后缀，免得被 `publish_prebuilt` 按扩展名又捡回去）。
依据是上游自己给的正道（`build.rs:1978-1979` 原文）：
> "Missing from the directory, a blob is built as usual."

⇒ stage2（`target=wasm32`）会**自己重编**这个 blob，走 `session,inwasm_solve,host_log` 那一支。

**★ 修补已实测生效（2026-10-13 深夜）**：清掉 stage2 的陈旧 blob 缓存后重建，
产出**新的运行时 blob**并验到 import 面变干净：

| 检查 | 修补前 | 修补后 |
|---|---|---|
| `blobs/runtime_wasip1_interactive.wasm` sha256 前 16 | `1f89fef3fd1e18e1` | **`df866d92b637ae96`** |
| `wasm-objdump -x` 数 `env.rt_host_lin_solve` **导入** | **1** | **0** |

⇒ "模型模块 import 的那个宿主回调无人提供"这条**断链已断掉**。
**仍未走完**：产物要在 stage2 收尾后重新 `--verify`，再用
`node test/node/accept-omc-simulate.mjs` 验仿真是否真跑完并出 `.mat`（那才是需求 B 的结案判据）。

**踩到的一个坑（记下来）**：光把 blob 从交接件移出**不够** —— stage2 的
`rust-target/.../build/openmodelica_wasm_jit-*/out/` 与 `Compiler/wasm-blobs/` 里
**还留着上一次的拷贝**，`prebuilt_in`/缓存都不看上游目录了，注释里说"missing ⇒ build as usual"
也救不了已经落盘的旧件。⇒ 必须**连 stage2 的旧 blob 一起清**（本次做法：
`rm -rf stage2/.../openmodelica_wasm_jit-*/out` 与 `stage2/.../Compiler/wasm-blobs`）。

## 顺带查清的两件事（存档）

- `omc_set_inwasm_driver(1)` **不够**：它只切"驱动"（谁驱动积分），不换运行时 blobs 的**特征集**；
  且 `RUST_OMC_WASM_INWASM_DRIVER` 这个 cmake option 只 append 到 **native omc 的 codegen**
  分支（`rust_omc.cmake:1278-1281`），对 stage1 的这条链**不起作用**（实测 stamp 未变）。
- `omc_simulate(class, stop, intervals, tol, method, flags)` 是**六参**（不是三参）；
  `omc_sim_start(prefix, result_file, simflags)` + `omc_sim_advance(budget_ms)` 是**分块可取消**
  的等价路径（官方 worker 用后者 + `_res.arrow`）。两者都试过，报同一个 Trap。
