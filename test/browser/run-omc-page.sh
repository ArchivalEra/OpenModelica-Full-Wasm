#!/bin/sh
# OpenModelica-Full-Wasm — 需求 B 验收跑法（本仓入口；只借 harness 的 node_modules）
# SPDX-License-Identifier: AGPL-3.0-or-later
# ★ 只读姊妹仓（拷到它的 harness 跑、跑完删副本），不改它任何文件。
# 前置：站点已发布（sh build/promote-site.sh）且 COI 服务在跑
#   （python3 build/serve-coi.py 8765 /mnt/hdd/openmodelica-wasm-build/site-omc）
# 用法：sh test/browser/run-omc-page.sh [URL]
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
URL="${1:-http://127.0.0.1:8765/omc-bridge.html}"
[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core（$H）" >&2; exit 2; }
[ -f "$REPO/test/browser/accept-omc-page.mjs" ] || { echo "FATAL: 套件不在" >&2; exit 2; }
rm -f "$H"/_omc-page.*.mjs 2>/dev/null || true
RUNF="$H/_omc-page.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cp "$REPO/test/browser/accept-omc-page.mjs" "$RUNF"
# ⚠️ 别写 `exec node`（exec 换掉 shell ⇒ trap 不跑 ⇒ 副本残留；姊妹仓 run.sh:19 逐字警告过）
cd "$H"
node "$RUNF" "$URL"
rc=$?
exit "$rc"
