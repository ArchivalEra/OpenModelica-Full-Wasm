// OpenModelica-Full-Wasm — Node 侧验收：**模型能不能在 wasm 里跑完并出 .mat**（需求 B）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 判据（悬案 03 的 Settling）：
//   ① 编译器前端：loadFile true + getClassNames 含模型名
//   ② translateModel 真跑（不是只回 true —— 还要模型 wasm 真被写出，用 wasi_path_open 探）
//   ③ 仿真：`omc_simulate(...)` 跑完且 `resultFile` 非空
//   ④ **产物层**：那个 .mat 真存在、非空、前 4 字节是 MAT4/MAT5 魔数（不是空壳也不是错误页）
//   ⑤ 反向断言：坏模型（语法错）⇒ **必须**报错（判据不是恒真）
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const DIR = process.argv[2] || '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web';
let pass = 0, fail = 0;
const ok = (name, cond, detail = '') => {
  if (cond) { pass++; console.log(`PASS | ${name}`); }
  else { fail++; console.log(`fail | ${name}${detail ? ' —— ' + detail : ''}`); }
};

const MODEL = `model BouncingBall
  parameter Real e=0.7 "coefficient of restitution";
  parameter Real g=9.81 "gravity acceleration";
  Real h(fixed=true, start=1) "height of ball";
  Real v(fixed=true) "velocity of ball";
equation
  der(v) = -g;
  der(h) = v;
  when h <= 0 then
    reinit(v, -e*pre(v));
  end when;
end BouncingBall;
`;

if (!existsSync(join(DIR, 'omc-cli.js'))) {
  console.log(`fail | 产物目录不在（${DIR}）—— 先跑 build/113/build-omc-wasm.sh build`);
  process.exit(2);
}
const require = createRequire(import.meta.url);
const omc = require(join(DIR, 'pkg-nodejs', 'OpenModelicaCompiler.js'));
omc.omc_set_env('OPENMODELICAHOME', '/usr');
const inited = omc.omc_init();
ok('①a omc_init()', !!inited);
omc.omc_set_inwasm_driver(1);            // 在 wasm 内驱动（浏览器/Node 的路径）
const enc = new TextEncoder();
omc.wasi_write_file('/tmp/BouncingBall.mo', enc.encode(MODEL));
omc.omc_eval('cd("/tmp")');

// ⚠️ `omc_eval` 返回的是**字符串**（实测：`"true"` 带引号），不是 JS boolean。
// 判据按字符串比（`true` / `"true"` 都算）；**别**写 `=== true`（那会假红——本探针第一版就错在这）。
const truthy = (v) => /^"?true"?$/.test(String(v).trim());
const loaded = omc.omc_eval('loadFile("/tmp/BouncingBall.mo")');
ok('①b loadFile → true', truthy(loaded), String(loaded));
const names = String(omc.omc_eval('getClassNames()'));
ok('①c getClassNames 含 BouncingBall', names.includes('BouncingBall'), names.slice(0, 120));

omc.omc_eval('getErrorString()');
const tr = omc.omc_eval('translateModel(BouncingBall)');
ok('②a translateModel → true', truthy(tr),
   String(tr).slice(0, 200) + ' | err=' + String(omc.omc_eval('getErrorString()')).slice(0, 200));
// 模型 wasm 真被写出？（协议：translateModel 写 <prefix>.wasm）
let fd = -1;
try { fd = omc.wasi_path_open('/tmp/BouncingBall.wasm', 0); } catch { fd = -1; }
ok('②b 模型 wasm 真被写出（wasi_path_open 返回有效 fd）', typeof fd === 'number' && fd >= 0, `fd=${fd}`);

// ③ 仿真（六参签名）
const t0 = Date.now();
let simOut = '';
try {
  simOut = String(omc.omc_simulate('BouncingBall', 3.0, 500, 1e-6, 'dassl', ''));
} catch (e) { simOut = 'THREW: ' + String(e).slice(0, 300); }
const secs = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`     仿真耗时 ${secs}s`);
const simLog = String(omc.omc_sim_log() || '');
const blob = simOut + '\n' + simLog;
ok('③a 仿真没抛且没报错字样', !/THREW|simulation failed|LOG_ERROR|panicked/i.test(blob),
   blob.replace(/\s+/g, ' ').slice(0, 300));
// resultFile 非空 = 真产出了结果文件
const m = blob.match(/resultFile\s*=\s*"([^"]*)"/);
const resultFile = m ? m[1] : '';
ok('③b resultFile 非空', resultFile.length > 0, `resultFile=${JSON.stringify(resultFile)}`);

