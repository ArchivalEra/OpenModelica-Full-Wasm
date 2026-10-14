// 需求 E 验收：MATLAB 语义桥 `omc_*`（在**真 Octave 引擎**里跑）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 判据（`docs/REQUIREMENTS.md` 需求 E）：
//   E1 实现命令驱动桥（拼 OM 脚本 → 调 omc → 读回 .mat）；
//   E2 在 Octave 里拿模型仿真结果 ⇒ **返回数据矩阵**；
//   E3 边界：只做命令驱动，未支持的命令/未知模型必须**明确报错**。
//
// ── ★ 架构（四条实测教训定出来的形状，改动前先读）──────────────────────────
//   1. omc 与 Octave 是两个独立 wasm。`.m` 触达宿主只有 MEMFS 文件队列
//      （`__web_fetch_sync__` 那条 sync-XHR 路**已被实测排除**：sync XHR 不被 Service Worker 拦截）。
//   2. **`.m` 侧绝不能忙等**：Octave 的忙等会占住它所在线程，而宿主读写 MEMFS 也要经过
//      同一个上下文 ⇒ **两边互等死锁**。实测：Octave 忙 3s 时宿主的 evaluate 被阻塞 2701ms。
//   3. ⇒ 落成**两段式**：`.m` 只 `omc_submit()`（提交即返回）；宿主把请求转给 omc、把应答写回；
//      **宿主再调** `omc_collect(seq)` 取回。任何时刻只有一边在跑。
//   4. Octave 跑在**站点的 worker 模式**（`?worker=1`）：主线程留给宿主桥；
//      worker 的 `disp` 输出经 postMessage 落到**页面 DOM 的 `#output`**（不是 page console），
//      而 `OctaveWorker.eval` 的返回值**不含求值结果** —— 这是两条独立通道，别混。
//
// ★ 只读姊妹仓：Octave 站点与 harness 只借不动（用户点令）。
//
// 用法：sh test/browser/run-omc-bridge.sh [URL]
// 退出码：0 = 全过；1 = 有 fail；2 = 环境（产物/harness 不在）
import { chromium } from 'playwright-core';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';

const OCT_BASE = (process.argv[2] || 'http://127.0.0.1:8761/').replace(/\/?$/, '/');
const OCT_URL = OCT_BASE + '?worker=1';     // ★ 见架构第 4 条
const REPO = process.env.OMC_REPO || '/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm';
const OM_WEB = process.env.OM_WEB || '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web';
const BRIDGE = join(REPO, 'bridge');
const require_ = createRequire(import.meta.url);

let pass = 0, fail = 0;
const ok = (name, cond, detail = '') => {
  if (cond) { pass++; console.log(`PASS | ${name}`); }
  else { fail++; console.log(`fail | ${name}${detail ? ' —— ' + detail : ''}`); }
};

const FNS = ['omc_submit', 'omc_collect', 'omc_getVersion', 'omc_simulate_async',
             'omc_mat_load', 'omc_fs_read', 'omc_fs_write', 'omc_simulate_model'];
for (const [what, p] of [
  ['OM 产物（node 档 web 包）', join(OM_WEB, 'omc-cli.js')],
  ...FNS.map((f) => [`桥接函数 ${f}`, join(BRIDGE, f + '.m')]),
]) if (!existsSync(p)) { console.log(`fail | 缺${what}（${p}）`); process.exit(2); }

// ── Node 侧 omc 实例（真 wasm）──────────────────────────────────────────────
const omc = require_(join(OM_WEB, 'pkg-nodejs', 'OpenModelicaCompiler.js'));
omc.omc_set_env('OPENMODELICAHOME', '/usr');
const inited = omc.omc_init();
omc.omc_set_inwasm_driver(1);

// ── 浏览器（Octave 在 worker 里）────────────────────────────────────────────
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium',
  args: ['--no-proxy-server', '--no-sandbox', '--disable-dev-shm-usage'] });
const page = await (await browser.newContext()).newPage();
await page.goto(OCT_URL, { waitUntil: 'load', timeout: 240000 });
for (let i = 0; i < 900; i++) {
  if (await page.evaluate(() => window.__octaveReady === true).catch(() => false)) break;
  await new Promise(r => setTimeout(r, 300));
}
await new Promise(r => setTimeout(r, 400));
ok('①a Octave 引擎就绪（worker 模式）', await page.evaluate(() => window.__octaveReady === true));
ok('①b omc 模块（Node 侧）init', !!inited);

