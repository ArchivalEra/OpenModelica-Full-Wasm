// OpenModelica-Full-Wasm — **74 MB ESM 引擎的浏览器 boot 分布**（宿主 mail/027 §4 / mail/029 §5）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 为什么单独一件：`accept-omc-bridge-product.mjs` 只回答「装配到没到位」（一次采样），
//   不回答「用户要等多久、会不会失败、第二次来还等不等」。宿主观测到 8761 在页面
//   ready 时仍是 `omc-not-ready` —— 那是**产品决定**（74 MB 引擎该不该进开机路径），
//   得先有分布才能谈。
//
// 测什么（每次跑 = 一个**全新浏览器实例** ⇒ 冷启动）：
//   t_page_ready  页面 `window.__octaveReady === true`（宿主的"资产就位"定义）
//   t_memfs       `__octaveOmcBridge` 离开 'assembling'（= 12 件进 MEMFS + addpath）
//   t_ready       引擎 boot 全过（state = 'ready'）—— 这才是 `omc_*` 真能跑的时点
//   wasm          resource timing 里 `OpenModelicaCompiler_bg.wasm` 的传输/解码耗时
//   failure       落到失败态（状态机三档 + 清单 404）或超时 ⇒ 计入失败率
//
// ★ 观测不侵入产品：只读页面的 `__octaveOmcBridge` 状态机与 resource timing，
//   不注入任何桥文件、不改站点、不调 ensure()（页面自己的 boot 链会调）。
//
// 跑法：sh test/browser/run-measure-omc-boot.sh [URL] [N] [OUT.json]
//   默认 URL=http://127.0.0.1:8761/  N=5
//   OMC_BOOT_KBPS=8000 模拟 64 Mbit 宽带（74 MB ⇒ ~18 s）；
//   OMC_BOOT_KBPS=600 模拟弱 4.8 Mbit（74 MB 单独 ~124 s）；
//   不给 = 环回（~1 GB/s），那是**下限**，不是用户的处境。
// 退出码：0 = 所有跑次都 ready；1 = 有失败；2 = 环境
import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const URL = process.argv[2] || 'http://127.0.0.1:8761/';
const RUNS = Number(process.argv[3] || 5);
const OUT = process.argv[4] || '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/omc-boot.json';
const RUN_TIMEOUT_MS = Number(process.env.OMC_BOOT_TIMEOUT_MS || 300000);
// ★ 环回带宽 (~1 GB/s) 会把 74 MB 的传输压成 ~80 ms —— 那不是用户的处境。
//   限速只改本进程的 CDP 会话，不动站点、不动系统。
const THROTTLE_KBPS = Number(process.env.OMC_BOOT_KBPS || 0);
// 复用 profile ⇒ 能测「HTTP 缓存有没有用」；不给 ⇒ 每次全新实例（冷启动）。
const PROFILE = process.env.OMC_BOOT_PROFILE || '';

const FAIL_STATES = new Set([
  'bridge-not-assembled', 'no-site-bytes', 'bridge-not-serving',
]);
// 'omc-not-ready' 既是"boot 中"也是失败态的名称 ⇒ 只有**超时**还停在这里才算失败。

const median = (a) => {
  const s = [...a].sort((x, y) => x - y);
  if (!s.length) return null;
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : Math.round((s[m - 1] + s[m]) / 2);
};