// ④ 产物层：结果文件**从 wasm VFS 里取出来**（不是宿主磁盘 —— 本产物跑在 wasm 内，
//    文件写在 omc 自己的 VFS 里；宿主 fs 上本来就没有，那是设计如此不是失败）。
//    取件协议（照 .d.ts 的契约，2026-10-14 实测）：
//      `wasi_path_open(path) → fd`（-1 = 不在）；`wasi_fd_read(fd) → Uint8Array`（整文件）。
let matBytes = null, matPath = resultFile || '/tmp/BouncingBall_res.mat';
{
  const fd = omc.wasi_path_open(matPath);
  if (typeof fd === 'number' && fd >= 0) {
    try { matBytes = omc.wasi_fd_read(fd); } finally { omc.wasi_fd_close(fd); }
  }
}
const matSize = matBytes ? matBytes.length : 0;
ok('④a 结果文件在 VFS 里且非空', matSize > 0, `path=${matPath} size=${matSize}`);
if (matBytes && matSize > 0) {
  const head = Buffer.from(matBytes.subarray(0, 128));
  // ⚠️ **MAT4 没有 ASCII 魔数**（本探针第一版就错在这：照 MAT5 的 `MATLAB 5.0 MAT-file`
  //    去判 ⇒ 假红）。MAT4 的判据是**类型码序列**：
  //      每个顶层项 = int32 类型码 + int32 字节数 + 载荷；`33` = miMATRIX，
  //      `04` = miUINT32，`0b` = miCOMPRESSED/miUTF8… 首项必是 33 00 00 00。
  //    更硬的旁证：**变量名字符串**（`Aclass` + 首个变量名，实测 `A1` / `bt`）。
  //    出处：上游 openmodelica_sim_meta/src/result.rs:166 `Mat4Stream::begin` /
  //          :361 `openmodelica_mat_writer::write_mat4`。
  const typeCode = head.readUInt32LE(0);
  const mrows = head.readUInt32LE(4);
  const ncols = head.readUInt32LE(8);
  const imagf = head.readUInt32LE(12);
  const nameLen = head.readUInt32LE(16);
  const name = head.subarray(20, 20 + Math.max(0, Math.min(nameLen - 1, 32))).toString('latin1');
  const asText = head.toString('latin1');
  // MAT4 首矩阵的**精确形状**（出处：上游 openmodelica_mat_writer/src/lib.rs:405-413
  // `write_mat_header`）：[i32 类型码][i32 mrows][i32 ncols][i32 imagf][i32 名长][名字\0]，
  // 全小端；首项必是 `Aclass` 这个 char 矩阵（lib.rs:152-153）。类型码 51 = mat_type(5,true)。
  const is4 = typeCode === 51 && mrows === 4 && ncols === 11 && imagf === 0 && name === 'Aclass';
  const is5 = asText.startsWith('MATLAB 5.0 MAT-file');
  const isArrow = asText.slice(0, 6) === 'ARROW1';
  ok('④b 结果文件头合法（MAT4：类型码 51 + 4x11 Aclass + imagf=0）', is4 || is5 || isArrow,
     `typeCode=${typeCode} mrows=${mrows} ncols=${ncols} imagf=${imagf} name=${JSON.stringify(name)}`);
  console.log(`     结果文件: ${matPath} (${matSize} 字节, 取自 VFS)` +
              `${is4 ? ' [MAT4 ✓]' : is5 ? ' [MAT5]' : isArrow ? ' [ARROW1]' : ' [格式未知]'}`);
  // ★ 落盘一份到宿主（供需求 D 的 Octave 握手用；也让"产物"可被人肉眼查）
  const OUT = process.env.OMC_RESULT_DUMP || '/tmp/omc-BouncingBall_res.mat';
  try {
    const { writeFileSync } = await import('node:fs');
    writeFileSync(OUT, Buffer.from(matBytes));
    console.log(`     ↳ 已落盘宿主: ${OUT}`);
  } catch (e) { console.log(`     (落盘宿主失败，不影响判据: ${String(e).slice(0,80)})`); }
}

// ⑤ 反向断言：坏模型必须报错
let badErrored = false;
try {
  omc.wasi_write_file('/tmp/Bad.mo', enc.encode('model Bad\n  Real x = ;\nequation\n  der(x)=1;\nend Bad;\n'));
  omc.omc_eval('loadFile("/tmp/Bad.mo")');
  const t = omc.omc_eval('translateModel(Bad)');
  const e = String(omc.omc_eval('getErrorString()'));
  badErrored = !truthy(t) || e.length > 2;
} catch { badErrored = true; }
ok('★⑤ 反向：坏模型 ⇒ 必须报错（判据不是恒真）', badErrored);

console.log(`\n=== NODE-SIMULATE ${pass} PASS / ${fail} FAIL ===`);
process.exit(fail ? 1 : 0);
