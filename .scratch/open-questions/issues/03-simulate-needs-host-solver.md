# 03 · 需求 B：simulate() 在 wasm 里跑不起来（宿主要求 `rt_host_lin_solve` 回调）

**Status:** needs-info
**Settling:** `bash build/113/build-omc-wasm.sh --verify && node test/node/accept-omc-simulate.mjs` —— rc=0 ⇒ A（模型在 Node 里跑完并产出 `.mat`，需求 B 结案）；rc=1 ⇒ B（仍失败，脚本打印卡在哪一层）；rc=2 ⇒ C（产物目录不在，环境问题不是结论）

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

**⚠️ 尚未验证**（关机打断了重建）：这条修补**未实测通过**。验收判据就是本工单的 `Settling:`，
另需补 `test/node/accept-omc-simulate.mjs`（口径：跑完 + 产出 `.mat` + 头 4 字节是 MAT4/魔数）。

## 顺带查清的两件事（存档）

- `omc_set_inwasm_driver(1)` **不够**：它只切"驱动"（谁驱动积分），不换运行时 blobs 的**特征集**；
  且 `RUST_OMC_WASM_INWASM_DRIVER` 这个 cmake option 只 append 到 **native omc 的 codegen**
  分支（`rust_omc.cmake:1278-1281`），对 stage1 的这条链**不起作用**（实测 stamp 未变）。
- `omc_simulate(class, stop, intervals, tol, method, flags)` 是**六参**（不是三参）；
  `omc_sim_start(prefix, result_file, simflags)` + `omc_sim_advance(budget_ms)` 是**分块可取消**
  的等价路径（官方 worker 用后者 + `_res.arrow`）。两者都试过，报同一个 Trap。
