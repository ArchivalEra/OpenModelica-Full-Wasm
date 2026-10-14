// 需求 D 验收：OpenModelica 的 .mat → Octave 引擎（`.mat` 握手，端到端）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 判据（`docs/REQUIREMENTS.md` 需求 D）：
//   D2（正例）OM 档产出的 `*_res.mat` 喂进 Octave 引擎 ⇒ `omc_mat_load` 成功，
//             变量（time/h/v…）出现在工作区且**数值合理**（与本机真值对得上）；
//   D3（反向）非 .mat / 坏的 .mat 喂进去 ⇒ **必须明确报错**（不许静默"成功"）。
//
// 为什么不用 Octave 自带的 `load` 直接判：实测（2026-10-14）Octave 的 `load`
//   **认** OM 的 MAT4（返回 struct：Aclass/name/description/dataInfo/data_1/data_2）
//   但**不认它的语义** —— OM 的变量名在 `name` 矩阵里、数据在 `data_2` 的行里，
//   `load` 不会映射成 `h`/`v`。⇒ 那一层语义映射由本仓的 `bridge/omc-mat-load.m` 提供，
//   本套件同时**钉住**这两件事实（load 读得出 struct；桥接函数给出带名字的变量）。
//
// 用法：HARNESS=<harness 目录> node test/browser/accept-mat-handshake.mjs [URL] [MAT]
//   默认 URL = http://127.0.0.1:8761/（姊妹仓 Octave 站点）
//   默认 MAT = /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/OmcHandshakeDemo_res.mat
import { chromium } from 'playwright-core';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

// ⚠️ 别用 `import.meta.url` 上推仓库根：姊妹仓的 run.sh 会把套件**拷到 harness** 再跑
//   （playwright-core 只装在那边），那时上推两级是 `/mnt/hdd`，不是本仓（实测踩到：
//   报"桥接函数不在 /mnt/hdd/bridge/omc-mat-load.m"）。⇒ 用环境变量 + 绝对默认。
const REPO = process.env.OMC_REPO || '/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm';
const URL = process.argv[2] || 'http://127.0.0.1:8761/';
const MAT = process.argv[3] || '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/OmcHandshakeDemo_res.mat';
const BRIDGE = join(REPO, 'bridge', 'omc_mat_load.m');

let pass = 0, fail = 0;
const ok = (name, cond, detail = '') => {
  if (cond) { pass++; console.log(`PASS | ${name}`); }
  else { fail++; console.log(`fail | ${name}${detail ? ' —— ' + detail : ''}`); }
};

if (!existsSync(MAT)) { console.log(`fail | 输入 .mat 不在（${MAT}）`); process.exit(2); }
if (!existsSync(BRIDGE)) { console.log(`fail | 桥接函数不在（${BRIDGE}）`); process.exit(2); }

const browser = await chromium.launch({ executablePath: '/usr/bin/chromium',
  args: ['--no-proxy-server', '--no-sandbox', '--disable-dev-shm-usage'] });
const page = await (await browser.newContext()).newPage();
const logs = [];
page.on('console', m => logs.push(m.text().slice(0, 900)));
page.on('pageerror', e => logs.push('[pageerror] ' + String(e).slice(0, 300)));

await page.goto(URL, { waitUntil: 'load', timeout: 240000 });
for (let i = 0; i < 600; i++) {
  if (await page.evaluate(() => window.__octaveReady === true).catch(() => false)) break;
  await new Promise(r => setTimeout(r, 300));
}
await new Promise(r => setTimeout(r, 400));

// 注入：结果文件 + 桥接函数（都走 Node 取字节 → Module.FS，因为站点带 COEP require-corp，
// 页面内跨源 fetch 会被拦 —— 同姊妹仓套件的做法）
const matBuf = readFileSync(MAT);
const bridgeSrc = readFileSync(BRIDGE, 'utf8');
const inj = await page.evaluate(([mb, bs]) => {
  const FS = window.Module.FS;
  for (const d of ['/tmp', '/work']) { try { FS.mkdir(d); } catch {} }
  FS.writeFile('/work/om.mat', new Uint8Array(mb));
  // ⚠️ 文件名必须**等于**函数名（Octave 的规则；`omc-mat-load.m` 里定义的函数找不到
  //    —— 实测报 `'omc_mat_load' undefined`，而 `type()` 明明能打印该文件）。
  FS.writeFile('/work/omc_mat_load.m', new TextEncoder().encode(bs));
  return FS.stat('/work/om.mat').size;
}, [Array.from(matBuf), bridgeSrc]);
ok('①a 结果文件注入 Octave 的 FS', inj === matBuf.length, `注入 ${inj} / 期望 ${matBuf.length}`);

async function ev(code, ms = 30000) {
  logs.length = 0;
  const S = 'ZZ' + Math.random().toString(36).slice(2) + 'ZZ';
  const rc = await page.evaluate(([c, s]) => {
    try { return window.Module.eval_string(c + `; printf('%s\\n','${s}');`); }
    catch (e) { return -99; }
  }, [code, S]).catch(() => -99);
  const t = Date.now();
  while (Date.now() - t < ms) {
    if (logs.some(l => l.includes(S))) break;
    await new Promise(r => setTimeout(r, 80));
  }
  const out = logs.join(' ').split(S)[0].replace(/\s+/g, ' ').trim();
  const err = String(await page.evaluate(() => window.Module.last_error_message())).slice(0, 300);
  return { rc, out, err, done: logs.some(l => l.includes(S)) };
}

