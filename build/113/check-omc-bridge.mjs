#!/usr/bin/env node
// OpenModelica-Full-Wasm — **omc_bridge.js 产品件自证**（宿主 mail/024 §2 的三条承重语义）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 为什么要有这件：宿主指出「三条承重语义只活在验收套件里」——它要求把语义放进
// **交付模块**（bridge/omc_bridge.js）而不是测试文件。放进去之后还得**可复跑**，
// 否则下次改动一样会悄悄丢掉某一条。
//
// 判据（用假 omc / 假 FS，纯 Node，无浏览器）：
//   ① getVersion
//   ② cd("<path>")            —— 承重语义 ①（仿真输出目录跟 cwd 走）
//   ③ loadFile 必须**搬字节**   —— 承重语义 ②（两个 wasm 的 VFS 互不可见）
//   ④ simulate 结果**回搬** + `MAT <path>` —— 承重语义 ③
//   ⑤ simulateModel 一步到位（需求 E2 的判据形态）
//   ⑥ 反向：未知命令必须被拒绝（判据可证伪，不是恒真）
//
// 用法：node build/113/check-omc-bridge.mjs [--selftest]
// 退出码：0 = 全过；1 = 判据红；2 = 环境。
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const BRIDGE = '/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm/bridge/omc_bridge.js';

function harness() {
  const calls = [];
  const fsmap = { '/tmp/BouncingBall.mo': 'model BouncingBall end BouncingBall;' };
  const omc = {
    omc_eval: (s) => {
      calls.push(s);
      if (/getVersion/.test(s)) return '"-rust"';
      if (/cd\(/.test(s)) return 'true';
      if (/loadFile/.test(s)) return 'true';
      if (/getErrorString/.test(s)) return '';
      return '';
    },
    omc_simulate: () => 'resultFile = "/tmp/BouncingBall_res.mat"',
    wasi_write_file: (p, b) => { calls.push('vfs-write:' + p + ':' + b.length); return true; },
    wasi_path_open: () => 7,
    wasi_fd_read: () => new Uint8Array([1, 2, 3]),
    wasi_fd_close: () => {},
  };
  const ctx = {
    omc,
    writeFile: async (p, b) => { fsmap[p] = b; calls.push('oct-write:' + p); return true; },
    readFile: async (p) => fsmap[p] || null,
    modelFileOf: (c) => '/tmp/' + c + '_res.mat',
  };
  return { ctx, calls, fsmap };
}

async function run() {
  const B = require(BRIDGE);
  const { ctx, calls } = harness();
  const out = [];
  const t = (name, cond) => out.push([name, !!cond]);

  let r = await B.dispatch('getVersion()', ctx);
  t('① getVersion 返回版本串', r.ok && /-rust/.test(r.payload));

  r = await B.dispatch('cd("/tmp")', ctx);
  t('② cd 转发给 omc（承重语义 ①：输出目录跟 cwd）', r.ok && calls.some((c) => c.startsWith('cd("')));

  r = await B.dispatch('loadFile("/tmp/BouncingBall.mo")', ctx);
  t('③ loadFile 从 Octave 侧读、写进 omc VFS（承重语义 ②：搬字节）',
    r.ok && calls.some((c) => c.startsWith('vfs-write:/tmp/BouncingBall.mo:')));

  r = await B.dispatch('simulate(BouncingBall, stopTime=3.0)', ctx);
  t('④ simulate 先 cd(/tmp)（语义 ①）',
    calls.some((c) => c === 'cd("/tmp")'));
  t('④b simulate 把 .mat 回搬进 Octave 并回 `MAT <path>`（语义 ③）',
    r.ok && /^MAT \/tmp\/BouncingBall_res\.mat$/.test(r.payload)
    && calls.some((c) => c === 'oct-write:/tmp/BouncingBall_res.mat'));

  r = await B.dispatch('simulateModel(BouncingBall, stopTime=3.0)', ctx);
  t('⑤ simulateModel 一步到位（需求 E2 判据形态）', r.ok && /^MAT /.test(r.payload));

  r = await B.dispatch('bogus()', ctx);
  t('★⑥ 反向：未知命令必须拒绝（判据不是恒真）', !r.ok && /不支持的命令/.test(r.payload));

  let pass = 0, fail = 0;
  for (const [name, ok] of out) {
    (ok ? pass++ : fail++);
    console.log((ok ? 'PASS | ' : 'FAIL | ') + name);
  }
  console.log(`=== check-omc-bridge 自证：${pass} PASS / ${fail} fail ===`);
  return fail === 0;
}

const ok = await run();
process.exit(ok ? 0 : 1);
