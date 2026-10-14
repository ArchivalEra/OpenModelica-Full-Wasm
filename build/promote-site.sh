#!/usr/bin/env bash
# OpenModelica-Full-Wasm — **开发站点发布入口**（需求 B；受管辖入口，三件套齐备）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# 职责：把 web 档产物**摊成一个可服务的站点**（+ 本仓自己的页面资产），并带 COOP/COEP 头
#       —— 后者是硬要求：**wasm 多线程/共享内存档没有这两个头会静默落回基础档**
#       （姊妹仓实测教训，本仓 AGENTS.md 也点名了）。
#
# 只发静态文件，**不做任何服务端计算**（纯客户端铁律：omc 恒跑在浏览器 wasm 里）。
#
# 用法：
#   sh build/promote-site.sh --dry-run   # 只打印要做什么
#   sh build/promote-site.sh --verify    # 只核不写（站点与产物一致？）
#   sh build/promote-site.sh --selftest  # 三类用例自证（夹具上证明它会红）
#   sh build/promote-site.sh             # 真发布
#
# 退出码：0 = 成功；1 = 校验失败；2 = 用法；3 = 环境（产物不在）
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${OMC_BASE:-/mnt/hdd/openmodelica-wasm-build}"
WEB="${WEB:-$BASE/build/omc-out-web/web}"
SITE="${SITE:-$BASE/site-omc}"
PORT="${PORT:-8765}"

log() { printf '%s\n' "$*"; }
err() { printf '%s\n' "$*" >&2; }

# ── COI 服务（站点自带的发头脚本；**必须**用它，普通 http.server 发不出那两个头）──
COI="$REPO/build/serve-coi.py"

# ── 三件套自证：证明"该红的会红" ────────────────────────────────────────────
gate_ok() {  # $1=产物目录 $2=站点目录 → ok / 说明（纯函数，自证走这里）
  if [ ! -f "$1/omc/OpenModelicaCompiler.js" ]; then echo "产物缺 omc/OpenModelicaCompiler.js"; return; fi
  if [ ! -f "$1/index.html" ]; then echo "产物缺 index.html（页面没装配上）"; return; fi
  if [ ! -f "$2/index.html" ]; then echo "站点缺 index.html（还没发布？）"; return; fi
  if [ ! -f "$2/omc/OpenModelicaCompiler_bg.wasm" ]; then echo "站点缺 omc/*_bg.wasm"; return; fi
  echo ok
}
selftest() {
  bad=0; n=0
  t() { n=$((n+1)); if [ "$2" = "$3" ]; then echo "PASS | $1"; else echo "fail | $1（期望 '$3' 实得 '$2'）"; bad=$((bad+1)); fi; }
  D="$(mktemp -d)"; mkdir -p "$D/web/omc" "$D/site/omc"
  touch "$D/web/omc/OpenModelicaCompiler.js" "$D/web/index.html" "$D/site/index.html" "$D/site/omc/OpenModelicaCompiler_bg.wasm"
  # ① 正常不报
  t "正常：产物齐 + 站点齐 ⇒ ok" "$(gate_ok "$D/web" "$D/site")" "ok"
  # ② 该报的必须报（每条都是真实失败形状）
  t "★ 产物缺 omc 模块 ⇒ 必须报" "$(rm "$D/web/omc/OpenModelicaCompiler.js"; gate_ok "$D/web" "$D/site" | grep -c '产物缺 omc')" "1"
  touch "$D/web/omc/OpenModelicaCompiler.js"
  t "★ 站点缺 wasm ⇒ 必须报" "$(rm "$D/site/omc/OpenModelicaCompiler_bg.wasm"; gate_ok "$D/web" "$D/site" | grep -c '站点缺 omc')" "1"
  t "★ 产物缺 index.html ⇒ 必须报" "$(rm "$D/web/index.html"; gate_ok "$D/web" "$D/site" | grep -c '产物缺 index')" "1"
  # ③ 空输入必须报
  t "★ 空目录 ⇒ 必须报（零值守卫）" "$(gate_ok "$D/nope" "$D/nope" | grep -c '产物缺')" "1"
  rm -rf "$D"
  echo "=== promote-site 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}

case "${1:-}" in
  --selftest) selftest; exit $? ;;
  --dry-run)
    log "== dry-run =="
    log "  产物 : $WEB"
    log "  站点 : $SITE"
    log "  服务 : python3 $COI $PORT $SITE（带 COOP/COEP）"
    log "  要做的: rsync 产物 → 站点；拷本仓页面资产（bridge/*.js）；写 .build-sha（三层 SHA 的磁盘层）"
    V="$(gate_ok "$WEB" "$SITE")"; [ "$V" = ok ] && log "  ✅ 自查通过" || { log "  （首发布时站点还没建 ⇒ 正常）"; }
    exit 0 ;;
  --verify)
    [ -f "$SITE/.build-sha" ] || { err "FATAL: 站点没有 .build-sha（没发布过？）"; exit 1; }
    WANT="$(sha256sum "$WEB/omc/OpenModelicaCompiler_bg.wasm" 2>/dev/null | cut -d' ' -f1)"
    GOT="$(sha256sum "$SITE/omc/OpenModelicaCompiler_bg.wasm" 2>/dev/null | cut -d' ' -f1)"
    [ -n "$WANT" ] || { err "FATAL: 产物 wasm 不在（$WEB）"; exit 1; }
    if [ "$WANT" != "$GOT" ]; then err "FATAL: 站点 wasm ≠ 产物 wasm（重发布）"; exit 1; fi
    log "  ✅ 站点 == 产物（sha256 ${WANT%"${WANT#????????????????}"}…）"
    exit 0 ;;
  "" ) ;;
  *) err "用法: promote-site.sh [--dry-run|--verify|--selftest]"; exit 2 ;;