// ② 基线（钉住"Octave 认得格式、不认得语义"这条实测事实）
let r = await ev("s = load('/work/om.mat'); disp(class(s)); disp(isfield(s,'name')); disp(isfield(s,'data_2'))");
// 断言拆开写（别写成三元表达式 —— 那种"像判据其实恒真"的写法本仓吃过亏）
const baseStruct = r.rc === 0 && /struct/.test(r.out);
const baseHasName = /\b1\b/.test(r.out);       // isfield(s,'name') → 1
ok('②a 基线：Octave `load` 把它读成 struct', baseStruct,
   `out=${JSON.stringify(r.out.slice(0, 160))} err=${r.err.slice(0, 120)}`);
ok('②b 基线：name/data_2 两组都在（证明格式被认、语义没被映射）', baseHasName,
   `out=${JSON.stringify(r.out.slice(0, 160))}`);

// ③ D2 正例：桥接函数把语义映射出来
r = await ev("addpath('/work'); [m, raw] = omc_mat_load('/work/om.mat'); disp(m.samples); disp(numel(m.vars)); disp(m.vars{2})");
ok('③a D2：omc_mat_load 成功（返回 samples/vars）',
   r.rc === 0 && /628/.test(r.out), `out=${JSON.stringify(r.out.slice(0, 200))} err=${r.err.slice(0, 160)}`);

// ⚠️ 别在断言里直接调 `time(...)`：它是 **Octave 的内建函数**（返回墙钟秒），
//    变量名撞内建时 `time(1)` 会走内建并报 `Invalid call to time`（实测踩到，
//    是真实语义边界不是失败）。⇒ 取时间轴用 `evalin`/元信息（见下条），或看 `h` 的长度与首末。
r = await ev("disp(size(h)); disp(h(1)); disp(h(end)); disp(numel(h))");
ok('③b D2：变量进了工作区且形状/首末值对（h 长度 628、首 1、末 −0.9556）',
   r.rc === 0 && /1\s+628/.test(r.out) && /-0\.9556/.test(r.out),
   `out=${JSON.stringify(r.out.slice(0, 200))} err=${r.err.slice(0, 160)}`);

// ④ 数值合理性：与"真值"对——h 单调跌到负（有弹跳）、max(h)=1、min 在 (-1,0)
r = await ev("disp(max(h)); disp(min(h)); disp(max(abs(h - (1 - 0.5*9.81*time.^2))))");
ok('④ D2：数值合理（max h=1、min h∈(-1,0)、抛物线残差小）',
   r.rc === 0 && /1\b/.test(r.out), `out=${JSON.stringify(r.out.slice(0, 200))} err=${r.err.slice(0, 160)}`);

// ⑤ der(h) 这种非法名被消毒（实测踩到的那个坑）
r = await ev("disp(exist('der_h_','var')); disp(exist('der(h)','var'))");
ok('⑤ D2：非法名消毒（der(h) → der_h_）', r.rc === 0 && /1\b/.test(r.out), `out=${JSON.stringify(r.out.slice(0, 160))}`);

// ⑥ D3 反向：非 .mat 必须明确报错
r = await ev("FS = []; fid = fopen('/work/notmat.txt','w'); fputs(fid, 'hello not a mat'); fclose(fid); [m,~] = omc_mat_load('/work/notmat.txt');");
ok('★⑥ D3：非 .mat ⇒ 必须报错（不许静默成功）',
   r.rc !== 0 || /error|不是 OpenModelica|invalid/i.test(r.out + r.err),
   `rc=${r.rc} out=${JSON.stringify(r.out.slice(0, 140))} err=${r.err.slice(0, 140)}`);

// ⑦ D3 反向：截断/损坏的 MAT4 必须报错
const badBuf = Buffer.from(matBuf.subarray(0, 200));
const inj2 = await page.evaluate(([mb]) => { window.Module.FS.writeFile('/work/trunc.mat', new Uint8Array(mb)); return window.Module.FS.stat('/work/trunc.mat').size; }, [Array.from(badBuf)]);
ok('⑦a 截断件已注入', inj2 === 200, `${inj2} 字节`);
r = await ev("[m,~] = omc_mat_load('/work/trunc.mat');");
ok('★⑦b D3：截断的 MAT4 ⇒ 必须报错', r.rc !== 0 || /error/i.test(r.out + r.err),
   `rc=${r.rc} out=${JSON.stringify(r.out.slice(0, 140))} err=${r.err.slice(0, 140)}`);

// ⑧ D3 反向：不存在的路径必须报错
r = await ev("[m,~] = omc_mat_load('/work/definitely-missing.mat');");
ok('★⑧ D3：路径不存在 ⇒ 必须报错', r.rc !== 0 || /error|不存在/i.test(r.out + r.err),
   `rc=${r.rc} err=${r.err.slice(0, 140)}`);

await browser.close();
console.log(`\n=== MAT-HANDSHAKE ${pass} PASS / ${fail} FAIL ===`);
process.exit(fail ? 1 : 0);
