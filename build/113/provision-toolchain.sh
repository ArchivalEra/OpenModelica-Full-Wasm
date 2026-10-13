#!/usr/bin/env bash
# OpenModelica-Full-Wasm — **工具链供给**（2026-10-13；用户点令：用 clang 24）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# 形态照姊妹仓 build/113/provision-emsdk.sh：**版本化安装 + 稳定路径 + fail-closed 版本复核
# + 三类用例自证**。本仓工具链 = **clang 24 + Rust nightly + wasm32 builtins**（官方 wasm 目标），
# 不是 emsdk。
#
# 为什么这样装（每条都有实测出处，不猜）：
#   · 上游 rust-toolchain.toml 钉 channel=nightly-2026-05-31 + targets=[wasm32-unknown-unknown,
#     wasm32-wasip1] + rust-src（FMI3 适配器的 -Z build-std 要它）⇒ 照上游原文装。
#   · 上游 rust_omc.cmake:297-320 用 `clang -print-resource-dir` 推
#     `<rd>/lib/wasi/libclang_rt.builtins-wasm32.a`（:303），缺则 **configure FATAL**；
#     同一文件 :375-391 把这个 .a 作为 `-DBUILTINS_LIB=` 传给 wasi-libc 的 CMake，
#     由它拼进 PIC sysroot 的 libc.so ⇒ 是**构建输入**，不是"编译器自己会找"。
#   · 本机无 root ⇒ 从 Debian 包取件不成立（llvm-24 在 experimental 且直连 404 实测）；
#     走**同源精编**：用 clang 24 自己编 llvm-project@55ea1f4e 的 compiler-rt builtins
#     （见 build-clang24-builtins.sh）。
#   · clang 24 来源：LLVM-wasm 仓的 emsdk 内置 clang-24（24.0.0git @55ea1f4e），
#     自包含可执行（实测 ldd 干净、拷出来能跑）⇒ 复制进 $BIN24，不动原仓。
#
# 用法：
#   bash build/113/provision-toolchain.sh install     # 装齐（clang24 + rust nightly + builtins + wrapper）
#   bash build/113/provision-toolchain.sh status      # 现在生效的是什么（读出来，不猜）
#   bash build/113/provision-toolchain.sh --dry-run   # 只打印要做什么
#   bash build/113/provision-toolchain.sh --selftest  # 三类用例自证（不碰真工具链）
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
TOOLS="${TOOLS:-/mnt/hdd/openmodelica-wasm-build/tools}"
DL="${DL:-$TOOLS/dl}"
BIN24="$TOOLS/bin24"                      # clang24 工具本体（复制来，自包含）
OVERLAY="$TOOLS/clang-resource"           # clang24 的 resource-dir overlay（含 builtins）
BIN="$TOOLS/bin"                          # 稳定入口 wrapper（构建系统 PATH 上只看这个）
CHANNEL="${CHANNEL:-nightly-2026-05-31}"
CLANG24_SRC="${CLANG24_SRC:-/mnt/hdd/zcode-projects/LLVM-wasm/toolchain/emsdk/upstream/bin}"

log() { printf '%s\n' "$*"; }

# ── 纯逻辑（自证走这里，不碰真工具链）────────────────────────────────────────
verdict_of() {  # $1=期望版本串 $2=实测版本串 → ok / 不符说明（纯函数）
  # ⚠️ 空期望必须先挡：`case "$2" in *""*)` 空 pattern 匹配一切 ⇒ 会**静默返回 ok**
  #    （自证第三条抓到过这个形状：零值守卫不是装饰。）
  [ -n "${1:-}" ] || { echo "不符（期望为空 —— 零值守卫：空断言面不是通过）"; return; }
  case "${2:-}" in
    *"$1"*) echo ok ;;
    *) echo "不符（期望含 '$1'，实测 '$2'）" ;;
  esac
}
overlay_ok() {  # $1=builtins 存在?(0/1) $2=resource-dir 指向 overlay?(0/1) $3=大版本对?(0/1)
  if [ "${1:-0}" != 1 ]; then echo "缺 libclang_rt.builtins-wasm32.a"; return; fi
  if [ "${2:-0}" != 1 ]; then echo "resource-dir 没指向 overlay（wrapper 没生效？）"; return; fi
  if [ "${3:-0}" != 1 ]; then echo "clang 大版本与 overlay 不匹配（23 的库给 24 用？）"; return; fi
  echo ok
}