esac

# ── 真发布 ─────────────────────────────────────────────────────────────────
[ -f "$WEB/omc/OpenModelicaCompiler.js" ] || { err "FATAL: 环境：web 产物不在 $WEB（先跑 MODE=web-release build/113/build-omc-wasm.sh build）"; exit 3; }
mkdir -p "$SITE"
log "== 发布产物 → $SITE =="
# 用 tar 管道（同步、保留权限、无外部 rsync 依赖）
tar -C "$WEB" -cf - . | tar -xf - -C "$SITE"
log "== 拷本仓页面资产（桥 + 演示页）=="
mkdir -p "$SITE/bridge"
# ★ `.m` 也要拷（需求 B/E/D 的桥接函数是 `.m`！只拷 `*.js` 会让页面 fetch 到 404 的 HTML
#   ⇒ Octave 报 `syntax error near line 1`（实测踩到：同页的 omc_mat_load 加载失败）。
#   —— 这条是"白名单只拷了一半"的同一族错误：**列清单时漏了扩展名**。
for f in "$REPO"/bridge/*.js "$REPO"/bridge/*.m; do
  [ -f "$f" ] && cp "$f" "$SITE/bridge/" && log "   + bridge/$(basename "$f")"
done
for f in "$REPO"/site/*.html "$REPO"/site/*.js "$REPO"/site/*.m; do
  [ -f "$f" ] && cp "$f" "$SITE/" && log "   + $(basename "$f")"
done
# 磁盘层指纹（三层 SHA 的第一层）
sha256sum "$SITE/omc/OpenModelicaCompiler_bg.wasm" | cut -d' ' -f1 > "$SITE/.build-sha"
log "== 站点点位 =="
log "   wasm sha256 = $(cat "$SITE/.build-sha")"
log "   起服务：python3 $COI $PORT $SITE"
V="$(gate_ok "$WEB" "$SITE")"
[ "$V" = ok ] || { err "FATAL: 自查不过：$V"; exit 1; }
log "✅ 发布完成"