// ── Octave 侧：eval + DOM 输出通道 ─────────────────────────────────────────
const DOM_OUT = async () => page.evaluate(() => (document.querySelector('#output') || {}).textContent || '');
async function evO(code, ms = 60000, want = null) {
  const before = (await DOM_OUT()).length;
  const r = await page.evaluate(async (c) => {
    try { return await window.OctaveWorker.eval(c); }
    catch (e) { return { rc: -99, err: String(e).slice(0, 200) }; }
  }, code);
  const t = Date.now();
  let tail = '';
  while (Date.now() - t < ms) {
    tail = (await DOM_OUT()).slice(before);
    if (want && want.test(tail)) break;
    if (!want && Date.now() - t > 1500) break;
    await new Promise(x => setTimeout(x, 40));
  }
  return { rc: (r && r.rc), err: (r && r.err) || '', tail };
}
// ★ base64 分块解码（协议见 bridge/omc_fs_read.m 的头注：三个坑定的形状）
const fsRead = async (p) => {
  const r = await evO(`addpath('/bridge'); omc_fs_read('${p}')`, 25000, /__OMCFS_(END|MISSING)__/);
  if (!/__OMCFS_BEGIN__/.test(r.tail)) return '';
  const parts = [...r.tail.matchAll(/__OMCFS_L ([A-Za-z0-9+/=]+)/g)].map((m) => m[1]).join('');
  if (!parts) return '';
  try { return Buffer.from(parts, 'base64').toString('utf8'); } catch { return ''; }
};
const fsWrite = async (p, b) => {
  const arr = Array.from(b instanceof Uint8Array ? b : new TextEncoder().encode(b));
  const r = await evO(`addpath('/bridge'); omc_fs_write('${p}', [${arr.join(',')}])`, 40000, /__OMCFS_WROTE__|__OMCFS_FAIL__/);
  return /__OMCFS_WROTE__/.test(r.tail);
};

// ── 注入（逐行 fprintf；不依赖任何已存在的助手）──────────────────────────────
async function injectFile(path, text) {
  const lines = text.split('\n');
  let code = `mkdir('/bridge'); mkdir('/tmp');\nf=fopen('${path}','w');\n`;
  for (const ln of lines) code += `fprintf(f, '%s\\n', '${ln.replace(/'/g, "''")}');\n`;
  code += `fclose(f); d=dir('${path}'); disp(sprintf('__INJ__ %d', numel(d)>0 && d.bytes>0));`;
  const r = await evO(code, 40000, /__INJ__/);
  return /__INJ__ 1/.test(r.tail);
}
let injected = 0;
for (const f of FNS) if (await injectFile(`/bridge/${f}.m`, readFileSync(join(BRIDGE, f + '.m'), 'utf8'))) injected++;
const MODEL = `model BouncingBall
  parameter Real e=0.7 "coefficient of restitution";
  parameter Real g=9.81 "gravity acceleration";
  Real h(fixed=true, start=1) "height of ball";
  Real v(fixed=true) "velocity of ball";
equation
  der(v) = -g;
  der(h) = v;
  when h <= 0 then
    reinit(v, -e*pre(v));
  end when;
end BouncingBall;
`;
const modelOk = await injectFile('/tmp/BouncingBall.mo', MODEL);
ok('② 桥接函数 + 模型注入 Octave MEMFS', injected === FNS.length && modelOk,
   `${injected}/${FNS.length} 函数，模型=${modelOk}`);

