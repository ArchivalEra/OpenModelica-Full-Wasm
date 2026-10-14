#!/bin/sh
# OpenModelica-Full-Wasm — 需求 D 验收跑法（本仓入口；harness 只在仓外）
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 为什么需要这个包装：套件 `import { chromium } from 'playwright-core'`，而
# playwright-core 只装在姊妹仓的 harness 里（ESM 解析看**脚本所在目录**）。
# 姊妹仓 `test/browser/run.sh` 用的是"每次现拷唯一名副本"的法子 —— 本脚本照同款做，
# **不缓存**（改完仓库用旧副本跑，断言红绿会整体错位，那是实测教训）。
#
# ★ 本脚本**只读**姊妹仓（拷到它的 harness 跑、跑完删副本），不改它任何文件
#   （用户点令：不允许修改本仓库以外其他仓库的文件）。
#
# 用法：sh test/browser/run-mat-handshake.sh [URL] [MAT]
#   默认 URL = http://127.0.0.1:8761/（姊妹仓 Octave 站点；起法见 README/姊妹仓 recover 脚本）
#   默认 MAT = 产物目录里的 OmcHandshakeDemo_res.mat（由 test/node/produce-result-mat.mjs 产出）
# 退出码：0 = 全过；1 = 套件红；2 = 用法/环境（harness 或输入件不在）
set -eu
REPO="${OMC_REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}"
H="${HARNESS:-/mnt/hdd/octave-wasm-build/harness}"
URL="${1:-http://127.0.0.1:8761/}"
MAT="${2:-/mnt/hdd/openmodelica-wasm-build/build/omc-out-wasm32/artifacts/BouncingBall_res.mat}"

[ -d "$H/node_modules/playwright-core" ] || { echo "FATAL: harness 缺 playwright-core（$H）" >&2; exit 2; }
[ -f "$REPO/test/browser/accept-mat-handshake.mjs" ] || { echo "FATAL: 套件不在" >&2; exit 2; }
[ -f "$MAT" ] || { echo "FATAL: 输入 .mat 不在（$MAT）—— 先跑 node test/node/produce-result-mat.mjs" >&2; exit 2; }

# 开跑前清掉**自己**的旧残留（trap 只在正常退出时跑；上游 shell 被取消会留下副本）
rm -f "$H"/_omc-mat-handshake.*.mjs "$H"/_omc-bridge-selftest.*.mjs 2>/dev/null || true
RUNF="$H/_omc-mat-handshake.$$.mjs"
trap 'rm -f "$RUNF"' EXIT INT TERM
cp "$REPO/test/browser/accept-mat-handshake.mjs" "$RUNF"
# ⚠️ 别写 `exec node`：exec 会把 shell 换掉 ⇒ trap 不跑 ⇒ 临时副本留在 harness 里
#    （姊妹仓 run.sh:19 逐字警告过同一件事："不能用 exec node：trap 要能在退出时删掉这次副本"）。
#    实测：本仓第一版就是 exec，跑完留下 _omc-*.mjs 残渣。
cd "$H"
node "$RUNF" "$URL" "$MAT"
rc=$?
exit "$rc"
