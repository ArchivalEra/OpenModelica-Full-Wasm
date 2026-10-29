// OpenModelica-Full-Wasm — **E 线桥的「产品态」验收**（mail/107 §4 第 3 问的判据件）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 与 accept-omc-bridge.mjs 的分工（两件都要，缺一不可）：
//   · accept-omc-bridge.mjs  —— **注入式**：逐件 injectFile 写进 Octave MEMFS 再 addpath。
//     它验「桥本身对不对」（11/0）。但注入是**测试夹具**，不是产品装配。
//   · 本件（product）        —— **零注入**：只 `addpath('/bridge')`，靠站点自己铺好的文件。
//     它验「交付到位了没有」。
//
// ★ mail/107 实测出的正是这条缝：注入式全绿、产品里 omc_* 不存在。
//   本件的价值就是**在装配没做时红**（而不是像注入式那样自己把缺的东西补上）。
//
// 前置：宿主已把 bridge/ 铺进 Octave 站点（形态见 docs/BRIDGE-DELIVERY.md §2），
//       并已启动 OmcBridge.serve()（§3）。
// 跑法：sh test/browser/run-omc-bridge-product.sh [URL]
// 退出码：0 = 产品态跑通；1 = 判据红（装配没做对）；2 = 环境。
import { chromium } from 'playwright-core';

const URL = process.argv[2] || 'http://127.0.0.1:8761/';
const PASS = [], FAIL = [];
function t(name, cond, detail) {
  (cond ? PASS : FAIL).push(name);
  console.log((cond ? 'PASS | ' : 'FAIL | ') + name + (detail ? '  [' + detail + ']' : ''));
}

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await (await browser.newContext()).newPage();
  page.setDefaultTimeout(180000);
  await page.goto(URL, { waitUntil: 'domcontentloaded' });

  // 等 Octave 引擎就绪（与既有套件同一判据：eval_string 能算）
  let ready = false;
  const t0 = Date.now();
  while (Date.now() - t0 < 120000) {
    ready = await page.evaluate(() => {
      const M = window.Module || (window.__octaveHosts && window.__octaveHosts[0] && window.__octaveHosts[0].mod);
      if (!M || typeof M.eval_string !== 'function') return false;
      try { return M.eval_string('x=1+1;') === 0; } catch { return false; }
    }).catch(() => false);
    if (ready) break;
    await new Promise(r => setTimeout(r, 500));
  }
  t('① Octave 引擎就绪', ready);

  // ★ 关键：**只 addpath**，不注入任何文件
  const addOk = await page.evaluate(() => {
    const M = window.Module || (window.__octaveHosts && window.__octaveHosts[0] && window.__octaveHosts[0].mod);
    try { return M.eval_string("addpath('/bridge');") === 0; } catch { return false; }
  }).catch(() => false);
  t('② addpath(/bridge) 成功（不注入任何文件）', addOk);

  // ── 判据：三件对外 API 必须**已经存在**（这正是 107 说产品里没有的东西）────────
  // ★ 取值走 FS（唯一确定通道）：写结果文件再读回 —— 别指望输出汇（三层汇、且本页没有）
  const probeScript = [
    "fid = fopen('/tmp/__probe.txt', 'w');",
    "names = {'omc_simulate_model', 'omc_getVersion', 'omc_mat_load', 'sin', '__omc_absent_xyz__'};",
    "for k = 1:numel(names)",
    "  c = names{k};",
    "  if exist(c) ~= 0 || exist(c, 'file') ~= 0",
    "    fprintf(fid, '%s FOUND\\n', c);",
    "  else",
    "    fprintf(fid, '%s MISSING\\n', c);",
    "  end",
    "end",
    "fclose(fid);",
  ].join('\n');
  const probeOk = await page.evaluate((src) => {
    const M = window.Module || (window.__octaveHosts && window.__octaveHosts[0] && window.__octaveHosts[0].mod);
    try {
      M.FS.writeFile('/tmp/__probe.m', new TextEncoder().encode(src));
      return M.eval_string("source('/tmp/__probe.m');") === 0;
    } catch { return false; }
  }, probeScript).catch(() => false);

  const probe = await page.evaluate(() => {
    const M = window.Module || (window.__octaveHosts && window.__octaveHosts[0] && window.__octaveHosts[0].mod);
    try { return new TextDecoder().decode(M.FS.readFile('/tmp/__probe.txt')); } catch { return ''; }
  }).catch(() => '');

  const has = (n) => new RegExp('^' + n + ' FOUND$', 'm').test(probe);
  t('③ 产品里 omc_simulate_model 存在（装配到位）', has('omc_simulate_model'), probe.replace(/\n/g, ' | ').slice(0, 180));
  t('④ 产品里 omc_getVersion 存在', has('omc_getVersion'));
  t('⑤ 产品里 omc_mat_load 存在', has('omc_mat_load'));
  // ── 反向/对照断言：证明探针有区分力（107 §1 的做法）────────────────────────────
  t('★⑥ 对照：内建 sin 判 FOUND（正例）', has('sin'));
  t('★⑦ 对照：不存在的名字判 MISSING（探针能区分）', /^__omc_absent_xyz__ MISSING$/m.test(probe));
  t('⑥ 探针脚本自身跑通（source 返回 rc=0）', probeOk);

  await browser.close();
  console.log(`\n=== BRIDGE-PRODUCT ${PASS.length} PASS / ${FAIL.length} FAIL ===`);
  if (FAIL.length) {
    console.log('\n诊断：③④⑤ 红 ⇒ 站点没有铺 bridge/（宿主装配未做）。');
    console.log('      形态见 docs/BRIDGE-DELIVERY.md §2；清单见 bridge/manifest.json。');
  }
  process.exit(FAIL.length ? 1 : 0);
})().catch(e => { console.error('FATAL:', e); process.exit(2); });
