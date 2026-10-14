// 同页集成验收：**两个 wasm 引擎在同一个页面里**（wasm32；用户点令的第一步）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 判据：
//   ① 同页：Octave 解释器可用 **且** omc 模块可 eval（两个引擎都真跑，不是只编译）；
//   ② 页内握手：omc 产 `.mat` → Octave 读——**不经过 Node、不经过任何服务端**；
//      Octave 侧读出的变量/采样数与 omc 侧产出**互相对上**（需求 D 的通道在页内闭环）；
//   ③ 反向：坏件喂进 Octave ⇒ 必须明确报错；
//   ④ 内存/体积实测（同页成本**实测值**，不是估算）。
//
// ★ 我早先的 R6 结论（"同页当前不可行"）已被**翻案**：那是**测量方法的错**
//   （探针把 91MB 模块 base64 成 ~122MB 的 JS 字符串 + 巨型数组 ⇒ 假崩）。
//   正解：`WebAssembly.compileStreaming`（引擎直接消化响应体）。
//   本套件因此**同时钉住**这条：两个大模块在同页都能编译（耗时+堆用量记账）。
//
// 用法：sh test/browser/run-samepage.sh [URL]
// 退出码：0 = 全过；1 = 有 fail；2 = 环境（站点/harness 不在）
import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync, statSync } from 'node:fs';
import { dirname } from 'node:path';

const URL = process.argv[2] || 'http://127.0.0.1:8765/samepage.html';
let pass = 0, fail = 0;
const ok = (name, cond, detail = '') => {
  if (cond) { pass++; console.log(`PASS | ${name}`); }
  else { fail++; console.log(`fail | ${name}${detail ? ' —— ' + detail : ''}`); }
};

const browser = await chromium.launch({ executablePath: '/usr/bin/chromium',
  args: ['--no-proxy-server', '--no-sandbox', '--disable-dev-shm-usage'] });
const page = await (await browser.newContext()).newPage();
const errs = [];
page.on('pageerror', e => errs.push(String(e).slice(0, 200)));
await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 300000 });

// ① 同页编译（钉住"翻案"那条：两个大模块都能编译）
const compileProbe = await page.evaluate(async () => {
  const out = [];
  for (const [n, u] of [['octave', './oct/octave.wasm'], ['omc', './omc/OpenModelicaCompiler_bg.wasm']]) {
    const t0 = performance.now();
    try {
      const m = await WebAssembly.compileStreaming(fetch(u));
      out.push({ name: n, ok: true, exports: WebAssembly.Module.exports(m).length, ms: Math.round(performance.now() - t0) });
    } catch (e) { out.push({ name: n, ok: false, err: String(e).slice(0, 140) }); }
  }
  return out;
});
ok('①a 同页：Octave 模块编译（29.6MB，流式）', compileProbe[0].ok, JSON.stringify(compileProbe[0]));
ok('①b 同页：omc 模块编译（91.4MB，流式）', compileProbe[1].ok, JSON.stringify(compileProbe[1]));
const bothMs = compileProbe.filter(x => x.ok).reduce((a, b) => a + b.ms, 0);
console.log(`     编译耗时：octave ${compileProbe[0].ms}ms + omc ${compileProbe[1].ms}ms = ${bothMs}ms`);

// ② 等页面跑完（探测口）
let P = null;
for (let i = 0; i < 1200; i++) {
  P = await page.evaluate(() => window.__samepage || null).catch(() => null);
  if (P && P.ready) break;
  await new Promise(r => setTimeout(r, 500));
}
ok('② 两引擎同页都跑起来了（Octave 解释器 + omc eval）',
   !!(P && P.ready && P.oct && P.oct.ready && P.omc && P.omc.ready && !P.error),
   `err=${String(P && P.error || '').slice(0, 220)} pageerr=${errs.join(' | ').slice(0, 160)}`);

// ③ 页内握手（需求 D 的通道在页内闭环）
const H = P && P.handoff;
ok('③a 页内握手：omc 的 .mat 进了 Octave 且读出变量',
   !!(H && H.matBytes > 1000 && /h/.test(String(H.vars))),
   JSON.stringify(H));
ok('③b 数值对（628 采样 / max h=1.0000 / 末 −0.9556，与 Node 侧一致）',
   !!(H && H.samples === '628' && H.hmax === '1.0000' && Math.abs(Number(H.hend) + 0.9556) < 1e-3),
   JSON.stringify(H));
// ③c 需求 D 的改名语义在**页内**也成立（非法名 `der(h)` → `der_h_`；`time` 撞内建 → `time_2`）
ok('③c 页内也走需求 D 的改名语义（der_h_ / time_2 在场）',
   !!(H && /der_h_/.test(String(H.vars)) && /time_2/.test(String(H.vars)) && H.renamed === '4'),
   `vars=${H && H.vars} renamed=${H && H.renamed}`);
ok('★④ 反向：坏件喂进 Octave ⇒ 必须明确报错', !!(P && P.reverseRejected),
   `reverse=${String(P && P.reverse || '').slice(-160)}`);

// ⑤ 内存/体积实测（同页成本的真值，不是估算）
const mem = (P && P.mem) || [];
console.log('     同页内存/体积：');
for (const row of mem) console.log('       ' + row.join(' | '));
ok('⑤ 内存实测有数（页面记账非空且含堆读数）',
   mem.length >= 2 && mem.some(r => /\d+ MB/.test(r[1])),
   JSON.stringify(mem).slice(0, 200));

// ⑥ 把实测**写进产物目录**（供台账读；值来自本次真跑，不手抄）
try {
  const OUT = process.env.SAMEPAGE_JSON
    || '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/samepage-cost.json';
  const pathOf = (u) => u.replace(/^https?:\/\/[^/]+\//, '').replace(/^\.\//, '');
  const OM_WASM = '/mnt/hdd/openmodelica-wasm-build/build/omc-out-web/web/omc/OpenModelicaCompiler_bg.wasm';
  const OCT_WASM = '/mnt/hdd/openmodelica-wasm-build/site-omc/oct/octave.wasm';
  const heapPeak = Math.max(...mem.map((r) => Number(String(r[1]).replace(/[^\d]/g, '')) || 0));
  const rec = {
    schema: 1,
    report: 'accept-samepage.mjs',
    when: new Date().toISOString(),
    om_wasm_bytes: statSync(OM_WASM).size,
    octave_wasm_bytes: statSync(OCT_WASM).size,
    sum_wasm_bytes: statSync(OM_WASM).size + statSync(OCT_WASM).size,
    js_heap_peak_bytes: heapPeak * 1000000,
    compile_ms_total: bothMs,
    compile_ms: compileProbe.map((x) => ({ name: x.name, ms: x.ms, exports: x.exports })),
    handoff: H || null,
    reverse_rejected: !!(P && P.reverseRejected),
    verdict: (fail === 0) ? 'ok' : 'fail',
    note: ('同页实测（wasm32 双引擎）。⚠️ 旧 samepage-cost.json 的口径（base64 测法）**已作废**，'
           + '见 build/retractions.json 的 R-R6-1：那次"整页崩"是测量方法的错。'),
  };
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(rec, null, 2) + '\n');
  console.log(`     实测已写出：${OUT}（verdict=${rec.verdict}）`);
} catch (e) { console.log('     (写实测文件失败，不影响判据: ' + String(e).slice(0, 80) + ')'); }

await browser.close();
console.log(`\n=== SAME-PAGE ${pass} PASS / ${fail} FAIL ===`);
process.exit(fail ? 1 : 0);
