// OpenModelica-Full-Wasm — Export FMU 验收（mail/008 缺陷 1 的回归判据）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 判什么：/simulator/index.html 对默认 BouncingBall 点 Export FMU：
//   ① 仿真先跑通（banner 出 points）——导出的前置；
//   ② 打开导出对话框（ME+CS 默认勾选）点 Export；
//   ③ ★ 正例：status 变「Exported *.fmu …」且触发浏览器下载（修复后形状）；
//   ④ ★ 反向（缺陷 1 的形状必须红）：status 出现
//      `unrecognized \`dylink.0\` subsection` / `failed to extract linking metadata`
//      ⇒ 直接 FAIL（那是 2026-10-19 钓鱼执法抓到的发信级缺陷，不许回来）。
//
// 跑法：sh test/browser/run-export-fmu.sh [URL]（默认 8765 /simulator/）
// 退出码：0 = 全过；1 = 判据红；2 = 环境/超时。
const URL = process.argv[2] || 'http://127.0.0.1:8765/simulator/';
import { chromium } from 'playwright-core';

const PASS = [], FAIL = [];
function t(name, cond, detail) {
  (cond ? PASS : FAIL).push(name);
  console.log((cond ? 'PASS | ' : 'FAIL | ') + name + (detail ? '  [' + detail + ']' : ''));
}
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await (await browser.newContext()).newPage();
  page.setDefaultTimeout(180000);

  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(URL, { waitUntil: 'domcontentloaded' });

  // ── ① 等仿真跑通（banner 出 points —— 那是「模型已编译」的信号）─────────────
  let simOk = false, banner = '';
  const t0 = Date.now();
  while (Date.now() - t0 < 120000) {
    banner = await page.locator('#status').innerText().catch(() => '');
    if (/points/.test(banner)) { simOk = true; break; }
    await sleep(500);
  }
  t('① 默认 BouncingBall 仿真跑通（banner 出 points）', simOk, banner);

  // ── ② 打开 Export FMU 对话框 ────────────────────────────────────────────────
  const exportBtn = page.locator('#exportFmu');
  await exportBtn.waitFor({ state: 'visible' });
  let enabled = false;
  const t1 = Date.now();
  while (Date.now() - t1 < 60000) {          // disabled 直到模型 ready
    if (await exportBtn.isEnabled()) { enabled = true; break; }
    await sleep(300);
  }
  t('②a Export FMU 按钮可点（模型 ready）', enabled);
  await exportBtn.click();
  await page.locator('#exportGo').waitFor({ state: 'visible' });
  const meChecked = await page.locator('#fmiMe').isChecked();
  const csChecked = await page.locator('#fmiCs').isChecked();
  t('②b 对话框开且 ME/CS 默认勾选（mail/008 的复现路径）', meChecked && csChecked);

  // ── ③ 点 Export；捕获下载 ──────────────────────────────────────────────────
  const dlPromise = page.waitForEvent('download', { timeout: 120000 }).catch(() => null);
  await page.locator('#exportGo').click();

  // 轮询 status：成功（Exported …）或失败（红错）
  let finalStatus = '', decided = false;
  const t2 = Date.now();
  while (Date.now() - t2 < 120000) {
    finalStatus = await page.locator('#status').innerText().catch(() => '');
    if (/Exported .*\.fmu/.test(finalStatus)) { decided = true; break; }
    if (/dylink\.0|extract linking metadata|failed|error/i.test(finalStatus)) { decided = true; break; }
    await sleep(400);
  }
  const dl = await dlPromise;

  // ── ③ ★ 正例：Exported + 下载触发 ──────────────────────────────────────────
  t('③a Export 成功（status 出 Exported *.fmu）', /Exported .*\.fmu/.test(finalStatus), finalStatus.slice(0, 140));
  t('③b 浏览器下载被触发（.fmu 文件）', dl !== null, dl ? dl.suggestedFilename() : '无下载事件');

  // ── ④ ★ 反向：缺陷 1 的报错文案绝不许出现 ─────────────────────────────────
  const bad = /unrecognized .dylink\.0. subsection|failed to extract linking metadata/.test(finalStatus);
  t('★④ 反向：缺陷 1 报错（dylink.0 subsection 6）未出现', !bad, bad ? finalStatus.slice(0, 160) : '');

  await browser.close();
  console.log(`\n=== EXPORT-FMU ${PASS.length} PASS / ${FAIL.length} FAIL ===`);
  process.exit(FAIL.length ? 1 : 0);
})().catch(e => { console.error('FATAL:', e); process.exit(2); });
