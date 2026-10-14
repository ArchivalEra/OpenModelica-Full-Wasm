#!/bin/sh
# OpenModelica-Full-Wasm — 同页集成验收（本仓入口；只借 harness 的 node_modules）
# SPDX-License-Identifier: AGPL-3.0-or-later
# ★ 只读姊妹仓：它的运行时文件**已由 promote-site.sh 的 oct/ 供给**（本站点同源）
# 前置：sh build/promote-site.sh && python3 build/serve-coi.py 8765 /mnt/hdd/openmodelica-wasm-build/site-omc
# 用法：sh test/browser/run-samepage.sh [URL]
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
URL="${1:-http://127.0.0.1:8765/samepage.html}"
[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core（$H）" >&2; exit 2; }
[ -f "$REPO/test/browser/accept-samepage.mjs" ] || { echo "FATAL: 套件不在" >&2; exit 2; }
rm -f "$H"/_omc-samepage.*.mjs 2>/dev/null || true
RUNF="$H/_omc-samepage.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cp "$REPO/test/browser/accept-samepage.mjs" "$RUNF"
# ⚠️ 别写 `exec node`（exec 换掉 shell ⇒ trap 不跑 ⇒ 副本残留）
cd "$H"
node "$RUNF" "$URL"
rc=$?
exit "$rc"
