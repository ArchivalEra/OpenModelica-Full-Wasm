// OpenModelica-Full-Wasm — Node 侧验收：**模型能不能在 wasm 里跑完并出 .mat**（需求 B）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 判据（悬案 03 的 Settling）：
//   ① 编译器前端：loadFile true + getClassNames 含模型名
//   ② translateModel 真跑（不是只回 true —— 还要模型 wasm 真被写出，用 wasi_path_open 探）
//   ③ 仿真：`omc_simulate(...)` 跑完且 `resultFile` 非空
//   ④ **产物层**：那个 .mat 真存在、非空、前 4 字节是 MAT4/MAT5 魔数（不是空壳也不是错误页）
//   ⑤ 反向断言：坏模型（语法错）⇒ **必须**报错（判据不是恒真）
import { existsSync, statSync } from 'node:fs';
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

// ④ 产物层：.mat 真存在 + 魔数（MAT4 = "MAT4" ASCII；MAT5 = 128 字节头含 "MATLAB 5.0"）
const cand = [resultFile, '/tmp/BouncingBall_res.mat', '/tmp/BouncingBall_res.arrow'].filter(Boolean);
let matPath = cand.find((p) => { try { return statSync(p).isFile() && statSync(p).size > 0; } catch { return false; } });
ok('④a 结果文件在磁盘上且非空', !!matPath, `试过 ${JSON.stringify(cand)}`);
if (matPath) {
  const { readFileSync } = await import('node:fs');
  const head = readFileSync(matPath).subarray(0, 128);
  const is4 = head.subarray(0, 4).toString('latin1') === 'MAT4';
  const is5 = head.subarray(0, 128).toString('latin1').startsWith('MATLAB 5.0 MAT-file');
  const isArrow = head.subarray(0, 6).toString('latin1') === 'ARROW1';
  ok('④b 结果文件头合法（MAT4 / MAT5 / ARROW1）', is4 || is5 || isArrow,
     `head=${JSON.stringify(head.subarray(0, 16).toString('latin1'))}`);
  console.log(`     结果文件: ${matPath} (${statSync(matPath).size} 字节)` +
              `${is4 ? ' [MAT4]' : is5 ? ' [MAT5]' : isArrow ? ' [ARROW1]' : ''}`);
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
