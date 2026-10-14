#!/bin/sh
# OpenModelica-Full-Wasm — `bridge/omc_mat_load.m` 的自证台（三类用例：正常不报/该报必须报/空输入必须报）
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 为什么必须自证：本仓纪律（每个闸门必须能证明自己会红）。桥接函数是**判据的产地** ——
# 它的错误分支（不是 OM 文件 / dataInfo 越界 / 缺字段）如果永远走不到，那么"load 成功"就
# 只剩"没抛异常"这一种含义了。⇒ 在真 Octave 引擎里跑三类用例。
#
# ★ 只读姊妹仓：套件与夹具都从本仓注入，harness 只借 node_modules。
#
# 用法：sh test/browser/selftest-mat-bridge.sh [URL]
# 退出码：0 = 全过；1 = 有 fail；2 = 环境
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
URL="${1:-http://127.0.0.1:8761/}"
[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core" >&2; exit 2; }

RUNF="$H/_omc-bridge-selftest.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cat > "$RUNF" <<'JS'
import { chromium } from 'playwright-core';
import { readFileSync } from 'node:fs';
const URL = process.argv[2] || 'http://127.0.0.1:8761/';
const REPO = process.env.OMC_REPO || '/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm';
const GOOD = '/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/BouncingBall_res.mat';
const bridge = readFileSync(REPO + '/bridge/omc_mat_load.m', 'utf8');
const good = readFileSync(GOOD);

const browser = await chromium.launch({ executablePath: '/usr/bin/chromium',
  args: ['--no-proxy-server','--no-sandbox','--disable-dev-shm-usage'] });
const page = await (await browser.newContext()).newPage();
const logs = []; page.on('console', m => logs.push(m.text().slice(0,900)));
await page.goto(URL, { waitUntil: 'load', timeout: 240000 });
for (let i=0;i<600;i++){ if (await page.evaluate(()=>window.__octaveReady===true).catch(()=>false)) break; await new Promise(r=>setTimeout(r,300)); }
await new Promise(r=>setTimeout(r,400));
await page.evaluate(([gd, bs]) => {
  const FS = window.Module.FS;
  try { FS.mkdir('/work'); } catch {}
  FS.writeFile('/work/omc_mat_load.m', new TextEncoder().encode(bs));
  FS.writeFile('/work/good.mat', new Uint8Array(gd));
  // 坏件：只有 name（没有 data_2）⇒ 必须被"不是 OM 文件"挡下
  FS.writeFile('/work/nonmat.txt', new TextEncoder().encode('hello not a mat at all'));
}, [Array.from(good), bridge]);

async function ev(code, ms=30000) {
  logs.length = 0; const S='ZZ'+Math.random().toString(36).slice(2)+'ZZ';
  await page.evaluate(([c,s])=>{ try{ return window.Module.eval_string(c+`; printf('%s\\n','${s}');`);}catch(e){return -99;} },[code,S]).catch(()=>-99);
  const t=Date.now(); while(Date.now()-t<ms){ if(logs.some(l=>l.includes(S)))break; await new Promise(r=>setTimeout(r,80)); }
  return { out: logs.join(' ').split(S)[0].replace(/\s+/g,' ').trim(),
           err: String(await page.evaluate(()=>window.Module.last_error_message())).slice(0,240) };
}
let pass=0, fail=0;
const ok=(n,c,d='')=>{ if(c){pass++;console.log('PASS | '+n);} else {fail++;console.log('fail | '+n+(d?' —— '+d:''));} };

// ① 正常不报
let r = await ev(`addpath('/work'); addpath('${REPO}/bridge'); disp(1)`);
r = await ev("[m,~] = omc_mat_load('/work/good.mat'); disp(numel(m.vars)); disp(m.samples); disp(numel(m.renamed)); disp(numel(m.skipped))");
// 期望（**实测定的确数**，不是"看着差不多"）：7 个名字里
//   · `der(h)`/`der(v)` ⇒ 非法字符改名（der_h_/der_v_）
//   · `time`/`e`       ⇒ 撞 Octave **内建**（exist 返回 5：time.cc / data.cc），主动改名
//     （time_2 / e_2 —— 见 bridge 的注释：撞内建必须改名，否则调用会走内建）
//   · 剩余 h/v/g 原名；共 4 个改名、0 跳过。改名逻辑一变这条就红。
ok('① 正常：真结果文件 ⇒ 成功（7 变量 / 628 采样 / 4 个改名 / 0 跳过）',
   /7\s+628\s+4\s+0/.test(r.out), `out=${JSON.stringify(r.out.slice(0,160))} err=${r.err.slice(0,140)}`);

// ①b 消毒后的名字真的存在，且原名与改名都在 meta 里
r = await ev("disp(exist('der_h_','var')); disp(exist('der_v_','var')); disp(exist('e_2','var')); disp(exist('time_2','var')); disp(exist('g','var')); disp(exist('h','var'))");
ok('①b 正常：改名与原名都到位（der_h_/der_v_/e_2/time_2/g/h 均存在）',
   /^1\s+1\s+1\s+1\s+1\s+1$/.test(r.out.trim()), `out=${JSON.stringify(r.out)}`);

// ①c 常量是标量（参数 e=0.7 / g=9.81 走 data_1）—— 这是 dataInfo 语义的证据
// e 被改名成 e_2（撞内建 log/exp 的 e）⇒ 断言用 e_2
r = await ev("disp(e_2); disp(g)");
ok('①c 正常：参数走 data_1 且值对（e_2=0.7, g=9.81）',
   /0\.7/.test(r.out) && /9\.81/.test(r.out), `out=${JSON.stringify(r.out)}`);

// ② 该报的必须报
r = await ev("[m,~] = omc_mat_load('/work/nonmat.txt');");
ok('★② 该报：非 OM 文件 ⇒ 必须报错', /error/i.test(r.out + r.err), `out=${JSON.stringify(r.out.slice(0,140))}`);
r = await ev("[m,~] = omc_mat_load('/work/no-such-file.mat');");
ok('★②b 该报：文件不存在 ⇒ 必须报错', /error/i.test(r.out + r.err), `out=${JSON.stringify(r.out.slice(0,140))}`);
// 造一个 dataInfo 越界的件：挑一个**真的走 channel 2** 的变量，把 index 改成超出行数。
// ⚠️ 取列号别写 `cellstr(s.name')`：在 Octave 里它给的是**列** cell ⇒ `strcmp` 返回空
//    ⇒ `s.dataInfo(2,[])` 什么也没改 ⇒ 测试**假绿**（本自证台第一版就这么假过了）。
//    正确取法：先 grep 名字矩阵的行、再定位到列（下面这样）。
r = await ev("s=load('/work/good.mat'); nm=char(s.name); nmc=cell(1,columns(nm)); for kk=1:columns(nm), r2=nm(:,kk)'; z=find(r2==0,1); if isempty(z), z=numel(r2)+1; end; nmc{kk}=char(r2(1:z-1)); end; k=find(strcmp(nmc,'h')); disp(k); s.dataInfo(2,k)=999; omc_mat_load(s)");
ok('★②c 该报：dataInfo 越界（index 超行数）⇒ 必须报错', /error/i.test(r.out + r.err),
   `out=${JSON.stringify(r.out.slice(0,140))}`);

// ③ 空输入必须报
r = await ev("omc_mat_load('')");
ok('★③ 空输入：空路径 ⇒ 必须报错', /error/i.test(r.out + r.err), `out=${JSON.stringify(r.out.slice(0,140))}`);
r = await ev("omc_mat_load(struct())");
ok('★③b 空输入：空 struct（没有 name/data_2）⇒ 必须报错', /error/i.test(r.out + r.err),
   `out=${JSON.stringify(r.out.slice(0,140))}`);

await browser.close();
console.log(`\n=== MAT-BRIDGE-SELFTEST ${pass} PASS / ${fail} FAIL ===`);
process.exit(fail?1:0);
JS
cd "$H" && exec node "$RUNF" "$URL"
