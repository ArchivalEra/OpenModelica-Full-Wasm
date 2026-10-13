#!/usr/bin/env bash
# OpenModelica-Full-Wasm — **wasm64 上游支持探针**（悬案 02 的结算件）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# 断言：「上游 OpenModelica 的 wasm 目标面**有没有** wasm64 / memory64 支持」。
# 为什么需要它：需求书 C1 写「master 线 → 产物 wasm64」，而 2026-10-13 实测上游**零支持**
# ⇒ 这不是"我们没做"，是"上游没有"。这条悬案的结案条件必须是**可复跑的探测**：
# 上游哪天加了支持，这个脚本就翻面（rc 0），悬案即可结。
#
# 判据（stdout 裸值）：
#   `ok: 上游已有 wasm64 支持（N 处命中）`   ⇒ rc=0（**结案**：master 线可以开始出 wasm64）
#   `NOT-YET: 上游仍无 wasm64 支持（N 处命中）` ⇒ rc=1（悬案继续；这不是失败，是"还没到"）
#   `SKIP: 上游树不在 …`                      ⇒ rc=3（环境问题，不是结论）
#
# 用法：bash build/113/check-wasm64-upstream.sh [--upstream <树路径>] [--selftest]
#
# ⚠️ 探测口径（读出来，不猜）：只看**承载 wasm 目标的那个文件**（rust_omc.cmake）
#    与 Rust 工作区配置（Cargo.toml / .cargo/config.toml / rust-toolchain.toml），
#    外加全树 `memory64` 的**肯定用法**（`memory64: true` / `-mmemory64` / `wasm64-` triple）。
#    为什么排掉裸 `wasm64`：emsdk 的 sysroot 目录名里有 wasm64-emscripten，属噪音。
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
UPSTREAM="${UPSTREAM:-/mnt/hdd/openmodelica-wasm-build/build/upstream/openmodelica}"

# 纯函数：$1=命中数 $2=树在?(1/0) → 裸值（**定义必须在 selftest 之前**：shell 顺序执行）
verdict_of() {
  if [ "${2:-0}" != 1 ]; then echo "SKIP: 上游树不在（环境问题不是结论）"; return; fi
  if [ "${1:-0}" -gt 0 ]; then echo "ok: 上游已有 wasm64 支持（$1 处命中）"; else echo "NOT-YET: 上游仍无 wasm64 支持（0 处命中）"; fi
}

selftest() {
  bad=0; n=0
  t() { n=$((n+1)); if [ "$2" = "$3" ]; then echo "PASS | $1"; else echo "fail | $1（期望 '$3' 实得 '$2'）"; bad=$((bad+1)); fi; }
  # ① 正常：有支持 ⇒ 裸值 ok、rc 0
  t "有支持 ⇒ 判为 ok"                       "$(verdict_of 3 1)" "ok: 上游已有 wasm64 支持（3 处命中）"
  # ② 反向：无支持 ⇒ NOT-YET（不许说成 ok）
  t "★ 无支持（0 命中）⇒ 必须 NOT-YET"        "$(verdict_of 0 1 | grep -c '^NOT-YET')" "1"
  # ③ 零值守卫：树不在 ⇒ SKIP（不是结论）
  t "★ 树不在 ⇒ 必须 SKIP（环境问题不是结论）" "$(verdict_of 0 0 | grep -c '^SKIP')" "1"
  # ③ 零值：命中数为空 ⇒ 不许当 0 静默成 NOT-YET 之外的东西
  t "★ 空命中数 ⇒ 必须落 NOT-YET（空输入不是 ok）" "$(verdict_of '' 1 | grep -c '^NOT-YET')" "1"
  echo "=== check-wasm64-upstream 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}
case "${1:-}" in --selftest) selftest; exit $? ;; esac
[ $# -gt 0 ] && shift || true
while [ $# -gt 0 ]; do case "$1" in --upstream) UPSTREAM="$2"; shift 2 ;; *) echo "未知参数 $1" >&2; exit 2 ;; esac; done

if [ ! -d "$UPSTREAM" ]; then verdict_of 0 0; exit 3; fi
RC="$UPSTREAM/OMCompiler/Compiler/.cmake/rust_omc.cmake"
TOML="$UPSTREAM/OMCompiler/Compiler/OpenModelica.rs/rust-toolchain.toml"
CFG="$UPSTREAM/OMCompiler/Compiler/OpenModelica.rs/.cargo/config.toml"

HITS=0
[ -f "$RC" ]   && HITS=$((HITS + $(grep -ciE 'memory64[": ]*true|-mmemory64|wasm64-' "$RC" || true)))
[ -f "$TOML" ] && HITS=$((HITS + $(grep -ciE 'wasm64|memory64' "$TOML" || true)))
[ -f "$CFG" ]  && HITS=$((HITS + $(grep -ciE 'wasm64|memory64' "$CFG" || true)))
# 全树肯定用法（只在 .rs/.cmake/.toml 里找，排掉 deps/ 与 build 产物）
HITS=$((HITS + $(grep -rlE 'memory64[": ]*true|-mmemory64|wasm64-unknown' \
  --include='*.rs' --include='*.cmake' --include='*.toml' \
  "$UPSTREAM/OMCompiler/Compiler" 2>/dev/null | wc -l)))

verdict_of "$HITS" 1
[ "$HITS" -gt 0 ] && exit 0 || exit 1
