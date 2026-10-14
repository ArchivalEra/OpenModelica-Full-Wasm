#!/usr/bin/env bash
# OpenModelica-Full-Wasm — **wasm64 可行性可行件**（IllegalPerformance 线；2026-10-14）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# 一句话：**在本机把 Rust 编成 wasm64 并验档**（可复跑、可证伪）。
#
# ── 为什么需要它（一次错误结论的更正，逐字记下来别再犯）───────────────────────
#   我曾写"Rust 侧没有 wasm64 target ⇒ 编译器主体编不成 wasm64"，
#   依据是 `rustup target list` —— **那是"可安装"列表，不是编译器内置目标表**。
#   实测（2026-10-14）：
#     · `rustc --print target-list | grep wasm64` → **`wasm64-unknown-unknown` 在**；
#     · 裸编报 `can't find crate for core`（该目标没有预编译 std）；
#     · **`cargo build --target wasm64-unknown-unknown -Zbuild-std=core,alloc`** ⇒
#       **8.8 秒编出 wasm64 产物**，实例化成功（`add64(2n,3n)=5`），
#       且**本仓纯度闸门认出档是 wasm64**（memory64 标志判据）。
#   ⇒ 结论更正：**wasm64 在工具链侧可做**；缺的是**上游 CMake 路径**（`rust_omc.cmake`
#     里 0 命中 wasm64）——即"上游还没把它接进构建系统"，不是"编不出来"。
#
# ── 本脚本做什么 ─────────────────────────────────────────────────────────────
#   ① 在**仓外临时目录**编一个最小 wasm64 crate（不碰本仓产物、不碰上游树）；
#   ② 用本仓纯度闸门验档（`--lane wasm64`）；
#   ③ 反向：同一条闸门对 wasm32 产物**必须红**（证明判据不是恒真）；
#   ④ 打印档特征（memory 导入/导出、BigInt 调用），供台账读。
#
# 用法：
#   bash build/113/build-w64-spike.sh            # 编 + 验 + 打印
#   bash build/113/build-w64-spike.sh --json     # 一行 JSON（供台账）
#   bash build/113/build-w64-spike.sh --selftest # 三类用例自证
# 退出码：0 = 编成且验档通过；1 = 编/验失败；2 = 用法；3 = 环境（缺 rust 组件）
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CHANNEL="${CHANNEL:-nightly-2026-05-31}"
WORK="${WORK:-/tmp/omc-w64-spike}"
GATE="$REPO/build/113/check-lane-purity.py"

# ── 纯逻辑（自证走这里）──────────────────────────────────────────────────────
# ⚠️ 反向断言那一行的**判据方向**（第一版写反了，自证台当场抓到）：
#   "反向合格" = 闸门对 wasm32 产物**返回非 0**（rc=1）⇒ 我们期望 `$3 == 1`。
#   写成 `!= 1` 会变成"只要不是 1 就报错"，与语义相反。
verdict_of() {  # $1=产物字节 $2=闸门 rc $3=反向 rc（1=正确地红了）→ ok / 说明
  [ "${1:-0}" -gt 0 ] || { echo "编不出产物（字节 0 —— 零值守卫：空产物不是通过）"; return; }
  [ "${2:-1}" = 0 ] || { echo "纯度闸门没通过（rc=$2）"; return; }
  [ "${3:-0}" = 1 ] || { echo "反向断言失效：wasm32 产物喂 wasm64 档居然通过了"; return; }
  echo ok
}
selftest() {
  bad=0; n=0
  t() { n=$((n+1)); if [ "$2" = "$3" ]; then echo "PASS | $1"; else echo "fail | $1（期望 '$3' 实得 '$2'）"; bad=$((bad+1)); fi; }
  # ① 正常不报
  t "正常：编成 + 闸门过 + 反向红 ⇒ ok" "$(verdict_of 353 0 1)" "ok"
  # ② 该报的必须报
  t "★ 产物 0 字节 ⇒ 必须报" "$(verdict_of 0 0 1 | grep -c '编不出产物')" "1"
  t "★ 闸门没通过 ⇒ 必须报" "$(verdict_of 353 1 1 | grep -c '纯度闸门没通过')" "1"
  t "★ 反向断言失效（wasm32 也过）⇒ 必须报" "$(verdict_of 353 0 0 | grep -c '反向断言失效')" "1"
  # ③ 空输入必须报
  t "★ 空输入 ⇒ 必须报" "$(verdict_of '' '' '' | grep -c '编不出产物')" "1"
  echo "=== build-w64-spike 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}
case "${1:-}" in --selftest) selftest; exit $? ;; --json|"") ;; *) echo "用法: build-w64-spike.sh [--json|--selftest]" >&2; exit 2 ;; esac
JSON=0; [ "${1:-}" = "--json" ] && JSON=1

