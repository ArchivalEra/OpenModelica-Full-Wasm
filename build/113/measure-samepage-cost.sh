#!/usr/bin/env bash
# OpenModelica-Full-Wasm — **同页成本测量**（悬案 04 / 需求 D4 的结算件）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# 量什么：两个引擎档"同时放进一个页面"的**体积**与**内存峰值**（要么量到、要么明说缺件）。
#   · 体积：直接读文件（OM 产物 + Octave 产物），不需要浏览器；
#   · 内存峰值：起真 chromium，把**两个模块都实例化**（fetch + WebAssembly.instantiate），
#     记录 `performance.memory.usedJSHeapSize` 与两模块 `WebAssembly.Memory.prototype.buffer`
#     的字节数 —— 这是"同页"最接近真实的可观测量（不承诺等于整页 RSS）。
#
# ★ 只读姊妹仓：Octave 产物与站点都只读（用户点令：不许改本仓以外任何仓库的文件）。
#
# 用法：bash build/113/measure-samepage-cost.sh [--octave-url URL] [--out FILE]
# 退出码：0 = 量到了（写 JSON）；1 = 量不到（缺产物，点名）；2 = 环境（无 node/chromium/harness）
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BASE="${OMC_BASE:-/mnt/hdd/openmodelica-wasm-build}"
OM_WEB="$BASE/build/omc-out-wasm32/web"
OM_WASM="$OM_WEB/pkg-nodejs/OpenModelicaCompiler_bg.wasm"
OCT_URL="${OCT_URL:-http://127.0.0.1:8761/}"
OUT="${OUT:-$BASE/build/omc-out-wasm32/artifacts/samepage-cost.json}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"

log() { printf '%s\n' "$*"; }

# ── 纯逻辑（自证走这里）──────────────────────────────────────────────────────
verdict_of() {  # $1=OM 字节 $2=Octave 字节 $3=峰值JS堆字节 → ok / 说明
  [ "${1:-0}" -gt 0 ] || { echo "缺 OM 产物字节（零值守卫：空输入不是通过）"; return; }
  [ "${2:-0}" -gt 0 ] || { echo "缺 Octave 产物字节"; return; }
  [ "${3:-0}" -gt 0 ] || { echo "没量到内存峰值（0 ⇒ 不是通过）"; return; }
  echo ok
}
selftest() {
  bad=0; n=0
  t() { n=$((n+1)); if [ "$2" = "$3" ]; then echo "PASS | $1"; else echo "fail | $1（期望 '$3' 实得 '$2'）"; bad=$((bad+1)); fi; }
  t "正常：三项都非零 ⇒ ok"                 "$(verdict_of 91152188 29632229 250000000)" "ok"
  t "★ 反向：OM 字节为 0 ⇒ 必须报（零值守卫）" "$(verdict_of 0 29632229 250000000 | grep -c '缺 OM')" "1"
  t "★ 反向：Octave 字节为 0 ⇒ 必须报"        "$(verdict_of 91152188 0 250000000 | grep -c '缺 Octave')" "1"
  t "★ 反向：内存峰值 0 ⇒ 必须报（不许拿 0 当量到）" "$(verdict_of 91152188 29632229 0 | grep -c '没量到')" "1"
  t "★ 空输入 ⇒ 必须报"                      "$(verdict_of '' '' '' | grep -c '缺 OM')" "1"
  echo "=== measure-samepage-cost 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}
case "${1:-}" in --selftest) selftest; exit $? ;; esac
while [ $# -gt 0 ]; do
  case "$1" in
    --octave-url) OCT_URL="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    *) log "未知参数 $1"; exit 2 ;;
  esac
done

# ① 体积（不需要浏览器）
OM_BYTES=0; [ -f "$OM_WASM" ] && OM_BYTES="$(stat -c%s "$OM_WASM")"
OCT_BYTES=0
OCT_SHA=""
OCT_LOCAL="$(ls /mnt/hdd/octave-wasm-build/site/octave.wasm 2>/dev/null | head -1)"
if [ -n "$OCT_LOCAL" ] && [ -f "$OCT_LOCAL" ]; then
  OCT_BYTES="$(stat -c%s "$OCT_LOCAL")"
else
  # 退路：从站点 HTTP 头读 content-length（只读）
  CL="$(timeout 15 curl -sI "$OCT_URL/octave.wasm" 2>/dev/null | tr -d '\r' | awk 'tolower($1)=="content-length:"{print $2}')"
  [ -n "$CL" ] && OCT_BYTES="$CL"
fi
log "== 体积 =="
log "   OM     : $OM_BYTES 字节（$OM_WASM）"
log "   Octave : $OCT_BYTES 字节（${OCT_LOCAL:-$OCT_URL/octave.wasm}）"