// ── 宿主桥（两段式的"宿主"）：读请求 → 转 omc → 写应答 ──────────────────────
async function serveOnce() {
  const req = await fsRead('/tmp/omc_req.txt');
  if (!req || !req.trim()) return 0;
  await fsWrite('/tmp/omc_req.txt', '');           // drain
  let res = await fsRead('/tmp/omc_res.txt');
  let n = 0;
  for (const ln of req.split('\n').filter((l) => l.trim())) {
    const i = ln.indexOf('\t');
    if (i < 0) continue;
    const seq = ln.slice(0, i), cmd = ln.slice(i + 1);
    let out;
    try {
      const r = await omc.dispatchCommand(cmd);
      out = r;
    } catch (e) { out = { ok: false, payload: 'bridge: ' + String(e).slice(0, 200) }; }
    res += `${seq}\t${out.ok ? 'ok' : 'err'}\t${omcEsc(out.payload || '')}\n`;
    n++;
  }
  await fsWrite('/tmp/omc_res.txt', res);
  return n;
}
// omc 命令分发（与 bridge/omc_bridge.js 的 dispatch 同义；这里是套件内的宿主实现）
omc.dispatchCommand = async function (cmd) {
  let m = cmd.match(/^getVersion\(\)\s*$/);
  if (m) return { ok: true, payload: String(omc.omc_eval('getVersion()')) };
  // ★ 三条真语义（都实测过，别简化）：
  //  ① `cd`：omc 的**仿真输出目录跟着 cwd 走**（没有它 resultFile 为空 —— 实测）。
  //  ② `loadFile`：路径是 **Octave 侧**的，而 omc 是**另一个 wasm** ⇒ 它的 VFS 里没有
  //     那个文件（实测 wasi_path_open → -1）。桥必须**搬运字节**：从 Octave MEMFS 读出来、
  //     写进 omc VFS，再 loadFile。
  //  ③ `simulate`：结果 .mat 在 **omc 的 VFS** 里 ⇒ 读出来写回 **Octave 的 MEMFS**，
  //     并把落地路径以 `MAT <path>` 告诉 Octave 侧（它再用 omc_mat_load 解析）。
  m = cmd.match(/^cd\("([^"]+)"\)\s*$/);
  if (m) return { ok: true, payload: String(omc.omc_eval(`cd("${m[1]}")`)) };
  m = cmd.match(/^loadFile\("([^"]+)"\)\s*$/);
  if (m) {
    const src = await fsRead(m[1]);
    if (!src || !src.length) return { ok: false, payload: 'Octave 侧读不到 ' + m[1] };
    omc.wasi_write_file(m[1], new TextEncoder().encode(src));
    const r = omc.omc_eval(`loadFile("${m[1]}")`);
    const err = String(omc.omc_eval('getErrorString()') || '').trim();
    if (!/^"?true"?$/.test(String(r).trim()) && err) return { ok: false, payload: err };
    return { ok: true, payload: String(r) };
  }
  m = cmd.match(/^simulate\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s*,\s*stopTime=([0-9.eE+-]+)\s*\)\s*$/);
  if (m) {
    omc.omc_eval('cd("/tmp")');      // 见 ①：钉死输出目录
    const out = String(omc.omc_simulate(m[1], Number(m[2]), 500, 1e-6, 'dassl', ''));
    const rf = (out.match(/resultFile\s*=\s*"([^"]*)"/) || [])[1] || '';
    if (!rf) return { ok: false, payload: out.slice(0, 400) };
    const fd = omc.wasi_path_open(rf);
    if (!(typeof fd === 'number' && fd >= 0)) return { ok: false, payload: 'VFS 打不开 ' + rf };
    let bytes; try { bytes = omc.wasi_fd_read(fd); } finally { omc.wasi_fd_close(fd); }
    if (!bytes || !bytes.length) return { ok: false, payload: 'VFS 读出 0 字节' };
    const dest = `/tmp/${m[1]}_res.mat`;
    if (!(await fsWrite(dest, bytes))) return { ok: false, payload: '写结果文件失败 ' + dest };
    return { ok: true, payload: 'MAT ' + dest };
  }
  // ★ `simulateModel(Class, stopTime=<t>)`：需求 E2 判据原文的一步到位形式
  //   （合成"找模型源 + loadFile + simulate + 取结果"四件事；模型源按约定路径找）
  m = cmd.match(/^simulateModel\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s*,\s*stopTime=([0-9.eE+-]+)\s*\)\s*$/);
  if (m) {
    const cls = m[1], stop = Number(m[2]);
    let src = '';
    for (const cand of [`/tmp/${cls}.mo`, `/${cls}.mo`]) {
      src = await fsRead(cand);
      if (src && src.length) {
        omc.wasi_write_file(`/tmp/${cls}.mo`, new TextEncoder().encode(src));
        const lf = omc.omc_eval(`loadFile("/tmp/${cls}.mo")`);
        if (!/^"?true"?$/.test(String(lf).trim())) {
          return { ok: false, payload: 'loadFile 失败：' + String(omc.omc_eval('getErrorString()')).slice(0, 200) };
        }
        break;
      }
    }
    if (!src || !src.length) return { ok: false, payload: `找不到模型源（试过 /tmp/${cls}.mo）` };
    omc.omc_eval('cd("/tmp")');
    const out = String(omc.omc_simulate(cls, stop, 500, 1e-6, 'dassl', ''));
    const rf = (out.match(/resultFile\s*=\s*"([^"]*)"/) || [])[1] || '';
    if (!rf) return { ok: false, payload: out.slice(0, 300) };
    const fd = omc.wasi_path_open(rf);
    if (!(typeof fd === 'number' && fd >= 0)) return { ok: false, payload: 'VFS 打不开 ' + rf };
    let bytes; try { bytes = omc.wasi_fd_read(fd); } finally { omc.wasi_fd_close(fd); }
    if (!bytes || !bytes.length) return { ok: false, payload: 'VFS 读出 0 字节' };
    const dest = `/tmp/${cls}_res.mat`;
    if (!(await fsWrite(dest, bytes))) return { ok: false, payload: '写结果文件失败 ' + dest };
    return { ok: true, payload: 'MAT ' + dest };
  }
  return { ok: false, payload: '未支持的命令（命令驱动；不做 .m→Modelica 翻译）：' + cmd };
};
function omcEsc(s) { return String(s).replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/\t/g, '\\t'); }

