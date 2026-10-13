#!/usr/bin/env bash
# OpenModelica-Full-Wasm — **clang24 的 wasm32 builtins 精编器**（本仓 2026-10-13）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# 为什么需要它（实测出处，不是推测）：
#   · 上游 rust_omc.cmake:297-320 用 `clang -print-resource-dir` 推
#     `lib/<wasi|lib>/libclang_rt.builtins-wasm32.a`，缺 ⇒ configure 期 **FATAL**；
#   · 用户点令改用 **clang 24**（LLVM-wasm 仓的 emsdk 内置，24.0.0git @55ea1f4e）；
#   · Debian 的 libclang-rt-24-dev-wasm32 在 experimental 池且直连 404 ⇒ 走**同源精编**：
#     用这套 clang24 自己编 llvm-project@55ea1f4e 的 compiler-rt builtins（同 commit 最忠实）。
#
# 用法：
#   bash build/113/build-clang24-builtins.sh build        # 编出 .a 并铺进 overlay
#   bash build/113/build-clang24-builtins.sh status       # 读出来验（不猜）
#   bash build/113/build-clang24-builtins.sh --dry-run
#   bash build/113/build-clang24-builtins.sh --selftest   # 三类用例自证
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# clang 24（LLVM-wasm 仓的 emsdk 内置；路径可覆盖）
C24="${C24:-/mnt/hdd/zcode-projects/LLVM-wasm/toolchain/emsdk/upstream/bin/clang}"
LD24="${LD24:-/mnt/hdd/zcode-projects/LLVM-wasm/toolchain/emsdk/upstream/bin/wasm-ld}"
AR24="${AR24:-/mnt/hdd/zcode-projects/LLVM-wasm/toolchain/emsdk/upstream/bin/llvm-ar}"
LLVM_SRC="${LLVM_SRC:-/mnt/hdd/zcode-projects/LLVM-wasm/toolchain/llvm-project}"
TOOLS="${TOOLS:-/mnt/hdd/openmodelica-wasm-build/tools}"
OVERLAY="$TOOLS/clang-resource"          # clang24 的 resource-dir overlay
OUT="${OUT:-$TOOLS/clang-resource/lib/wasi}"
WORK="${WORK:-$TOOLS/builtins-build}"
TARGET="${TARGET:-wasm32-wasip1}"

# ── 纯逻辑（自证走这里）──────────────────────────────────────────────────────
# 从 compiler-rt CMakeLists 抽源表（**读出来，不手抄** —— 手抄会随上游漂）
sources_of() {  # $1=CMakeLists 路径 → 每行一个源文件名（wasm32 用 GENERIC_TF + GENERIC）
  python3 - "$1" <<'PY'
import re, sys
txt = open(sys.argv[1], encoding="utf-8", errors="replace").read()
out = []
for name in ("GENERIC_TF_SOURCES", "GENERIC_SOURCES"):
    m = re.search(r"set\(" + name + r"\s+(.*?)\n\)", txt, re.S)
    if not m:
        continue
    for tok in m.group(1).split():
        if tok.endswith((".c", ".S")):
            out.append(tok)
# ⚠️ 空表必须输出**零字节**：`print("\n".join([]))` 会吐一个空行 ⇒ 下游 `wc -l` 读到 1
#    （自证第五条抓到的形状：空输入冒充"抽到了东西"）
sys.stdout.write("\n".join(out))
if out:
    sys.stdout.write("\n")
PY
}
count_ok() {  # $1=源数 $2=对象数 → ok / 说明
  if [ "${1:-0}" -eq 0 ]; then echo "源表为空（零值守卫：空断言面不是通过）"; return; fi
  if [ "${1:-0}" -ne "${2:-0}" ]; then echo "对象数 ≠ 源数（$2 ≠ $1）—— 有源编失败"; return; fi
  echo ok
}
selftest() {
  bad=0; n=0
  t() { n=$((n+1)); if [ "$2" = "$3" ]; then echo "PASS | $1"; else echo "fail | $1（期望 '$3' 实得 '$2'）"; bad=$((bad+1)); fi; }
  t "正常：源数=对象数 ⇒ ok"                 "$(count_ok 120 120)" "ok"
  t "★ 反向：对象少于源 ⇒ 必须报（有源编失败）" "$(count_ok 120 118 | grep -c '对象数 ≠')" "1"
  t "★ 零值：源表为空 ⇒ 必须报（空断言面）"    "$(count_ok 0 0 | grep -c '源表为空')" "1"
  t "★ 零值：空实测（0 对象 而 源非空）⇒ 必须报" "$(count_ok 120 0 | grep -c '对象数 ≠')" "1"
  # 源表抽取器本身也要能红：喂一个没有源表的文件 ⇒ 必须抽到 0 行
  # ⚠️ 用 `grep -c ''` 数行而不是 `wc -l`：无尾换行的单行输入 `wc -l` 报 1（假绿形状）
  t "★ 抽取器：无源表的文件 ⇒ 必须抽到 0 行"  "$(printf 'x' > /tmp/_no_sources.$$; sources_of /tmp/_no_sources.$$ | grep -c ''; rm -f /tmp/_no_sources.$$)" "0"
  echo "=== build-clang24-builtins 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}
case "${1:-}" in --selftest) selftest; exit $? ;; esac

