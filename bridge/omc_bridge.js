// OpenModelica-Full-Wasm — MATLAB 语义桥的**宿主侧**（需求 E 的另一半）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 职责：把 Octave 侧 `bridge/omc_call__.m` 写进 MEMFS 的**请求行**，转成对 omc(motor)
// 的调用，再把应答写回 MEMFS。omc 恒跑在**浏览器内**（纯客户端铁律），这里只是搬运。
//
// ── 为什么是"轮询文件"而不是"同步调用"（实测决定，别改回去）──────────────────
//  · Octave 的 `.m` 是**同步**的，它触达宿主只有两族通道（`bridge/queue.js` 注释逐字记）：
//    MEMFS 文件队列、`__web_fetch_sync__`（sync XHR）；
//  · 实测：**sync XHR 不被 Service Worker 拦截**（我起了 SW 专门试：async fetch 被应答、
//    sync XHR 落回真实 404/挂住）⇒ 不能靠"宿主现算 + sync XHR 取"那条路；
//  · ⇒ 走文件队列：请求一行、应答一行（与 sibling 的 `ufp`/`webnet` 同族形状）。
//  · `pause(0.05)` 轮询的代价记在这：一次调用 ~50ms 粒度（教学规模够用，如实记）。
//
// 协议（两侧同名常量；改一处必须改另一处）：
//   请求  /tmp/omc_req.txt   追加一行：`<seq>\t<command>`
//   应答  /tmp/omc_res.txt   追加一行：`<seq>\t<ok|err>\t<escaped payload>`
//   escape：payload 里的 `\` `\n` `\t` 分别写成 `\\` `\n` `\t`（单行承载多行文本）
//
// 用法（宿主侧）：
//   const omc = require('.../pkg-nodejs/OpenModelicaCompiler.js');  // node 档
//   或 浏览器 web 档的 `omc/OpenModelicaCompiler.js`
//   await OmcBridge.serve({ omc, fs: () => window.Module.FS, intervalMs: 50 });
//   OmcBridge.stop();
//
// 支持的命令（**命令驱动**，需求 E3 的边界：不做 .m → Modelica 翻译）：
//   getVersion()                      → `"<版本串>"`
//   loadFile("<path>")                → true/false
//   simulate(Class, stopTime=<t>)     → `MAT <vfs结果路径>`（宿主把 .mat 取回并写进 MEMFS）
;(function () {
  'use strict';
  const REQ = '/tmp/omc_req.txt';
  const RES = '/tmp/omc_res.txt';

  function esc(s) {
    return String(s).replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/\t/g, '\\t');
  }
  function unesc(s) {
    return String(s).replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\\\/g, '\\');
  }

  // 解析一行请求：`<seq>\t<command>`。命令里可能含制表符 ⇒ 只切第一个。
  function parseReq(line) {
    const i = line.indexOf('\t');
    if (i < 0) return null;
    const seq = Number(line.slice(0, i));
    if (!Number.isFinite(seq)) return null;
    return { seq, command: line.slice(i + 1) };
  }

  // 命令分发（纯函数式：给 omc 模块 + FS 读写器 ⇒ 返回 {ok, payload}）
  //
  // ★★ 三条承重语义（全部实测过；宿主 Octave-Full-Wasm mail/024 §2 点名要求
  //    把它们放进**交付模块**而不是只留在测试里 —— 下面 ①②③ 就是那三条）：
  //   ① cd：omc 的**仿真输出目录跟着 cwd 走**。不先 cd 到一个确定目录，
  //      `resultFile` 会为空（实测）。
  //   ② loadFile 必须**搬字节**：路径是 Octave 侧的，而 omc 是**另一个 wasm**，
  //      它的 VFS 里没有那个文件（实测 wasi_path_open → -1）⇒ 从 Octave MEMFS 读出来、
  //      写进 omc VFS，再 loadFile。
  //   ③ simulate 结果要**回搬**：结果 .mat 在 omc 的 VFS 里 ⇒ 读出来写回 Octave MEMFS，
  //      并以 `MAT <path>` 告诉 Octave 侧（它再用 omc_mat_load 解析）。
  // ── 承重语义的实现（被上面的路由表调用；每条一个函数，名字即语义）────────────
  // ② loadFile 必须**搬字节**：Octave 侧的路径在 omc 的 VFS 里不存在（实测
  //    wasi_path_open → -1）⇒ 从 Octave MEMFS 读出、写进 omc VFS，再 loadFile。
  async function _evalLoadFile(omc, writeFile, readFile, path) {
    const src = readFile ? await readFile(path) : null;
    if (!src || !src.length) return { ok: false, payload: 'Octave 侧读不到 ' + path };
    omc.wasi_write_file(path, new TextEncoder().encode(src));
    return _evalOmcTrue(omc, `loadFile("${path}")`);
  }

  // omc 的 eval 返回 "true"/true/带引号 —— 只有**明确真**才算成功（不许"没报错就当成功"）。
  function _evalOmcTrue(omc, expr) {
    const r = String(omc.omc_eval(expr) || '').trim();
    const err = String(omc.omc_eval('getErrorString()') || '').trim();
    if (!/^"?true"?$/.test(r)) return { ok: false, payload: err || r };
    return { ok: true, payload: r };
  }

  // ③ simulate 结果要**回搬**：.mat 在 omc 的 VFS 里 ⇒ 读出写回 Octave MEMFS，
  //    并以 `MAT <path>` 告诉 Octave 侧（它再用 omc_mat_load 解析）。
  async function _simulateAndFetch(omc, writeFile, cls, stop, dest) {
    const out = String(omc.omc_simulate(cls, stop, 500, 1e-6, 'dassl', ''));
    // RegExp.exec 而非 String#match（GitRoll #72）：只要捕获组，exec 语义更直接。
    const rfMatch = /resultFile\s*=\s*"([^"]*)"/.exec(out);
    const rf = rfMatch ? rfMatch[1] : '';
    if (!rf) return { ok: false, payload: out.slice(0, 400) };
    // 协议照产物 .d.ts：wasi_path_open → fd；wasi_fd_read → Uint8Array
    const fd = omc.wasi_path_open(rf);
    if (!(typeof fd === 'number' && fd >= 0)) return { ok: false, payload: 'VFS 打不开 ' + rf };
    let bytes;
    try { bytes = omc.wasi_fd_read(fd); } finally { omc.wasi_fd_close(fd); }
    if (!bytes || !bytes.length) return { ok: false, payload: 'VFS 读出 0 字节' };
    await writeFile(dest, bytes);
    return { ok: true, payload: 'MAT ' + dest };
  }

  // ── 命令表：**每条命令 = 一个 matcher + 一个 handler**。加命令只加一行 ─────────
  // 为什么用表而不是 if 链：原来 5 个分支挤在一个函数里（认知复杂度 41），
  // 加一条命令就得通读全文确认没有交叉。表把"匹配什么"与"做什么"分开。
  const CLASS_RE = '[A-Za-z_][A-Za-z0-9_.]*';
  const STOP_RE = '[0-9.eE+-]+';
  const COMMANDS = [
    {
      re: /^getVersion\(\)\s*$/,
      run: ({ omc }) => ({ ok: true, payload: String(omc.omc_eval('getVersion()')) }),
    },
    {
      // ① cd：omc 的**仿真输出目录跟着 cwd 走**。不先 cd 到确定目录，`resultFile` 会为空。
      re: /^cd\("([^"]+)"\)\s*$/,
      run: ({ omc }, m) => ({ ok: true, payload: String(omc.omc_eval(`cd("${m[1]}")`)) }),
    },
    {
      re: /^loadFile\("([^"]+)"\)\s*$/,
      run: (ctx, m) => _evalLoadFile(ctx.omc, ctx.writeFile, ctx.readFile, m[1]),
    },
    {
      re: new RegExp(`^simulate\\(\\s*(${CLASS_RE})\\s*,\\s*stopTime=(${STOP_RE})\\s*\\)\\s*$`),
      run: (ctx, m) => _simulateAndFetch(ctx.omc, ctx.writeFile, m[1], Number(m[2]),
                                      ctx.modelFileOf(m[1])),
    },
    {
      re: new RegExp(`^simulateModel\\(\\s*(${CLASS_RE})\\s*,\\s*stopTime=(${STOP_RE})\\s*\\)\\s*$`),
      run: (ctx, m) => _simulateModel(ctx, m[1], Number(m[2])),
    },
  ];

  // ④ simulateModel：合成"找模型源 + 搬进去 + loadFile + simulate + 取结果"。
  async function _simulateModel(ctx, cls, stop) {
    const src = await _findModelSource(ctx.readFile, cls);
    if (!src) return { ok: false, payload: `找不到模型源（试过 /tmp/${cls}.mo）` };
    ctx.omc.wasi_write_file(`/tmp/${cls}.mo`, new TextEncoder().encode(src));
    const lf = _evalOmcTrue(ctx.omc, `loadFile("/tmp/${cls}.mo")`);
    if (!lf.ok) return { ok: false, payload: 'loadFile 失败：' + String(lf.payload).slice(0, 200) };
    return _simulateAndFetch(ctx.omc, ctx.writeFile, cls, stop, `/tmp/${cls}_res.mat`);
  }

  // 模型源按约定路径找：先 /tmp，再站根。找不到回 ''（调用方据此报"找不到"）。
  async function _findModelSource(readFile, cls) {
    if (!readFile) return '';
    for (const cand of [`/tmp/${cls}.mo`, `/${cls}.mo`]) {
      const src = await readFile(cand);
      if (src && src.length) return src;
    }
    return '';
  }

  async function dispatch(cmd, ctx) {
    // 约定：`writeFile`/`readFile` 可以是同步也可以是返回 Promise 的（await 两种都吞）。
    const c = String(cmd);
    for (const { re, run } of COMMANDS) {
      const m = c.match(re);
      if (m) return run(ctx, m);
    }
    return {
      ok: false,
      payload: 'omc_bridge: 不支持的命令（命令驱动，不做 .m→Modelica 翻译）：' + c,
    };
  }

  const OmcBridge = {
    REQ, RES, esc, unesc, parseReq, dispatch,
    _timer: null,
    // serve：开始轮询请求队列（幂等；重复调用只换配置）
    async serve(opts) {
      const ctx = {
        omc: opts.omc,
        writeFile: opts.writeFile,
        readFile: opts.readFile,
        modelFileOf: opts.modelFileOf || ((cls) => `/tmp/${cls}_res.mat`),
      };
      if (!ctx.omc || !ctx.writeFile) throw new Error('OmcBridge.serve: 需要 omc 与 writeFile');
      this.stop();
      const interval = Math.max(10, opts.intervalMs || 50);
      // 应答文件：确保存在（否则 .m 侧每次都要判 exist 分支）
      // ⚠️ 这里**故意吞异常**（GitRoll #67 问"handle or don't catch"）：`exists` 探针与
      //   首次 writeFile 都可能因宿主 FS 已有该路径而抛，而那正是"已存在"这个**想要的**
      //   结果。真正的失败会在下面的轮询里表现为"请求永不应答"，由调用方超时明说 ——
      //   不在这里编一个假的成功。
      try {
        if (!opts.exists || !(await opts.exists(RES))) {
          await ctx.writeFile(RES, new TextEncoder().encode(''));
        }
      } catch (e) {
        /* 已存在 ⇒ 目标状态已达成，不是错误（理由见上） */
      }
      let busy = false;
      this._timer = setInterval(async () => {
        if (busy) return;
        busy = true;
        try {
          let txt = '';
          try { txt = (await ctx.readFile(REQ)) || ''; } catch (e) { txt = ''; }
          if (txt && txt.length) {
            // 读走并清空（同族协议：drain）
            await ctx.writeFile(REQ, new TextEncoder().encode(''));
            const lines = txt.split('\n').filter((l) => l.length);
            let outLines = '';
            try { outLines = (await ctx.readFile(RES)) || ''; } catch (e) { outLines = ''; }
            for (const ln of lines) {
              const q = this.parseReq(ln);
              if (!q) continue;
              let res;
              try { res = await dispatch(q.command, ctx); }
              catch (e) { res = { ok: false, payload: 'bridge 异常：' + String(e).slice(0, 300) }; }
              outLines += `${q.seq}\t${res.ok ? 'ok' : 'err'}\t${esc(res.payload || '')}\n`;
            }
            await ctx.writeFile(RES, new TextEncoder().encode(outLines));
          }
        } finally { busy = false; }
      }, interval);
      return this;
    },
    stop() { if (this._timer) { clearInterval(this._timer); this._timer = null; } },
  };

  if (typeof window !== 'undefined') window.OmcBridge = OmcBridge;
  if (typeof globalThis !== 'undefined') globalThis.OmcBridge = OmcBridge;
  if (typeof module !== 'undefined' && module.exports) module.exports = OmcBridge;
})();