// ★ 两段式驱动：Octave 提交 → 宿主服务一次 → Octave 取回
async function callViaBridge(codeSubmit, codeCollect, tries = 60) {
  const r1 = await evO(`addpath('/bridge'); ${codeSubmit}`, 30000, /__SEQ__/);
  const m = r1.tail.match(/__SEQ__ (\d+)/);
  if (!m) return { ok: false, err: '没拿到 seq：' + r1.tail.slice(-200) };
  const seq = m[1];
  let served = 0;
  for (let i = 0; i < tries; i++) {
    served += await serveOnce();
    const r2 = await evO(`addpath('/bridge'); r = omc_collect(${seq}); disp(sprintf('__COL__ %d %d', r.pending, r.ok)); if (!r.pending), if (r.ok), disp(['__TXT__ ' r.text]); else, disp(['__ERR__ ' r.err]); end, end`, 20000, /__COL__/);
    if (/__COL__ 0 1/.test(r2.tail)) {
      const t = r2.tail.match(/__TXT__ (.*)/);
      return { ok: true, text: t ? t[1].trim() : '', served };
    }
    if (/__COL__ 0 0/.test(r2.tail)) {
      const e = r2.tail.match(/__ERR__ (.*)/);
      return { ok: false, err: e ? e[1].trim() : '(无错误文本)', served };
    }
    await new Promise(r => setTimeout(r, 200));
  }
  return { ok: false, err: '取回应答超时', served };
}

// ── E1：omc_getVersion ────────────────────────────────────────────────────
let r = await callViaBridge(
  `v = omc_getVersion(); disp(['__SEQ__ ' num2str(v.seq)])`,
  null);
// omc_getVersion 内部用 omc_submit；但为了让宿主拿到 seq，这条走显式两步
r = await callViaBridge(`seq = omc_submit('getVersion()'); disp(sprintf('__SEQ__ %d', seq))`, null);
ok('③a E1：getVersion 经两段式桥拿到应答', r.ok && /rust/i.test(r.text || ''),
   `text=${JSON.stringify(String(r.text).slice(0, 120))} err=${String(r.err).slice(0, 140)}`);