selftest() {
  bad=0; n=0
  t() { n=$((n+1)); if [ "$2" = "$3" ]; then echo "PASS | $1"; else echo "fail | $1（期望 '$3' 实得 '$2'）"; bad=$((bad+1)); fi; }
  # ① 正常不报
  t "版本串含期望 ⇒ ok"                     "$(verdict_of 24.0.0 'clang version 24.0.0git (x)')" "ok"
  t "overlay 齐（builtins+指向+大版本对）⇒ ok" "$(overlay_ok 1 1 1)" "ok"
  # ② 该报的必须报（反向：这些正是上游 configure FATAL 的形状）
  t "★ 缺 builtins ⇒ 必须报（上游 configure FATAL 的那个）" "$(overlay_ok 0 1 1 | grep -c '缺 libclang')" "1"
  t "★ resource-dir 没指向 overlay ⇒ 必须报（wrapper 没生效）" "$(overlay_ok 1 0 1 | grep -c '没指向')" "1"
  t "★ clang 大版本与 overlay 不匹配 ⇒ 必须报（23 的库给 24 用）" "$(overlay_ok 1 1 0 | grep -c '大版本')" "1"
  t "★ 版本不符 ⇒ 必须报"                   "$(verdict_of 24.0.0 'clang version 23.1.2 (x)' | grep -c '不符')" "1"
  # ③ 空输入必须报
  t "★ 空期望版本 ⇒ 必然不符（零值守卫）"    "$(verdict_of '' 'clang 24.0.0' | grep -c '不符')" "1"
  t "★ 空实测（读不出来）⇒ 必须报"          "$(verdict_of 24.0.0 '' | grep -c '不符')" "1"
  echo "=== provision-toolchain 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}

case "${1:-}" in --selftest) selftest; exit $? ;; esac

DRY=0
case "${1:-install}" in
  --dry-run) DRY=1 ;;
  install|status) ;;
  *) echo "用法: provision-toolchain.sh install|status|--dry-run|--selftest" >&2; exit 2 ;;
esac
step() { if [ "$DRY" = 1 ]; then log "[dry-run] $*"; else log "== $*"; fi; }

# ── ① clang 24 本体（复制 emsdk 那份自包含的 clang-24）───────────────────────
step "clang 24 → $BIN24"
if [ "$DRY" = 1 ]; then
  log "[dry-run] cp $CLANG24_SRC/{clang-24,wasm-ld,llvm-ar,llvm-ranlib,llvm-objdump} $BIN24/"
else
  mkdir -p "$BIN24"
  for f in clang-24 wasm-ld llvm-ar llvm-ranlib llvm-objdump; do
    [ -x "$BIN24/$f" ] || cp "$CLANG24_SRC/$f" "$BIN24/" || { echo "FATAL: 取不到 $f" >&2; exit 3; }
  done
  GOT="$("$BIN24/clang-24" --version | head -1)"
  V="$(verdict_of 24.0.0 "$GOT")"; [ "$V" = ok ] || { echo "FATAL: clang24 $V" >&2; exit 3; }
  log "   ✅ $GOT"
fi

# ── ② clang24 的 resource-dir overlay（含同源精编的 wasm32 builtins）─────────
step "clang24 resource-dir overlay → $OVERLAY"
if [ "$DRY" = 1 ]; then
  log "[dry-run] 铺 overlay（include/bin/share 软链 ← clang24 -print-resource-dir）"
  log "[dry-run] builtins 由 build-clang24-builtins.sh 精编 → $OVERLAY/lib/wasi/"
else
  # ⚠️ 两次实测踩到的坑，都记在这：
  #  ① 别用 `$BIN24/clang-24 -print-resource-dir`：二进制**复制**出来后它按自身位置推，
  #     返回 `<tools>/lib/clang/24`（不存在）⇒ overlay 铺出**断链** ⇒ 编译期
  #     `stddef.h file not found`（-nostdinc 的 clang 内建头真的找不到）。
  #  ② 用**源** resource-dir（emsdk 那份，含真内建头 include/stddef.h 等）。
  R24="$CLANG24_SRC/../lib/clang/24"
  [ -d "$R24/include" ] || { echo "FATAL: 源 clang24 resource-dir 不在 $R24" >&2; exit 3; }
  rm -f "$OVERLAY/include" "$OVERLAY/bin" "$OVERLAY/share" "$OVERLAY/README.txt"
  mkdir -p "$OVERLAY/lib"
  for d in include bin share; do [ -e "$R24/$d" ] && ln -sfn "$R24/$d" "$OVERLAY/$d"; done
  log "   overlay 软链 → $R24（含内建头：$( [ -e "$OVERLAY/include/stddef.h" ] && echo 'stddef.h ✅' || echo 'stddef.h ❌' )）"