# ② 内存峰值（真 chromium，两个模块都实例化）
[ -d "$H/node_modules/playwright-core" ] || { log "FATAL: 环境：harness 缺 playwright-core（$H）"; exit 2; }
command -v node >/dev/null || { log "FATAL: 环境：缺 node"; exit 2; }
PEAK=0
RUNF="$H/_omc-samepage.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cat > "$RUNF" <<'JS'
import { chromium } from 'playwright-core';
import { readFileSync } from 'node:fs';
const [OMWASM, OCTURL] = process.argv.slice(2);
const OCT_LOCAL = process.env.OCT_LOCAL || '/mnt/hdd/octave-wasm-build/site/octave.wasm';

// ★ 量的顺序很重要（2026-10-14 实测）：**先小后大**。
//   先 compile Octave（29.6MB）再 compile OM（91MB）会一路量到；反过来一次就
//   `Target page closed`（整页崩，连前面的读数都拿不回来）。⇒ 每一步都**单独上报**，
//   崩了也能知道"崩在哪一步、之前量到了什么"。
const steps = [
  { name: 'octave', bytes: readFileSync(OCT_LOCAL).toString('base64') },
  { name: 'om',     bytes: readFileSync(OMWASM).toString('base64') },
];

const browser = await chromium.launch({ executablePath: '/usr/bin/chromium',
  args: ['--no-proxy-server','--no-sandbox','--disable-dev-shm-usage','--js-flags=--expose-gc'] });
const out = { peak: 0, steps: [], notes: [] };

for (const st of steps) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  try {
    await page.goto('about:blank');
    const r = await page.evaluate(async (b64) => {
      const jsh = () => (performance.memory ? performance.memory.usedJSHeapSize : 0);
      const before = jsh();
      const arr = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      const mid = jsh();
      const m = await WebAssembly.compile(arr);      // 只编译，不实例化
      const after = jsh();
      // 模块字节在 JS 侧的副本也要算（那是同页成本的一部分）
      return { ok: true, bytes: arr.length, before, mid, after, modExports: WebAssembly.Module.exports(m).length };
    }, st.bytes);
    out.steps.push({ name: st.name, ...r });
    out.peak = Math.max(out.peak, r.after || 0, r.mid || 0);
  } catch (e) {
    // 崩了：如实记（这正是"同页成本"的答案之一），不算隐藏失败
    out.steps.push({ name: st.name, ok: false, error: String(e).slice(0, 200) });
    out.notes.push(`${st.name}: ${String(e).slice(0, 160)}`);
    try { await ctx.close(); } catch {}
    break;   // 崩了就停（后面的不可靠）
  }
  try { await ctx.close(); } catch {}
}
console.log('SAME_PAGE_JSON ' + JSON.stringify(out));
await browser.close();
JS
RAW="$(cd "$H" && OCT_LOCAL="${OCT_LOCAL:-}" timeout 400 node "$RUNF" "$OM_WASM" "$OCT_URL" 2>&1 | grep -o 'SAME_PAGE_JSON .*' | head -1)"
if [ -n "$RAW" ]; then
  PEAK="$(printf '%s' "$RAW" | sed 's/^SAME_PAGE_JSON //' | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    print(0); raise SystemExit
v=[s.get("after",0) or 0 for s in d.get("steps",[]) if s.get("ok")]
v.append(d.get("peak",0) or 0)
print(max(v) if v else 0)' 2>/dev/null)"
fi
log "== 内存峰值（两模块 compile 后 usedJSHeapSize 峰值）=="
log "   peak = ${PEAK:-0} 字节"
[ -n "$RAW" ] && log "   原始: $(printf '%s' "$RAW" | sed 's/^SAME_PAGE_JSON //' | head -c 400)"

V="$(verdict_of "$OM_BYTES" "$OCT_BYTES" "${PEAK:-0}")"
if [ "$V" != ok ]; then log "量不到：$V"; exit 1; fi

mkdir -p "$(dirname "$OUT")"
python3 - "$OUT" "$OM_BYTES" "$OCT_BYTES" "$PEAK" "$RAW" <<'PY'
import json, sys, datetime
out, om, oct_, peak, raw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
d = {
  "schema": 1,
  "when": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
  "om_wasm_bytes": om,
  "octave_wasm_bytes": oct_,
  "js_heap_peak_bytes": peak,
  "sum_wasm_bytes": om + oct_,
  "note": ("体积 = 磁盘真实字节；内存 = 两模块 WebAssembly.compile 后 "
           "performance.memory.usedJSHeapSize 峰值（chromium, about:blank，**不含**页面/站点资源）。"
           "这不是整页 RSS，判读时别超范围引用。"),
  "raw": raw,
}
open(out, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
print(f"写出 {out}")
PY
log "== 同页成本 =="
log "   wasm 合计 : $(( OM_BYTES + ${OCT_BYTES:-0} )) 字节"
exit 0
