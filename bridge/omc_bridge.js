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
  async function dispatch(cmd, ctx) {
    // 约定：`writeFile`/`readFile` 可以是同步也可以是返回 Promise 的（await 两种都吞）。
    const { omc, writeFile, modelFileOf } = ctx;
    // ① getVersion()
    let m = cmd.match(/^getVersion\(\)\s*$/);
    if (m) {
      const v = omc.omc_eval('getVersion()');
      return { ok: true, payload: String(v) };
    }
    // ② loadFile("<path>")
    m = cmd.match(/^loadFile\("([^"]+)"\)\s*$/);
    if (m) {
      // 模型源码由宿主写进 VFS（浏览器里用户给的 .mo；测试里由夹具给）
      const r = omc.omc_eval(`loadFile("${m[1]}")`);
      const err = String(omc.omc_eval('getErrorString()') || '').trim();
      if (!/^"?true"?$/.test(String(r)) && err) return { ok: false, payload: err };
      return { ok: true, payload: String(r) };
    }
    // ③ simulate(Class, stopTime=<t>)
    m = cmd.match(/^simulate\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s*,\s*stopTime=([0-9.eE+-]+)\s*\)\s*$/);
    if (m) {
      const cls = m[1], stop = Number(m[2]);
      const out = String(omc.omc_simulate(cls, stop, 500, 1e-6, 'dassl', ''));
      const rf = (out.match(/resultFile\s*=\s*"([^"]*)"/) || [])[1] || '';
      if (!rf) return { ok: false, payload: out.slice(0, 400) };
      // 从 VFS 取件（协议照产物 .d.ts：wasi_path_open → fd；wasi_fd_read → Uint8Array）
      const fd = omc.wasi_path_open(rf);
      if (!(typeof fd === 'number' && fd >= 0)) return { ok: false, payload: 'VFS 打不开 ' + rf };
      let bytes;
      try { bytes = omc.wasi_fd_read(fd); } finally { omc.wasi_fd_close(fd); }
      if (!bytes || !bytes.length) return { ok: false, payload: 'VFS 读出 0 字节' };
      // 写进 Octave 能看到的路径（Octave 的 MEMFS；宿主侧 writeFile 由调用方给，
      // ⚠️ 可以是**异步**的 —— Node 侧驱动时它走 page.evaluate，见 accept-omc-bridge.mjs）
      const dest = modelFileOf(cls);
      await writeFile(dest, bytes);
      return { ok: true, payload: 'MAT ' + dest };
    }
    return { ok: false, payload: 'omc_bridge: 不支持的命令（命令驱动，不做 .m→Modelica 翻译）：' + cmd };
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
      try { if (!opts.exists || !(await opts.exists(RES))) await ctx.writeFile(RES, new TextEncoder().encode('')); } catch (e) {}
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
