// 需求 B 验收：**页面里**跑通一个 Modelica 模型（端到端）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 判据（`docs/REQUIREMENTS.md` 需求 B）：
//   B1 页面里 `loadFile("BouncingBall.mo")` + `simulate(BouncingBall)` ⇒ 产出 `.mat`；
//   B2 `.mat` 头正确（MAT4）、变量数/采样数与参考一致；
//   B3 反向：语法错的 `.mo` ⇒ `getErrorString()` 给出**可读错误**（不许静默）。
//
// 与需求 A/`accept-omc-getversion`（Node 侧）的分工：那条验的是 **node 档**产物，
//   本条验的是 **web 档**产物 + 真浏览器 + 我们自己的站点（`build/promote-site.sh` 发布）。
// ⚠️ 本条**不是**需求 E（那条用 Node 侧 omc 驱动 Octave）；这里没有 Octave，只有 omc 页面。
//
// 用法：sh test/browser/run-omc-page.sh [URL]
// 退出码：0 = 全过；1 = 有 fail；2 = 环境（站点/harness 不在）
import { chromium } from 'playwright-core';

const URL = process.argv[2] || 'http://127.0.0.1:8765/omc-bridge.html';
let pass = 0, fail = 0;
const ok = (name, cond, detail = '') => {
  if (cond) { pass++; console.log(`PASS | ${name}`); }
  else { fail++; console.log(`fail | ${name}${detail ? ' —— ' + detail : ''}`); }
};

const browser = await chromium.launch({ executablePath: '/usr/bin/chromium',
  args: ['--no-proxy-server', '--no-sandbox', '--disable-dev-shm-usage'] });
const page = await (await browser.newContext()).newPage();
const consoleErrs = [];
page.on('pageerror', e => consoleErrs.push(String(e).slice(0, 200)));
await page.goto(URL, { waitUntil: 'load', timeout: 300000 });

// 等页面探测口就绪（页面把每步写进 __omcBridgeProbe；**探测按需触发 + 带超时**，
// 不放在开机路径上 —— 本仓纪律）
let P = null;
for (let i = 0; i < 900; i++) {
  P = await page.evaluate(() => window.__omcBridgeProbe || null).catch(() => null);
  if (P && P.ready) break;
  await new Promise(r => setTimeout(r, 500));
}
ok('① 页面探测口就绪（omc wasm 装载 + init）', !!(P && P.ready),
   `err=${P && P.error ? P.error.slice(0, 160) : '(none)'} pageerrors=${consoleErrs.join(' | ').slice(0, 160)}`);
if (!P || !P.ready) { await browser.close(); console.log(`\n=== OMC-PAGE ${pass} PASS / ${fail} FAIL ===`); process.exit(1); }

ok('①b 页面里 getVersion() 出串', /rust|OpenModelica/i.test(String(P.version || '')), `version=${JSON.stringify(P.version)}`);

// B1：页面里 loadFile + simulate ⇒ 产出 .mat
ok('②a B1：页面里 loadFile → true（编译器前端在页面内跑通）',
   /^"?true"?$/.test(String(P.steps.find(s => s.startsWith('loadFile=')) || '').replace('loadFile=', '').trim()),
   `steps=${JSON.stringify(P.steps.slice(0, 6))}`);
ok('②b B1：页面里 simulate 产出 resultFile（.mat 在页面 VFS 里）',
   !!P.mat, `error=${String(P.error || '').slice(0, 200)}`);

// B2：.mat 头正确（MAT4）+ 采样数/变量数与参考一致
if (P.mat) {
  // MAT4 首矩阵 = Aclass（类型码 51 + 4×11 + imagf 0；出处：上游 write_mat_header）
  ok('③a B2：.mat 是 MAT4（首矩阵 Aclass、类型码 51、4×11、imagf=0）',
     P.mat.typeCode === 51 && P.mat.mrows === 4 && P.mat.ncols === 11 && P.mat.imagf === 0 && P.mat.firstName === 'Aclass',
     JSON.stringify(P.mat));
  // 变量数/采样数：从**真实字节**里再解析一遍（不信页面自报的数字）
  const parsed = await page.evaluate(() => {
    const b = window.__omcMatBytes;
    if (!b) return null;
    const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
    const out = { mats: [] };
    let p = 0;
    while (p + 20 <= b.length && out.mats.length < 8) {
      const ty = dv.getUint32(p, true), mr = dv.getUint32(p + 4, true), nc = dv.getUint32(p + 8, true);
      const nl = dv.getUint32(p + 16, true);
      const name = new TextDecoder('latin1').decode(b.subarray(p + 20, p + 20 + Math.max(0, nl - 1)));
      const elt = (ty % 10 === 1) ? 1 : ((Math.floor(ty / 10) % 10 === 2) ? 4 : ((Math.floor(ty / 10) % 10 === 1) ? 4 : 8));
      const dlen = mr * nc * elt;
      out.mats.push({ name, mr, nc });
      p += 20 + nl + dlen;
    }
    out.total = b.length;
    return out;
  });
  ok('③b B2：字节解析出 6 个矩阵（Aclass/name/description/dataInfo/data_1/data_2）',
     !!parsed && parsed.mats.length === 6 &&
     ['Aclass', 'name', 'description', 'dataInfo', 'data_1', 'data_2'].every((n, i) => parsed.mats[i].name === n),
     JSON.stringify(parsed && parsed.mats));
  if (parsed) {
    const d2 = parsed.mats[5];
    ok('③c B2：data_2 = 5×628（5 个随时间的量 × 628 采样，与参考一致）',
       d2.mr === 5 && d2.nc === 628, `data_2=${d2.mr}x${d2.nc}`);
    const nm = parsed.mats[1];
    ok('③d B2：name 矩阵 7 列（7 个变量：time/h/v/der(h)/der(v)/e/g）',
       nm.nc === 7, `name=${nm.mr}x${nm.nc}`);
  }
}

// B3：反向 —— 语法错的模型必须给出**可读错误**
const rev = P.reversed;
ok('★④a B3：语法错的 .mo ⇒ loadFile 不为 true', !!rev && !/^"?true"?$/.test(String(rev.load || '')),
   JSON.stringify(rev));
ok('★④b B3：getErrorString() 给出可读错误（非空、含定位信息）',
   !!rev && String(rev.error || '').length > 10 && /error|Error|\[/.test(String(rev.error)),
   `error=${JSON.stringify(String(rev && rev.error).slice(0, 200))}`);

await browser.close();
console.log(`\n=== OMC-PAGE ${pass} PASS / ${fail} FAIL ===`);
process.exit(fail ? 1 : 0);