fi

# ── ③ wasm32 builtins（同源精编；见 build-clang24-builtins.sh 的理由）─────────
step "wasm32 builtins → $OVERLAY/lib/wasi/libclang_rt.builtins-wasm32.a"
if [ "$DRY" = 1 ]; then
  log "[dry-run] sh build/113/build-clang24-builtins.sh build"
else
  if [ -s "$OVERLAY/lib/wasi/libclang_rt.builtins-wasm32.a" ]; then
    log "   已有 ⇒ 跳过（$(stat -c%s "$OVERLAY/lib/wasi/libclang_rt.builtins-wasm32.a") 字节）"
  else
    sh "$REPO/build/113/build-clang24-builtins.sh" build || { echo "FATAL: builtins 精编失败" >&2; exit 3; }
  fi
fi

# ── ④ 稳定入口 wrapper（构建系统 PATH 上只见 $BIN —— 同 emsdk 的 /emsdk 思路）──
step "wrapper → $BIN"
if [ "$DRY" = 1 ]; then
  log "[dry-run] 写 $BIN/{clang,clang++,wasm-ld,llvm-ar,llvm-ranlib,llvm-objdump,wasm-objdump}"
else
  mkdir -p "$BIN"
  cat > "$BIN/clang" <<EOF
#!/bin/sh
# OpenModelica-Full-Wasm — clang 24 wrapper：注入本地 resource-dir overlay（含 wasm32 builtins）
# 生成者：build/113/provision-toolchain.sh（别手改；改了就重跑 install）
exec $BIN24/clang-24 -resource-dir=$OVERLAY "\$@"
EOF
  sed 's|clang-24|clang-24|; s|^exec .*|exec '"$BIN24"'/clang-24 -resource-dir='"$OVERLAY"' "$@"|' "$BIN/clang" > "$BIN/clang++"
  chmod +x "$BIN/clang" "$BIN/clang++"
  for t in wasm-ld llvm-ar llvm-ranlib llvm-objdump; do ln -sfn "$BIN24/$t" "$BIN/$t"; done
  [ -x /mnt/hdd/crossbuild-tools/wabt/bin/wasm-objdump ] && \
    ln -sfn /mnt/hdd/crossbuild-tools/wabt/bin/wasm-objdump "$BIN/wasm-objdump"
fi

# ── ⑤ Rust 通道（按上游 rust-toolchain.toml 原文；自动装可省）───────────────
step "Rust $CHANNEL"
if [ "$DRY" = 1 ]; then
  log "[dry-run] rustup toolchain install $CHANNEL --profile minimal --component rustc-codegen-cranelift-preview --component clippy --component rustfmt --component rust-src --target wasm32-unknown-unknown --target wasm32-wasip1"
else
  if rustup run "$CHANNEL" rustc --version >/dev/null 2>&1; then
    log "   已装 ⇒ 跳过（$(rustup run "$CHANNEL" rustc --version)）"
  else
    log "   未装（rust-toolchain.toml 会在 cargo 调用时自动装；本批显式装）"
    # ★ 走代理（2026-10-13 实测：static.rust-lang.org **直连 19 KB/s、经 127.0.0.1:2080 代理
    #   7.5 MB/s** —— 快 380 倍。不用代理装一次要数小时，会让本批"看着像卡死"）。
    #   ⚠️ 代理是**本机事实**，不是所有机器都有 ⇒ 到达不了就回落直连（rustup 自己会重试）。
    RUSTUP_ENV=""
    if timeout 5 curl -s -o /dev/null -x "${DL_PROXY:-http://127.0.0.1:2080}" https://static.rust-lang.org/ 2>/dev/null; then
      RUSTUP_ENV="https_proxy=${DL_PROXY:-http://127.0.0.1:2080} http_proxy=${DL_PROXY:-http://127.0.0.1:2080}"
      log "   走代理 ${DL_PROXY:-http://127.0.0.1:2080}（实测快 380×）"
    else
      log "   ⚠️ 代理不可达 ⇒ 直连（可能很慢）"
    fi
    env $RUSTUP_ENV rustup toolchain install "$CHANNEL" --profile minimal \
      --component rustc-codegen-cranelift-preview --component clippy --component rustfmt --component rust-src \
      --target wasm32-unknown-unknown --target wasm32-wasip1 || { echo "FATAL: rustup 失败" >&2; exit 3; }
  fi
  GOT="$(rustup run "$CHANNEL" rustc --version 2>&1)"
  V="$(verdict_of 1.98.0-nightly "$GOT")"; [ "$V" = ok ] || log "   ⚠️ $V（通道已解析出别的版本？）"
  for t in wasm32-unknown-unknown wasm32-wasip1; do
    rustup target list --installed --toolchain "$CHANNEL" | grep -qx "$t" || {
      echo "FATAL: $CHANNEL 缺 target $t" >&2; exit 3; }
  done
