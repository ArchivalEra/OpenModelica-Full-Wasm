#!/bin/sh
# OpenModelica-Full-Wasm — Export FMU 验收跑法（mail/008 缺陷 1 的回归判据）
# SPDX-License-Identifier: AGPL-3.0-or-later
# ★ 只读姊妹仓（拷到它的 harness 跑、跑完删副本），不改它任何文件。
# 前置：站点已发布（sh build/promote-site.sh）且 COI 服务在跑
#   （python3 build/serve-coi.py 8765 /mnt/hdd/openmodelica-wasm-build/site-omc）
# 用法：sh test/browser/run-export-fmu.sh [URL]
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
URL="${1:-http://127.0.0.1:8765/simulator/}"
[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core（$H）" >&2; exit 2; }
[ -f "$REPO/test/browser/accept-export-fmu.mjs" ] || { echo "FATAL: 套件不在" >&2; exit 2; }
rm -f "$H"/_omc-fmu.*.mjs 2>/dev/null || true
RUNF="$H/_omc-fmu.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cp "$REPO/test/browser/accept-export-fmu.mjs" "$RUNF"
# ⚠️ 别写 `exec node`（exec 换掉 shell ⇒ trap 不跑 ⇒ 副本残留）
cd "$H"
node "$RUNF" "$URL"
rc=$?
exit "$rc"