// ── E2：仿真 ⇒ 数据矩阵 ───────────────────────────────────────────────────
async function simTwoPhase(cls, stopTime, moPath) {
  // ① loadFile
  let r1 = await callViaBridge(`seq = omc_submit('loadFile("${moPath}")'); disp(sprintf('__SEQ__ %d', seq))`);
  if (!r1.ok) return { ok: false, step: 'loadFile', err: r1.err };
  // ② simulate
  let r2 = await callViaBridge(`seq = omc_submit('simulate(${cls}, stopTime=${stopTime})'); disp(sprintf('__SEQ__ %d', seq))`, null, 120);
  if (!r2.ok) return { ok: false, step: 'simulate', err: r2.err };
  const mm = String(r2.text).match(/MAT\s+(\S+)/);
  if (!mm) return { ok: false, step: 'result', err: '应答里没有 MAT 路径：' + r2.text };
  return { ok: true, mat: mm[1] };
}
const sim = await simTwoPhase('BouncingBall', 3.0, '/tmp/BouncingBall.mo');
ok('④a E2：两段式仿真跑完并拿到 MAT 路径', sim.ok === true, `${sim.step || ''} ${String(sim.err || '')}`);
if (!sim.ok) console.log('      DEBUG sim =', JSON.stringify(sim).slice(0, 1500));
if (sim.ok) {
  // ③ 用 omc_mat_load 解析成矩阵
  const rd = await evO(`addpath('/bridge'); [m,~] = omc_mat_load('${sim.mat}'); disp(sprintf('__M__ %d %d', m.samples, numel(m.vars)))`, 40000, /__M__/);
  const mm = rd.tail.match(/__M__ (\d+) (\d+)/);
  ok('④b E2：结果解析成矩阵（628 采样 / 7 变量）',
     !!mm && mm[1] === '628' && mm[2] === '7', `tail=${JSON.stringify(rd.tail.slice(-160))}`);
  if (mm) {
    const stats = await evO(`addpath('/bridge'); i=find(strcmp(m.vars,'h')); hv=evalin('base','h'); disp(sprintf('__S__ %.4f %.4f %.4f', max(hv), min(hv), hv(end)))`, 30000, /__S__/);
    const sm = stats.tail.match(/__S__ (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)/);
    ok('④c E2：数值对（max h=1.0000、min<0、末 −0.9556）',
       !!sm && sm[1] === '1.0000' && Number(sm[2]) < 0 && Math.abs(Number(sm[3]) + 0.9556) < 1e-3,
       `stats=${JSON.stringify(sm && sm.slice(1))}`);
  }
}

// ── E2 原文形态：`omc_simulate_model('BouncingBall')` 一步到位 ⇒ 数据矩阵 ─────
let one = await callViaBridge(`[seq, cls] = omc_simulate_model('BouncingBall', 'stopTime', 3.0); disp(sprintf('__SEQ__ %d', seq))`, null, 120);
ok('④d E2（原文形态）：omc_simulate_model 一步到位拿到 MAT',
   one.ok === true && /MAT\s+\S+/.test(String(one.text || '')),
   `text=${JSON.stringify(String(one.text).slice(0, 120))} err=${String(one.err).slice(0, 160)}`);
if (one.ok) {
  const mm2 = String(one.text).match(/MAT\s+(\S+)/);
  const rd2 = await evO(`addpath('/bridge'); [m2,~] = omc_mat_load('${mm2[1]}'); disp(sprintf('__M2__ %d %d', m2.samples, numel(m2.vars)))`, 40000, /__M2__/);
  const g = rd2.tail.match(/__M2__ (\d+) (\d+)/);
  ok('④e E2（原文形态）：解析成 628×7 数据矩阵', !!g && g[1] === '628' && g[2] === '7',
     `tail=${JSON.stringify(rd2.tail.slice(-140))}`);
}

// ── E3：反向（未知模型 / 未支持命令必须明确报错）──────────────────────────
let bad = await callViaBridge(`seq = omc_submit('simulate(NoSuchModelXYZ, stopTime=1.0)'); disp(sprintf('__SEQ__ %d', seq))`);
ok('★⑤a E3：未知模型 ⇒ 桥回 err（不许静默）', bad.ok === false && /NoSuchModel|not found|Error/i.test(String(bad.err)),
   `err=${String(bad.err).slice(0, 180)}`);
let uns = await callViaBridge(`seq = omc_submit('translateToPythonPlease(x)'); disp(sprintf('__SEQ__ %d', seq))`);
ok('★⑤b E3：未支持命令 ⇒ 桥明确拒绝（命令驱动边界）', uns.ok === false && /未支持/.test(String(uns.err)),
   `err=${String(uns.err).slice(0, 180)}`);

await browser.close();
console.log(`\n=== OMC-BRIDGE ${pass} PASS / ${fail} FAIL ===`);
process.exit(fail ? 1 : 0);
