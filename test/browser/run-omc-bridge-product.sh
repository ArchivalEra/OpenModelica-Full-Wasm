#!/bin/sh
# OpenModelica-Full-Wasm — E 线桥「产品态」验收跑法（零注入；mail/107 §4 第 3 问）
# SPDX-License-Identifier: AGPL-3.0-or-later
# ★ 只读姊妹仓（拷到它的 harness 跑、跑完删副本），不改它任何文件。
# 前置：**宿主已把 bridge/ 铺进 Octave 站点**（docs/BRIDGE-DELIVERY.md §2）
# 用法：sh test/browser/run-omc-bridge-product.sh [URL]（默认 8761 = 姊妹仓站点）
# 退出码：0 = 产品态跑通；1 = 装配没做对（判据红）；2 = 环境
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
URL="${1:-http://127.0.0.1:8761/}"
[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core（$H）" >&2; exit 2; }
[ -f "$REPO/test/browser/accept-omc-bridge-product.mjs" ] || { echo "FATAL: 套件不在" >&2; exit 2; }
rm -f "$H"/_omc-prod.*.mjs 2>/dev/null || true
RUNF="$H/_omc-prod.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cp "$REPO/test/browser/accept-omc-bridge-product.mjs" "$RUNF"
# ⚠️ 别写 `exec node`（exec 换掉 shell ⇒ trap 不跑 ⇒ 副本残留）
cd "$H"
node "$RUNF" "$URL"
rc=$?
exit "$rc"