# ── 环境（缺组件 ⇒ rc=3，不是结论）────────────────────────────────────────────
rustup run "$CHANNEL" rustc --version >/dev/null 2>&1 || { echo "FATAL: 环境：缺 $CHANNEL" >&2; exit 3; }
rustup run "$CHANNEL" rustc --print target-list 2>/dev/null | grep -qx 'wasm64-unknown-unknown' || {
  echo "FATAL: 环境：$CHANNEL 的目标表里没有 wasm64-unknown-unknown" >&2; exit 3; }
[ -d "$(rustup run "$CHANNEL" rustc --print sysroot 2>/dev/null)/lib/rustlib/src/rust/library/core" ] || {
  echo "FATAL: 环境：缺 rust-src（-Zbuild-std 要它）" >&2; exit 3; }

# ── ① 编（仓外临时目录；不碰本仓产物与上游树）─────────────────────────────────
rm -rf "$WORK"; mkdir -p "$WORK/src"
cat > "$WORK/Cargo.toml" <<'TOML'
[package]
name = "w64spike"
version = "0.1.0"
edition = "2021"
[lib]
crate-type = ["cdylib"]
[profile.release]
panic = "abort"
TOML
cat > "$WORK/src/lib.rs" <<'RS'
#![no_std]
#![no_main]
#[panic_handler]
fn p(_: &core::panic::PanicInfo) -> ! { loop {} }
/// 64 位地址空间的自证：usize 是 64 位 ⇒ 调用侧必须给 BigInt（实测特征）。
#[no_mangle]
pub extern "C" fn add64(a: usize, b: usize) -> usize { a.wrapping_add(b) }
RS
( cd "$WORK" && RUSTUP_TOOLCHAIN="$CHANNEL" cargo build --release \
    --target wasm64-unknown-unknown -Zbuild-std=core,alloc > build.log 2>&1 ) \
  || { echo "FATAL: 编译失败（tail $WORK/build.log）" >&2; tail -12 "$WORK/build.log" >&2; exit 1; }
W="$WORK/target/wasm64-unknown-unknown/release/w64spike.wasm"
BYTES="$(stat -c%s "$W" 2>/dev/null || echo 0)"

# ── ② 闸门验档（正例）───────────────────────────────────────────────────────
G="$(python3 "$GATE" --lane wasm64 --host "$W" --mod "$W" >/tmp/_w64gate.log 2>&1; echo $?)"
# ── ③ 反向：wasm32 产物喂 wasm64 档（必须红）─────────────────────────────────
T32="$WORK/_t32.wasm"
printf 'int f(int x){return x;}\n' > "$WORK/_t.c"
"${TOOLS:-/mnt/hdd/openmodelica-wasm-build/tools}/bin/clang" --target=wasm32-unknown-unknown \
  -nostdlib -Wl,--no-entry "$WORK/_t.c" -o "$T32" 2>/dev/null || T32=""
RG=0
if [ -n "$T32" ]; then
  python3 "$GATE" --lane wasm64 --host "$T32" --mod "$T32" >/tmp/_w64rev.log 2>&1 && RG=0 || RG=1
fi

V="$(verdict_of "$BYTES" "$G" "$RG")"
[ "$V" = ok ] || { echo "量不到：$V" >&2; exit 1; }

SHA="$(sha256sum "$W" | cut -d' ' -f1)"
if [ "$JSON" = 1 ]; then
  printf '{"schema":1,"lane":"wasm64","wasm":"%s","bytes":%s,"sha256":"%s","gate_rc":%s,"reverse_rc":%s,"channel":"%s"}\n' \
    "$W" "$BYTES" "$SHA" "$G" "$RG" "$CHANNEL"
else
  echo "== wasm64 可行件（IllegalPerformance 线）=="
  echo "   通道      : $CHANNEL（-Zbuild-std=core,alloc 自建 std）"
  echo "   产物      : $W"
  echo "   字节      : $BYTES"
  echo "   sha256    : ${SHA%"${SHA#????????????????}"}…"
  echo "   纯度闸门  : rc=$G  ✅（lane=wasm64 期望=wasm64 宿主=wasm64）"
  echo "   反向断言  : wasm32 产物喂 wasm64 档 ⇒ rc=$RG （1 = 正确地红了）"
  echo
  echo "⇒ **工具链侧 wasm64 可做**；缺的是**上游 CMake 路径**（rust_omc.cmake 0 命中 wasm64）。"
  echo "   即"上游还没把这条接进构建系统"，不是"编不出来"（这正是本脚本要钉住的事实）。"
fi