DRY=0; case "${1:-build}" in --dry-run) DRY=1 ;; build|status) ;; *) echo "用法: build-clang24-builtins.sh build|status|--dry-run|--selftest" >&2; exit 2 ;; esac
step() { if [ "$DRY" = 1 ]; then echo "[dry-run] $*"; else echo "== $*"; fi; }

CM="$LLVM_SRC/compiler-rt/lib/builtins/CMakeLists.txt"
[ -f "$CM" ] || { echo "FATAL: 找不到 $CM" >&2; exit 3; }
[ -x "$C24" ] || { echo "FATAL: clang24 不在 $C24" >&2; exit 3; }

VER="$("$C24" --version | head -1)"
echo "   clang24 = $VER"
echo "   llvm-src = $LLVM_SRC @ $(git -C "$LLVM_SRC" rev-parse --short HEAD 2>/dev/null || echo '(无 git)')"

SRC_LIST="$WORK/sources.txt"
if [ "$DRY" = 1 ]; then
  step "抽源表 → $SRC_LIST（GENERIC_TF_SOURCES + GENERIC_SOURCES）"
  step "编译 $(sources_of "$CM" | wc -l) 个源 → $TARGET 对象"
  step "llvm-ar 打 archive → $OUT/libclang_rt.builtins-wasm32.a"
  echo "[dry-run] 完"; exit 0
fi

mkdir -p "$WORK/obj" "$OUT"
sources_of "$CM" > "$SRC_LIST"
NSRC="$(wc -l < "$SRC_LIST")"
step "编 $NSRC 个 builtins 源（$TARGET）"
cd "$WORK/obj"
NOBJ=0; FAILED=""
while read -r s; do
  [ -n "$s" ] || continue
  o="$WORK/obj/$(basename "${s%.c}").o"
  if "$C24" --target="$TARGET" -O2 -fno-builtin -fvisibility=hidden -c "$LLVM_SRC/compiler-rt/lib/builtins/$s" -o "$o" 2>>"$WORK/err.log"; then
    NOBJ=$((NOBJ+1))
  else
    FAILED="$FAILED $s"
  fi
done < "$SRC_LIST"
V="$(count_ok "$NSRC" "$NOBJ")"
if [ "$V" != ok ]; then
  echo "FATAL: $V" >&2; echo "   失败源:$FAILED" >&2; tail -20 "$WORK/err.log" >&2; exit 1
fi
step "打 archive → $OUT/libclang_rt.builtins-wasm32.a"
rm -f "$OUT/libclang_rt.builtins-wasm32.a"
"$AR24" rcs "$OUT/libclang_rt.builtins-wasm32.a" "$WORK"/obj/*.o || { echo "FATAL: llvm-ar 失败" >&2; exit 1; }
SZ="$(stat -c%s "$OUT/libclang_rt.builtins-wasm32.a")"
echo "   ✅ $OUT/libclang_rt.builtins-wasm32.a（$SZ 字节，$NOBJ/$NSRC 对象）"

if [ "${1:-}" = status ]; then
  echo ""
  echo "生效状态（读出来）："
  echo "  archive = $SZ 字节，$( "$AR24" t "$OUT/libclang_rt.builtins-wasm32.a" | wc -l) 个成员"
  echo "  成员示例：$( "$AR24" t "$OUT/libclang_rt.builtins-wasm32.a" | head -3 | tr '\n' ' ')"
fi
