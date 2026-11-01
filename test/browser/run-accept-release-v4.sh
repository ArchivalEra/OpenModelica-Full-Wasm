#!/bin/sh
# OpenModelica-Full-Wasm — v4 release 端到端验的跑法
# SPDX-License-Identifier: AGPL-3.0-or-later
# ★ 只读姊妹仓（拷到它的 harness 跑、跑完删副本），不改它任何文件。
# 用法：sh test/browser/run-accept-release-v4.sh <BASE_URL> [codec] [并发] [源产物目录]
#   codec 默认 identity（最严格：逐字节就是原文）；另可 zstd / gzip
#   BASE_URL 指一个已发布（或本地铺好的）release 目录，里面必须有 manifest.json
# 退出码：0 = 全过；1 = 有红；2 = 环境
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
BASE="${1:?用法: run-accept-release-v4.sh <BASE_URL> [codec] [并发] [源目录]}"
CODEC="${2:-identity}"
CONC="${3:-8}"
SRC="${4:-}"
[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core（$H）" >&2; exit 2; }
[ -f "$REPO/test/browser/accept-release-v4.mjs" ] || { echo "FATAL: 套件不在" >&2; exit 2; }
rm -f "$H"/_v4acc.*.mjs 2>/dev/null || true
RUNF="$H/_v4acc.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cp "$REPO/test/browser/accept-release-v4.mjs" "$RUNF"
# ⚠️ 别写 `exec node`（exec 换掉 shell ⇒ trap 不跑 ⇒ 副本残留）
cd "$H"
node "$RUNF" "$BASE" "$CODEC" "$CONC" "$SRC"
rc=$?
exit "$rc"
