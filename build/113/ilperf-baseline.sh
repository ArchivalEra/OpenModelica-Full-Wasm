#!/usr/bin/env bash
# OpenModelica-Full-Wasm — **性能线基线测量与档身份**（判据先行）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# ⚠️ **线的状态（2026-10-14 用户点令）**：原 `IllegalPerformance` 线**已删除**
#   （本地 + 远端）—— 性能线只有在 wasm64 做到生产级后才是"脱离官方树的开发"。
#   **本脚本保留为资产**：它量的是**当前产物**的档身份与已在的加速面，
#   是"重建该线"时 A/B 差分门的**基线**（重建前不必重写测量法）。
#
# 用途：把"性能线要对比的**基线**"量成**可复跑的数**（不是感觉）。
#   —— 姊妹仓 §5 的纪律：任何"更快"的分支都要有 **A/B 差分门**（同旗标 + 变异自证），
#      否则你量的是"改了之后"而不是"因为改了"；**负判决也是资产**。
#
# 这一步**只量基线、不改任何产物**：给出
#   ① 产物档身份（架构 / memory 是导入还是导出 / post-MVP feature 集）
#   ② 已在产物里的加速面（SIMD 指令数、bulk-memory 类指令数）
#   ③ 编译期与运行期的**起点数**（同页编译耗时从验收件读；这里量产物体积/指令面）
#
# 用法：
#   bash build/113/ilperf-baseline.sh            # 量并打印
#   bash build/113/ilperf-baseline.sh --json     # 只打一行 JSON（供台账读）
#   bash build/113/ilperf-baseline.sh --selftest # 三类用例自证
# 退出码：0 = 量到；1 = 量不到（缺产物，点名）；2 = 用法；3 = 环境（工具缺）
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BASE="${OMC_BASE:-/mnt/hdd/openmodelica-wasm-build}"
WASM="${WASM:-$BASE/build/omc-out-web/web/omc/OpenModelicaCompiler_bg.wasm}"
OBJDUMP="${OBJDUMP:-/mnt/hdd/crossbuild-tools/wabt/bin/wasm-objdump}"

# ── 纯逻辑（自证走这里）──────────────────────────────────────────────────────
verdict_of() {  # $1=字节 $2=指令面命中数 → ok / 说明
  [ "${1:-0}" -gt 0 ] || { echo "缺产物字节（零值守卫：空输入不是通过）"; return; }
  [ "${2:-0}" -gt 0 ] || { echo "指令面为 0（工具没读到？不许当'没有 SIMD'用）"; return; }
  echo ok
}
selftest() {
  bad=0; n=0
  t() { n=$((n+1)); if [ "$2" = "$3" ]; then echo "PASS | $1"; else echo "fail | $1（期望 '$3' 实得 '$2'）"; bad=$((bad+1)); fi; }
  # ① 正常不报
  t "正常：字节与指令面都非零 ⇒ ok" "$(verdict_of 74579521 5876)" "ok"
  # ② 该报的必须报
  t "★ 反向：无产物字节 ⇒ 必须报" "$(verdict_of 0 5876 | grep -c '缺产物字节')" "1"
  t "★ 反向：指令面 0 ⇒ 必须报（工具没读到 ≠ 没有 SIMD）" "$(verdict_of 74579521 0 | grep -c '指令面为 0')" "1"
  # ③ 空输入必须报
  t "★ 空输入 ⇒ 必须报" "$(verdict_of '' '' | grep -c '缺产物字节')" "1"
  echo "=== ilperf-baseline 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}
case "${1:-}" in --selftest) selftest; exit $? ;; --json|"") ;; *) echo "用法: ilperf-baseline.sh [--json|--selftest]" >&2; exit 2 ;; esac
JSON=0; [ "${1:-}" = "--json" ] && JSON=1

[ -f "$WASM" ] || { echo "FATAL: 产物不在 $WASM（先跑 MODE=web-release build/113/build-omc-wasm.sh build）" >&2; exit 1; }
[ -x "$OBJDUMP" ] || { echo "FATAL: 环境：缺 wasm-objdump（$OBJDUMP）" >&2; exit 3; }

BYTES="$(stat -c%s "$WASM")"
SHA="$(sha256sum "$WASM" | cut -d' ' -f1)"
SIMD="$(   "$OBJDUMP" -d "$WASM" 2>/dev/null | grep -cE 'v128\.|i32x4\.|f64x2\.|i8x16\.|f32x4\.' || true)"
POSTMVP="$("$OBJDUMP" -d "$WASM" 2>/dev/null | grep -coE 'memory\.copy|memory\.fill|i32\.trunc_sat|i64\.trunc_sat' || true)"
FEATS="$(  "$OBJDUMP" -x "$WASM" 2>/dev/null | sed -n '/target_features/,/^$/p' | grep -oE '\[\+\] [a-z0-9-]+' | sed 's/\[+\] //' | sort | tr '\n' ',' | sed 's/,$//')"
MEMSHAPE="$(node -e "
const fs=require('fs');const m=new WebAssembly.Module(fs.readFileSync(process.argv[1]));
const i=WebAssembly.Module.imports(m).filter(x=>x.kind==='memory').length;
const e=WebAssembly.Module.exports(m).filter(x=>x.kind==='memory').length;
console.log(i+'/'+e);" "$WASM" 2>/dev/null || echo "?/?")"

V="$(verdict_of "$BYTES" "${SIMD:-0}")"
[ "$V" = ok ] || { echo "量不到：$V" >&2; exit 1; }

if [ "$JSON" = 1 ]; then
  printf '{"schema":1,"lane":"perf-baseline","wasm":"%s","bytes":%s,"sha256":"%s","simd_ops":%s,"postmvp_ops":%s,"features":"%s","memory_import_export":"%s"}\n' \
    "$WASM" "$BYTES" "$SHA" "${SIMD:-0}" "${POSTMVP:-0}" "$FEATS" "$MEMSHAPE"
else
  echo "== 性能线基线（只读，不改产物；原 IP 线已删，本件留作重建基线）=="
  echo "   产物        : $WASM"
  echo "   字节        : $BYTES"
  echo "   sha256      : ${SHA%"${SHA#????????????????}"}…"
  echo "   SIMD 指令   : ${SIMD:-0}    ← 已在（上游注释：rustc/LLVM 默认开 simd128）"
  echo "   post-MVP 指令: ${POSTMVP:-0}（bulk-memory / trunc_sat 之类）"
  echo "   features    : $FEATS"
  echo "   memory 导入/导出: $MEMSHAPE   （0/1 = wasm32 宿主导出 memory）"
  echo
  echo "⇒ 本线**已有**的加速面：SIMD + bulk-memory（不是待做项）。"
  echo "   待做的性能候选按姊妹仓 §5 的封口清单：换分配器 / 换 BLAS / libm（负判决）/ 热点定位。"
fi
