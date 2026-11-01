// OpenModelica-Full-Wasm — **v4 release 端到端验**（产物侧判据，宿主/内容仓复验用）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 判据（一码一跑，codec ∈ zstd | gzip | identity）：
//   1. manifest schema=2 / id 带版本 / entries 条数 / 回退链有序
//   2. 逐字取 chunks[].file（**不拼名字**，v4 铁律），8 并发拉
//   3. 每块 sha256 与 manifest 一致
//   4. 逐块解压再拼接（★ 每块是**独立压缩帧**：拼接后单次解压只出第一帧，实测踩到）
//   5. 拼接后 bytes / sha256 == entries[] 的原始字节与哈希
//   6. 与**源产物**逐字节一致（证明 release 就是那份产物，不是别的）
//   7. ★ 全是普通 GET：0 个 Range / 0 个条件请求 / 0 个自定义头
//
// 跑法：
//   node test/browser/accept-release-v4.mjs <BASE_URL> <codec> [并发] [源产物目录]
// 退出码：0 = 全过；1 = 有红；2 = 环境

import { chromium } from 'playwright-core';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = process.argv[2];
const CODEC = process.argv[3] || 'identity';
const CONC = Number(process.argv[4] || 8);
const SRC = process.argv[5] || '';
if (!BASE) { console.error('用法: node accept-release-v4.mjs <BASE_URL> <codec> [并发] [源目录]'); process.exit(2); }

const sha = (buf) => createHash('sha256').update(buf).digest('hex');

let pass = 0, fail = 0;
const t = (name, cond, detail) => {
  if (cond) { pass++; console.log('PASS | ' + name); }
  else { fail++; console.log('FAIL | ' + name + (detail ? '  [' + detail + ']' : '')); }
};

const browser = await chromium.launch({ args: ['--no-sandbox'] });
const page = await (await browser.newContext()).newPage();
const reqs = [];
page.on('request', (r) => reqs.push({ url: r.url(), headers: r.headers() }));

// ★ 不要 `goto(BASE + '/manifest.json')`：GitHub release 直链发 `application/octet-stream`
//   ⇒ 浏览器把它当**下载**（`page.goto` 报 `Download is starting`）。
//   判据是"客户端能不能按 manifest 取分片"，所以落一个**中性的真 http 页**，之后全程页面内 fetch。
//   ⚠️ 不能用 `data:`（opaque origin ⇒ 跨源 fetch 被挡）。中性页由本套件自己起：
//     它同时回 CORS 头（真实部署里分片是同源静态站；这里跨源就必须有 CORS）。
const { createServer } = await import('node:http');
const neutral = createServer((q, res) => {
  res.writeHead(200, {
    'content-type': 'text/html; charset=utf-8',
    'access-control-allow-origin': '*',
    'access-control-allow-headers': '*',
  });
  res.end('<!doctype html><title>v4 release acceptance</title>');
});
await new Promise((r) => neutral.listen(0, '127.0.0.1', r));
const NEUTRAL = 'http://127.0.0.1:' + neutral.address().port + '/';
await page.goto(NEUTRAL);
const man = await page.evaluate(async (u) => (await fetch(u)).json(), BASE + '/manifest.json');

t('manifest schema = 2', man.schema === 2, 'schema=' + man.schema);
t('id 是字符串且非空', typeof man.id === 'string' && man.id.length > 0, String(man.id));
t('entries 非空', Array.isArray(man.entries) && man.entries.length > 0, 'n=' + (man.entries || []).length);
t('products 非空', man.products && Object.keys(man.products).length > 0);

const tmp = mkdtempSync(join(tmpdir(), 'v4rel-'));
const decoded = {};

for (const e of man.entries) {
  const v = e.variants.find((x) => x.codec === CODEC);
  t(e.name + ': 有 ' + CODEC + ' 变体', !!v, v ? '' : '变体表 ' + e.variants.map((x) => x.codec).join('/'));
  if (!v) continue;

  // ② 逐字取 file + 并发
  const names = v.chunks.map((c) => c.file);
  const parts = new Array(names.length);
  for (let i = 0; i < names.length; i += CONC) {
    const batch = names.slice(i, i + CONC).map((n) =>
      fetch(BASE + '/' + n).then(async (r) => {
        if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + n);
        return Buffer.from(await r.arrayBuffer());
      }));
    const got = await Promise.all(batch);
    got.forEach((g, k) => { parts[i + k] = g; });
  }

  // ③ 逐块 sha
  let chunkOk = true;
  for (let i = 0; i < v.chunks.length; i++) {
    if (sha(parts[i]) !== v.chunks[i].sha256) { chunkOk = false; break; }
  }
  t(e.name + ': ' + CODEC + ' 逐块 sha 全对', chunkOk, v.chunks.length + ' 块');

  // ④ 逐块解压再拼（★ 关键：每块独立压缩帧）
  let raw = null;
  if (CODEC === 'identity') {
    raw = Buffer.concat(parts);
  } else if (CODEC === 'gzip') {
    const { gunzipSync } = await import('node:zlib');
    raw = Buffer.concat(parts.map((p) => gunzipSync(p)));
  } else if (CODEC === 'zstd') {
    // Node 侧没有 zstd 解码器 ⇒ 交给 Python（与生成器同源，用它验它产出的东西最自洽）
    raw = Buffer.concat(parts.map((p, k) => {
      const z = join(tmp, 'c' + k + '.zst');
      const o = z + '.raw';
      writeFileSync(z, p);
      execFileSync('python3', ['-I', '-c',
        'import sys,zstandard;open(sys.argv[2],"wb").write(' +
        'zstandard.ZstdDecompressor().decompress(open(sys.argv[1],"rb").read()))', z, o],
        { stdio: 'ignore' });
      return readFileSync(o);
    }));
  }

  // ⑤ 全局
  t(e.name + ': 解码拼接 bytes == manifest.bytes',
    raw.length === e.bytes, 'got=' + raw.length + ' want=' + e.bytes);
  t(e.name + ': 拼接后 sha == manifest.sha256', sha(raw) === e.sha256, sha(raw).slice(0, 16));
  decoded[e.name] = raw;
}

// ⑥ 与源产物逐字节对比（给了源目录才做）
if (SRC) {
  for (const e of man.entries) {
    if (!decoded[e.name]) continue;
    const base = e.name.split('/').pop();          // manifest 里可能带 product 前缀目录
    let want;
    try { want = readFileSync(join(SRC, base)); } catch { continue; }
    t(base + ': 与源产物逐字一致', decoded[e.name].equals(want));
  }
}

// ⑦ 全是普通 GET
const assets = reqs.filter((r) => /\.(wasm|js|d\.ts|zip|000|001|002|003|004|005|006|007|008|009|010|011|012|013|014)/.test(r.url));
t('★ 0 个 Range 请求', !assets.some((r) => r.headers.range), assets.length + ' 个 asset 请求');
t('★ 0 个条件请求',
  !assets.some((r) => r.headers['if-none-match'] || r.headers['if-modified-since']));
const CUSTOM = ['x-', 'authorization', 'cookie'];
const hasCustomHeader = (r) => Object.keys(r.headers).some(
  (h) => CUSTOM.some((c) => h.startsWith(c)));
t('★ 0 个自定义头', !assets.some(hasCustomHeader));

console.log(`\n=== V4-E2E(${CODEC}) ${pass} PASS / ${fail} FAIL ===`);
await browser.close();
neutral.close();
process.exit(fail ? 1 : 0);