async function oneRun(i) {
  const launchOpts = { args: ['--no-sandbox'] };
  const browser = PROFILE
    ? await chromium.launchPersistentContext(PROFILE, launchOpts)
    : await chromium.launch(launchOpts);
  const ctx = PROFILE ? browser : await browser.newContext();
  const page = PROFILE ? (browser.pages()[0] || await browser.newPage()) : await ctx.newPage();
  page.setDefaultTimeout(RUN_TIMEOUT_MS);
  // CDP：① 限速 ② 读**是否真的走了网络**（`fromDiskCache`）——只有它能分辨
  //   "HTTP 有响应"与"字节从盘上来"（resource timing 的 transferSize 在环回下不可靠）
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Network.enable');
  if (THROTTLE_KBPS > 0) {
    await cdp.send('Network.emulateNetworkConditions', {
      offline: false, latency: 40,
      downloadThroughput: THROTTLE_KBPS * 1024,
      uploadThroughput: THROTTLE_KBPS * 256,
    });
  }
  const wasmNet = [];
  cdp.on('Network.requestWillBeSent', (e) => {
    if (/OpenModelicaCompiler_bg\.wasm/.test(e.request.url)) wasmNet.push({ reqId: e.requestId, fromDiskCacheAtReq: !!e.request.fromDiskCache });
  });
  cdp.on('Network.responseReceived', (e) => {
    if (/OpenModelicaCompiler_bg\.wasm/.test(e.response.url)) {
      const m = wasmNet.find((r) => r.reqId === e.response.requestId);
      if (m) { m.fromDiskCache = !!e.response.fromDiskCache; m.cacheControl = e.response.headers['cache-control'] || '(none)'; }
    }
  });
  cdp.on('Network.loadingFinished', (e) => {
    const m = wasmNet.find((r) => r.reqId === e.requestId);
    if (m) m.networkBytes = e.encodedDataLength;
  });

  let rec = { run: i + 1, ok: false, state: null, detail: '', t_page_ready_ms: null, t_memfs_ms: null, t_ready_ms: null, wasm: null, wasm_net: null, transitions: [] };
  try {
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => {
      const t0 = performance.now();
      window.__bootProbe = { t0, transitions: [] };
      const seen = new Set();
      window.__bootTimer = setInterval(() => {
        const b = window.__octaveOmcBridge;
        if (!b) return;
        const key = b.state + '|' + (b.detail || '');
        if (seen.has(key)) return;
        seen.add(key);
        window.__bootProbe.transitions.push({ t: Math.round(performance.now() - t0), state: b.state, detail: (b.detail || '').slice(0, 160) });
      }, 50);
    });
    const tStart = Date.now();
    let pageReady = false, sawReady = null, memfsT = null;
    while (Date.now() - tStart < RUN_TIMEOUT_MS) {
      const s = await page.evaluate(() => {
        const b = window.__octaveOmcBridge;
        return {
          octaveReady: window.__octaveReady === true,
          state: b ? b.state : null, detail: b ? (b.detail || '').slice(0, 200) : '',
          transitions: (window.__bootProbe && window.__bootProbe.transitions) || [],
        };
      }).catch(() => null);
      if (!s) break;
      rec.state = s.state; rec.detail = s.detail; rec.transitions = s.transitions;
      if (s.octaveReady && !pageReady) { pageReady = true; rec.t_page_ready_ms = Date.now() - tStart; }
      if (memfsT == null) {
        const left = s.transitions.find((x) => x.state && x.state !== 'assembling' && x.state !== 'idle');
        if (left) memfsT = left.t;
      }
      if (s.state === 'ready') { rec.ok = true; rec.state = 'ready'; sawReady = Date.now() - tStart; break; }
      if (FAIL_STATES.has(s.state)) break;
      await new Promise((r) => setTimeout(r, 100));
    }
    rec.t_ready_ms = sawReady;
    rec.t_memfs_ms = memfsT;
    rec.wasm = await page.evaluate(() => {
      const e = performance.getEntriesByType('resource').find((x) => x.name.includes('OpenModelicaCompiler_bg.wasm'));
      return e ? { duration_ms: Math.round(e.duration), transfer_bytes: e.transferSize || 0, decoded_bytes: e.decodedBodySize || 0 } : null;
    }).catch(() => null);
    await new Promise((r) => setTimeout(r, 200));   // 让 loadingFinished 落地
    rec.wasm_net = wasmNet[wasmNet.length - 1] || null;
    await page.evaluate(() => clearInterval(window.__bootTimer)).catch(() => {});
  } catch (e) {
    rec.error = String((e && e.message) || e).slice(0, 300);
  } finally {
    await browser.close().catch(() => {});
  }
  return rec;
}

(async () => {
  const runs = [];
  for (let i = 0; i < RUNS; i++) {
    const r = await oneRun(i);
    runs.push(r);
    const net = r.wasm_net || {};
    console.log(`RUN ${r.run}: ${r.ok ? 'ready' : 'FAIL(' + (r.state || r.error || 'timeout') + ')'}`
      + `  page_ready=${r.t_page_ready_ms ?? '-'}ms  memfs=${r.t_memfs_ms ?? '-'}ms  engine_ready=${r.t_ready_ms ?? '-'}ms`
      + `  wasm_net=${net.networkBytes ?? '?'}B cache=${net.fromDiskCache ? 'DISK' : 'network'}(${net.cacheControl ?? '?'})`);
    if (!r.ok) console.log(`  detail=${JSON.stringify(r.detail)} error=${JSON.stringify(r.error || '')}`);
  }
  const okRuns = runs.filter((r) => r.ok);
  const readyM = okRuns.map((r) => r.t_ready_ms).filter((v) => v != null);
  const memfsM = runs.map((r) => r.t_memfs_ms).filter((v) => v != null);
  const netM = runs.map((r) => r.wasm_net && r.wasm_net.networkBytes).filter((v) => v != null);
  const summary = {
    measured_at: new Date().toISOString(),
    url: URL,
    runs: runs.length,
    failures: runs.length - okRuns.length,
    throttle_kbps: THROTTLE_KBPS || 'none (loopback)',
    persistent_profile: PROFILE || null,
    engine_ready_ms: readyM.length
      ? { min: Math.min(...readyM), p50: median(readyM), max: Math.max(...readyM) }
      : null,
    memfs_ms_p50: median(memfsM),
    wasm_network_bytes_p50: median(netM),
    wasm_bytes: (runs.find((r) => r.wasm) || { wasm: {} }).wasm?.decoded_bytes || 0,
    results: runs,
  };
  try {
    mkdirSync(dirname(OUT), { recursive: true });
    writeFileSync(OUT, JSON.stringify(summary, null, 2) + '\n');
    console.log(`wrote ${OUT}`);
  } catch (e) { console.error('warn: 写不了 ' + OUT + ': ' + e.message); }
  console.log(`\n=== OMC-BOOT runs=${summary.runs} fail=${summary.failures} `
    + `throttle=${summary.throttle_kbps} `
    + `engine_ready_p50=${summary.engine_ready_ms?.p50 ?? '-'}ms `
    + `min=${summary.engine_ready_ms?.min ?? '-'} max=${summary.engine_ready_ms?.max ?? '-'} `
    + `memfs_p50=${summary.memfs_ms_p50 ?? '-'}ms wasm_net_p50=${summary.wasm_network_bytes_p50 ?? '-'}B ===`);
  process.exit(summary.failures ? 1 : 0);
})().catch((e) => { console.error('FATAL:', e); process.exit(2); });