fi

# ── ⑥ status：把"现在生效的是什么"**读出来**（不是复述参数）──────────────────
if [ "${1:-}" = status ]; then
  log ""
  log "生效状态（读出来）："
  log "  clang          = $("$BIN/clang" --version 2>/dev/null | head -1)"
  RES="$("$BIN/clang" -print-resource-dir 2>/dev/null || echo '(跑不通)')"
  log "  resource-dir   = $RES"
  [ "$RES" = "$OVERLAY" ] && log "  ✅ 指向 overlay" || log "  ❌ 没指向 overlay"
  B="$OVERLAY/lib/wasi/libclang_rt.builtins-wasm32.a"
  [ -s "$B" ] && log "  ✅ builtins $(( $(stat -c%s "$B") )) 字节" || log "  ❌ 缺 builtins"
  # wasm32 两大目标实编 + 实链（含需要 builtins 的 __udivti3 用例）
  T="$(mktemp -d)"
  printf 'int f(int x){return x;}\n' > "$T/a.c"
  # ★ 内建头断言（2026-10-13 实测踩过：overlay 断链 ⇒ `stddef.h file not found`,
  #   在 wasi-libc 交叉编时才炸，离根因很远）。这条把它拉到眼前。
  printf '#include <stddef.h>\n#include <stdarg.h>\nsize_t h(void){return sizeof(int);}\n' > "$T/hdr.c"
  if "$BIN/clang" --target=wasm32-wasip1 -c "$T/hdr.c" -o "$T/h.o" 2>/dev/null; then
    log "  ✅ 内建头（stddef.h/stdarg.h 找得到）"
  else
    log "  ❌ 内建头找不到 —— overlay at $OVERLAY 的 include 链断了？"
  fi
  printf 'unsigned __int128 g(unsigned __int128 a){return a/3;}\n' > "$T/need.c"
  for tgt in wasm32-unknown-unknown wasm32-wasip1; do
    "$BIN/clang" --target=$tgt -c "$T/a.c" -o "$T/a.o" 2>/dev/null \
      && log "  ✅ 实编 $tgt" || log "  ❌ 实编 $tgt 失败"
  done
  # ① builtins 的**真断言**：用一个需要 builtins 的源（128 位除法 → __udivti3），
  #    -nostdlib 只链 builtins 归档 ⇒ 通了就证明"这个 .a 真能被 clang 24 用"。
  #    ⚠️ 别指望 clang 自己去 `<rd>/lib/wasi/` 找它：上游是把路径当 `-DBUILTINS_LIB=`
  #    传给 wasi-libc 的 CMake（rust_omc.cmake:375-391），**不是**靠编译器默认搜索。
  #    （本脚本第一版就是错在这：期望值写成了"系统里有 wasi sysroot"，于是恒红。）
  "$BIN/clang" --target=wasm32-wasip1 -nostdlib -Wl,--no-entry -Wl,--export-all \
      "$OVERLAY/lib/wasi/libclang_rt.builtins-wasm32.a" "$T/need.c" -o "$T/n.wasm" 2>/dev/null \
    && log "  ✅ builtins 实链（__udivti3 解得开 ⇒ 这个 .a 真能用）" || log "  ❌ builtins 实链失败"
  [ -f "$T/n.wasm" ] && "$BIN/wasm-objdump" -h "$T/n.wasm" >/dev/null 2>&1 && log "  ✅ wasm-objdump 可读产物"
  rm -rf "$T"
  log "  rust           = $(rustup run "$CHANNEL" rustc --version 2>&1 | head -1)"
  log "  targets        = $(rustup target list --installed --toolchain "$CHANNEL" 2>/dev/null | grep wasm | tr '\n' ' ')"
fi
log "工具链供给完成（TOOLS=$TOOLS）"
