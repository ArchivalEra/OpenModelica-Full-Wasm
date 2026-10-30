#!/bin/sh
# OpenModelica-Full-Wasm — 74 MB ESM 引擎 boot 分布的跑法（宿主 mail/027 §4 / 029 §5）
# SPDX-License-Identifier: AGPL-3.0-or-later
# ★ 只读姊妹仓（拷到它的 harness 跑、跑完删副本），不改它任何文件。
# 用法：sh test/browser/run-measure-omc-boot.sh [URL] [N] [OUT.json]
#   URL 默认 http://127.0.0.1:8761/ ；N 默认 5 ；OUT 默认落在产物目录 artifacts/
# 退出码：0 = 每跑次都 ready；1 = 有失败（失败率 > 0）；2 = 环境
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
URL="${1:-http://127.0.0.1:8761/}"
N="${2:-5}"
OUT="${3:-/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/omc-boot.json}"
[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core（$H）" >&2; exit 2; }
[ -f "$REPO/test/browser/measure-omc-boot.mjs" ] || { echo "FATAL: 测量件不在" >&2; exit 2; }
rm -f "$H"/_omc-boot.*.mjs 2>/dev/null || true
RUNF="$H/_omc-boot.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cp "$REPO/test/browser/measure-omc-boot.mjs" "$RUNF"
# ⚠️ 别写 `exec node`（exec 换掉 shell ⇒ trap 不跑 ⇒ 副本残留）
cd "$H"
node "$RUNF" "$URL" "$N" "$OUT"
rc=$?
exit "$rc"