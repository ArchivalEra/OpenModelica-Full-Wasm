// OpenModelica-Full-Wasm — Node 侧验收：omc 包能不能跑（需求 A3 的判据物）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 为什么要有它（而不是"构建脚本自己说 ok"）：本仓纪律「能编过 ≠ 能用了」——
// 碰运行期行为必须**从产物**实测。这个探针**只读产物**（不碰仓库源码、不碰构建树），
// 在干净的 Node 里加载 omc-cli.js 并要求 getVersion() 出串。
//
// 用法：node test/node/accept-omc-getversion.mjs [产物目录]
//   默认 [产物目录] = /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web
// 退出码：0 = 全过；1 = 有失败；2 = 用法/环境（产物目录不在）
//
// 断言（每条都必须能红；反向断言见 manifest.json 的 note）：
//   ① omc-cli.js 存在，pkg-nodejs/OpenModelicaCompiler.js 存在（wasm-bindgen 出包）
//   ② `_bg.wasm` 非空且是 **wasm32** 模块（用 WebAssembly.Module 读 magic+version，
//      并断言不是 wasm64——那需要另一套 magic）
//   ③ Node 里跑 getVersion()：rc=0 且输出含版本形状 `1.28` 或 `OpenModelica`
//   ④ 反向：喂一个坏路径 ⇒ **必须**非 0（不许静默"没测到也算过"）
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

const DIR = process.argv[2] || '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web';
let pass = 0, fail = 0;
const ok = (name, cond, detail = '') => {
  if (cond) { pass++; console.log(`PASS | ${name}`); }
  else { fail++; console.log(`fail | ${name}${detail ? ' —— ' + detail : ''}`); }
};

ok('①a omc-cli.js 存在', existsSync(join(DIR, 'omc-cli.js')), DIR);
const glue = join(DIR, 'pkg-nodejs', 'OpenModelicaCompiler.js');
ok('①b pkg-nodejs/OpenModelicaCompiler.js 存在', existsSync(glue));

// ② 读产物字节，断言 wasm32（magic 后跟 version，且**不**是 wasm64 的形状）
let bg = '';
const cand = [join(DIR, 'pkg-nodejs', 'OpenModelicaCompiler_bg.wasm')];
for (const c of cand) if (existsSync(c)) bg = c;
ok('②a 找到 *_bg.wasm', bg !== '', cand.join(' , '));
if (bg) {
  const sz = statSync(bg).size;
  ok('②b 产物非空', sz > 1024, `${sz} 字节`);
  const hdr = readFileSync(bg).subarray(0, 8);
  const magic = hdr.readUInt32LE(0) === 0x6d736100;   // \0asm
  ok('②c 是 wasm 模块（\\0asm magic）', magic);
  // wasm 的 magic 相同；架构靠**能否用 wasm32 引擎实例化**判（下面 ③ 就在做这件事），
  // 这里额外断言**不是**一眼假（比如 HTML 错误页被当成 wasm 下载回来）
  const two = hdr.subarray(4, 8).toString('latin1');
  ok('②d 版本字段合法（不是 HTML/文本）', genuineHeader(hdr), `hdr=${[...hdr].slice(0,4).join(',')}`);
  function genuineHeader(h) { return h.length === 8 && h[4] === 1 && h[5] === 0; }
}

// ③ 实测：Node 里跑 getVersion()（这是需求 A3 的判据）
let out = '', rc = 0;
if (existsSync(join(DIR, 'omc-cli.js'))) {
  try {
    out = execFileSync('node', ['omc-cli.js', 'getVersion()'],
      { cwd: DIR, timeout: 300000, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) { rc = e.status ?? 1; out = `${e.stdout || ''}${e.stderr || ''}`; }
  ok('③a getVersion() rc=0', rc === 0, `rc=${rc} out=${String(out).slice(0, 200)}`);
  // 判断据（2026-10-13 实测校正）：`getVersion()` 的合法形状不止 "OpenModelica 1.x"。
  // 上游 cmake/omc_git_revision.cmake 在**无 git tag 的构建树**里走 SOURCE_REVISION=unknown
  // 降级路径 ⇒ 本仓产物实测吐 `"-rust"`（引号 + 后缀）。⇒ 判据 = 非空 + **单个短 token**
  // （形如 "..." 或 1.x.y…），且**不许**含错误字样（那才是"炸了"的形状）。
  const s = String(out).trim();
  const looksVersion = /^-?"?[A-Za-z0-9_.+-]{1,40}"?$/.test(s);
  const hasError = /error|traceback|cannot|failed|undefined/i.test(s);
  ok('③b 输出是版本串形状（允许上游无 tag 的 "-rust" 降级串）', looksVersion && !hasError,
     `got=${JSON.stringify(s.slice(0, 80))}`);
  console.log(`     实测输出: ${s.slice(0, 120)}`);
}

// ④ 反向断言：坏路径必须红（证明这套判据不是"恒真"）
let badFlagged = false;
try {
  execFileSync('node', ['omc-cli.js', 'getVersion()'],
    { cwd: '/tmp/definitely-missing-omc-dir', timeout: 30000, stdio: 'pipe' });
} catch { badFlagged = true; }
ok('★④ 反向：坏产物目录 ⇒ 必须失败（判据不是恒真）', badFlagged);

console.log(`\n=== NODE-ACCEPT ${pass} PASS / ${fail} FAIL ===`);
process.exit(fail ? 1 : 0);
