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

  // ── 就绪门（2026-10-29 修：原门早了 ~400ms，导致 3 条假红）────────────────────
  // ★ 宿主 mail/027 §2 实测（我独立复现）：`x=1+1` 在 763ms 就通过，而那时 `/bridge`
  //   里 0 件；`__octaveReady` 到 1159ms（`/bridge` 14 件）⇒ 原门比"装配就位"早 ~400ms，
  //   于是在 MEMFS 还空着时探 exist() ⇒ 3 条必然 MISSING（假红）。
  // 新门用**本桥的装配定义**（不依赖某个站点的全局标志）：
  //   ① 引擎可算（eval_string 能跑）——必要条件；
  //   ② /bridge 在 MEMFS 里且非空——**这是"装配就位"的直接定义**。
  // 兼容：若站点自己暴露 `window.__octaveReady`，它也必须在（双条件取交集的一个软项，
  //   不作硬要求——别的站点可能没有这个变量，硬要就把判据绑死在某个实现上）。
  let ready = false, gateInfo = {};
  const t0 = Date.now();
  while (Date.now() - t0 < 180000) {
    gateInfo = await page.evaluate(() => {
      const M = window.Module || (window.__octaveHosts && window.__octaveHosts[0] && window.__octaveHosts[0].mod);
      let canEval = false;
      try { canEval = !!(M && typeof M.eval_string === 'function' && M.eval_string('x=1+1;') === 0); } catch {}
      let bridgeFiles = 0;
      try { bridgeFiles = M && M.FS ? M.FS.readdir('/bridge').filter((n) => n !== '.' && n !== '..').length : 0; } catch { bridgeFiles = 0; }
      return { canEval, bridgeFiles, octaveReady: window.__octaveReady === true };
    }).catch(() => ({ canEval: false, bridgeFiles: 0, octaveReady: false }));
    // 门 = 能算 且 /bridge 非空（装配就位）
    if (gateInfo.canEval && gateInfo.bridgeFiles > 0) { ready = true; break; }
    await new Promise(r => setTimeout(r, 250));
  }
  t('① 就绪（引擎可算 + /bridge 在 MEMFS 里非空）', ready,
    `files=${gateInfo.bridgeFiles} octaveReady=${gateInfo.octaveReady}`);

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

  // ★⑧ 门自证（本轮缺陷的回归）：就绪门必须包含"/bridge 非空"这一条，
  //   否则会退回"引擎能算就算就绪"⇒ MEMFS 空着时探 exist ⇒ 3 条假红（2026-10-29 实测）。
  //   这里直接从 gateInfo 判：真到了就绪时 /bridge 必须非空（若门只等高能算，这个值会是 0）。
  t('★⑧ 门自证：就绪时 /bridge 非空（防"门太早"回归）',
    gateInfo.bridgeFiles > 0, `bridgeFiles=${gateInfo.bridgeFiles}`);

  await browser.close();
  console.log(`\n=== BRIDGE-PRODUCT ${PASS.length} PASS / ${FAIL.length} FAIL ===`);
  if (FAIL.length) {
    console.log('\n诊断：③④⑤ 红 ⇒ 站点没有铺 bridge/（宿主装配未做）。');
    console.log('      形态见 docs/BRIDGE-DELIVERY.md §2；清单见 bridge/manifest.json。');
  }
  process.exit(FAIL.length ? 1 : 0);
})().catch(e => { console.error('FATAL:', e); process.exit(2); });
