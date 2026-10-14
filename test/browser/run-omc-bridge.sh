#!/bin/sh
# OpenModelica-Full-Wasm — 需求 E 验收跑法（本仓入口；harness 只借 node_modules）
# SPDX-License-Identifier: AGPL-3.0-or-later
# ★ 只读姊妹仓（拷到它的 harness 跑、跑完删副本），不改它任何文件。
# 用法：sh test/browser/run-omc-bridge.sh [URL]
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
URL="${1:-http://127.0.0.1:8761/}"
[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core（$H）" >&2; exit 2; }
[ -f "$REPO/test/browser/accept-omc-bridge.mjs" ] || { echo "FATAL: 套件不在" >&2; exit 2; }
# 开跑前清自己的旧残留（trap 只在正常退出时跑；上游 shell 被取消会留下副本）
rm -f "$H"/_omc-bridge.*.mjs 2>/dev/null || true
RUNF="$H/_omc-bridge.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cp "$REPO/test/browser/accept-omc-bridge.mjs" "$RUNF"
# ⚠️ 别写 `exec node`：exec 会把 shell 换掉 ⇒ trap 不跑 ⇒ 副本留在 harness
#    （姊妹仓 run.sh:19 逐字警告过同一件事）
cd "$H"
node "$RUNF" "$URL"
rc=$?
exit "$rc"
