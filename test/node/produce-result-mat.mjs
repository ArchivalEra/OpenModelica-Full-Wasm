// 产出一份「OM 仿真结果 .mat」到本仓产物目录（需求 D 的输入件；可复跑）
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// 为什么要有它：需求 D 要的是"OM 档的 `*_res.mat` 喂进 Octave"。那份 .mat 必须
// **可复跑地产出**（而不是某个 /tmp 里手搓的临时文件）—— 否则套件换机器就跑不了。
//
// 用法：node test/node/produce-result-mat.mjs [产物目录] [输出目录]
//   默认产物目录 = /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web
//   默认输出目录 = /mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts
// 退出码：0 = 真产出（文件非空 + MAT4 头形状对）；1 = 失败；2 = 环境（产物不在）
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const WEB = process.argv[2] || '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/web';
const OUTDIR = process.argv[3] || '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts';
const MODEL = `/tmp/BouncingBall.mo`;
const MODEL_SRC = `model BouncingBall
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

if (!existsSync(join(WEB, 'omc-cli.js'))) {
  console.error(`FATAL: 产物不在 ${WEB}（先跑 build/113/build-omc-wasm.sh build）`);
  process.exit(2);
}
const require = createRequire(import.meta.url);
const omc = require(join(WEB, 'pkg-nodejs', 'OpenModelicaCompiler.js'));
omc.omc_set_env('OPENMODELICAHOME', '/usr');
omc.omc_init();
omc.omc_set_inwasm_driver(1);
const enc = new TextEncoder();
omc.wasi_write_file(MODEL, enc.encode(MODEL_SRC));
omc.omc_eval('cd("/tmp")');
// ⚠️ omc_eval 的返回值是**字符串**（实测 `"true"` / `"false"` 带引号，见需求 B 的教训）
const truthy = (v) => /^"?true"?$/.test(String(v).trim());
const loaded = omc.omc_eval(`loadFile("${MODEL}")`);
if (!truthy(loaded)) {
  console.error(`FATAL: loadFile 返回 ${JSON.stringify(String(loaded))}；err=${omc.omc_eval('getErrorString()')}`);
  process.exit(1);
}
const simOut = String(omc.omc_simulate('BouncingBall', 3.0, 500, 1e-6, 'dassl', ''));
const m = simOut.match(/resultFile\s*=\s*"([^"]*)"/);
const vfsPath = m ? m[1] : '';
if (!vfsPath) { console.error('FATAL: 没拿到 resultFile：' + simOut.slice(0, 400)); process.exit(1); }

// 从 wasm VFS 取件（协议照产物 .d.ts：wasi_path_open → fd；wasi_fd_read → Uint8Array）
const fd = omc.wasi_path_open(vfsPath);
if (!(typeof fd === 'number' && fd >= 0)) { console.error('FATAL: VFS 里打不开 ' + vfsPath); process.exit(1); }
let bytes;
try { bytes = omc.wasi_fd_read(fd); } finally { omc.wasi_fd_close(fd); }
if (!bytes || bytes.length === 0) { console.error('FATAL: VFS 读出 0 字节'); process.exit(1); }

// 判据：MAT4 首矩阵 = Aclass（类型码 51 + 4x11 + imagf=0）
const b = Buffer.from(bytes);
const ty = b.readUInt32LE(0), mr = b.readUInt32LE(4), nc = b.readUInt32LE(8), im = b.readUInt32LE(12);
const ok4 = ty === 51 && mr === 4 && nc === 11 && im === 0 && b.subarray(20, 26).toString('latin1') === 'Aclass';
if (!ok4) { console.error(`FATAL: 不是预期的 MAT4 形状（ty=${ty} ${mr}x${nc} imagf=${im}）`); process.exit(1); }

mkdirSync(OUTDIR, { recursive: true });
// 名字逐字对上需求书 D2 点名的 `BouncingBall_res.mat`
const outPath = join(OUTDIR, 'BouncingBall_res.mat');
writeFileSync(outPath, b);
console.log(`${outPath} (${b.length} 字节, MAT4)  ← 复跑：node test/node/produce-result-mat.mjs`);
