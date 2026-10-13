#!/bin/sh
# OpenModelica-Full-Wasm — Node 侧验收运行器（本仓 2026-10-13；照姊妹仓 test/browser/run.sh 的形状）
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 为什么在仓库里（而不是仓外 harness）：验收**契约**必须在仓库里，否则改完仓库跑的是
# 仓外的老副本，红绿整体错位（姊妹仓实测踩过两次）。本仓的 Node 侧验收**零依赖**
# （只用 node 内建模块，不要 playwright）⇒ 不需要 harness 的 node_modules，
# **从仓库原路径直跑**（照 AGENTS.md 的操作习惯）。
#
# 用法：sh test/node/run.sh <探针.mjs> [参数…]
# 退出码：0 = 全过；1 = 探针红；2 = 用法/环境错
set -e
[ -n "${1:-}" ] || { echo "用法: sh test/node/run.sh <探针.mjs> [参数…]" >&2; exit 2; }
F="$1"; shift
[ -f "$F" ] || { echo "FATAL: 找不到 $F" >&2; exit 2; }
command -v node >/dev/null 2>&1 || { echo "FATAL: 缺 node" >&2; exit 2; }
# 从**仓库原路径**直跑（不 cp 副本）
exec node "$F" "$@"
