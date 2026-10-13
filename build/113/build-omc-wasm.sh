#!/usr/bin/env bash
# OpenModelica-Full-Wasm — **omc.wasm 构建入口**（需求 A；本仓 2026-10-13 首批）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# 一句话：把上游 OpenModelica 的**第一方 wasm 目标**（rust_omc.cmake 的 OM_OMC_WASM）
# build 成可在 Node 里跑的 omc 包，并写**产物身份证**（verdict==ok 才可部署）。
#
# ── 为什么是这条链（每条都有实测出处，不猜）────────────────────────────────────
#  · 开关：根 CMakeLists.txt:115-118 `omc_option(OM_OMC_WASM ... OFF)`，开它 FORCE 打开
#    OM_OMC_ENABLE_RUST ⇒ 走 Rust omc 移植（mmtorust 转译 + cargo build），
#    **不编 bomc/omc 的 C 引导链**（OMCompiler/Compiler/CMakeLists.txt:2-8,66-71）。
#  · 模式：rust_omc.cmake:1923-1946 `RUST_OMC_WASM_MODE=web-release|node-release|...`
#    node-release ⇒ wasm-bindgen --target nodejs，产物落 `<build>/OMCompiler/Compiler/web/pkg-nodejs/`
#    （:2218），旁边配 omc-cli.js（:2219,2261）；install 装 `share/omc/web`（:2282-2284）。
#  · 工具链：clang + wasi-libc + wasm-ld（:261 注释）；builtins 见 :297-320。
#  · 两步链（本仓采用，理由见 docs/REQUIREMENTS.md §7）：
#      ① stage1 `-DOM_OMC_ENABLE_RUST=ON -DRUST_OMC_CI=ON -DRUST_OMC_WASM_ARTIFACTS_OUT=<dir>`
#         + `--target rust_codegen rust_wasm_runtime rust_wasm_artifacts`（官方 README:333-356）
#         —— 产出 wasm 交接件 + 顺带在源树生成 `SimulationRuntime/c/RuntimeSources.mo`
#            （官方 CI 为此专门 stash/unstash 搬运：.CI/common.groovy:554-556）。
#      ② stage2 `-DOM_OMC_WASM=ON -DRUST_OMC_WASM_MODE=node-release
#         -DRUST_OMC_PREBUILT_WASM_DIR=<dir>` + `--target install`（官方 README:358-369）。
#
# ── CLI 与退出码（与工单 01 的 Settling 契约逐字一致）──────────────────────────
#   build-omc-wasm.sh --dry-run | build | --verify | --selftest
#   rc=0 构建成功（Node 里 getVersion() 出串）；rc=1 构建/判定失败（打印卡在哪）；
#   rc=2 用法错；rc=3 环境问题（工具链/target 缺）。
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# 宿主直跑（2026-10-13：本机 docker 不可用 —— 用户不在 docker 组、sudo 被 no_new_privs 挡）
BASE="${OMC_BASE:-/mnt/hdd/openmodelica-wasm-build}"
UPSTREAM="${UPSTREAM:-$BASE/build/upstream/openmodelica}"
OUT="${OUT:-$BASE/build/omc-out-wasm32}"
TOOLS="${TOOLS:-$BASE/tools}"
MODE="${MODE:-node-release}"
JOBS="${JOBS:-$(nproc)}"
# 单测期可覆写成小值（--selftest 不跑真构建）
STAGE1_TARGETS="${STAGE1_TARGETS:-rust_codegen rust_wasm_runtime rust_wasm_artifacts}"
# wasm-opt（binaryen -Oz 体积优化）：**默认 OFF**，理由是本机实测：
#   · 上游 rust_omc.cmake:829 的旗标清单（--enable-bulk-memory …）与唯一可用的
#     binaryen 133（emsdk 版）**不兼容** —— 旧 feature 名在新版被改名
#     （bulk-memory → bulk-memory-opt，等等），上游因此在自己的 build.rs:801 **panic**
#     （原文：`wasm-opt failed on .../fmi3_me_adapter.wasm. Fix the binaryen invocation,
#      or build with -DRUST_OMC_WASM_OPT=OFF to leave every blob unoptimized.`）
#   · ⇒ 按上游给的正道关掉它。代价**只**是产物偏大（官方 CI 也是 PR 关、发布开，
#     见 .CI/common.groovy:1483-1487），功能不受影响。
#   · 想开：WASM_OPT=ON 前先装与上游旗标兼容的 binaryen（或补全 feature 别名）。
WASM_OPT="${WASM_OPT:-OFF}"

log()  { printf '%s\n' "$*"; }
err()  { printf '%s\n' "$*" >&2; }

# ── 纯逻辑（自证走这里，不碰真构建）──────────────────────────────────────────
verdict_of() {  # $1=构建 rc $2=node 探针 rc → verdict 串（纯函数）
  if [ "${1:-x}" != 0 ]; then echo "failed(构建 rc=$1)"; return; fi
  if [ "${2:-x}" != 0 ]; then echo "unverified(node 探针 rc=$2)"; return; fi
  echo ok
}
id_check() {  # $1=verdict $2=wasm 字节 $3=web 目录文件数 → ok / 说明
  if [ "${2:-0}" -le 0 ]; then echo "产物为空（$2 字节）"; return; fi
  if [ "${3:-0}" -le 0 ]; then echo "web 包为空（$3 个文件）—— 布局没收全？"; return; fi
  if [ "${1:-}" != "ok" ]; then echo "verdict=$1 不可部署（只有 ok 可部署）"; return; fi
  echo ok
}
selftest() {
  bad=0; n=0
  t() { n=$((n+1)); if [ "$2" = "$3" ]; then echo "PASS | $1"; else echo "fail | $1（期望 '$3' 实得 '$2'）"; bad=$((bad+1)); fi; }
  # ① 正常不报
  t "构建+探针都过 ⇒ ok"                    "$(verdict_of 0 0)" "ok"
  t "身份证齐（ok/非空/有包）⇒ ok"           "$(id_check ok 1048576 12)" "ok"
  # ② 该报的必须报（反向；每条都是真实失败形状）
  t "★ 构建失败 ⇒ 必须不是 ok（不许静默绿）"  "$(verdict_of 1 0 | grep -c '^failed')" "1"
  t "★ 构建过但探针失败 ⇒ 必须 unverified"    "$(verdict_of 0 1)" "unverified(node 探针 rc=1)"
  t "★ 产物 0 字节 ⇒ 必须报（空产物不是成功）" "$(id_check ok 0 12 | grep -c '产物为空')" "1"
  t "★ web 包 0 文件 ⇒ 必须报（布局没收全）"   "$(id_check ok 1024 0 | grep -c 'web 包为空')" "1"
  t "★ 未核对（unverified）⇒ 必须不可部署"     "$(id_check unverified 1024 12 | grep -c '不可部署')" "1"
  t "★ 缺 verdict（空）⇒ 必须不可部署"         "$(id_check '' 1024 12 | grep -c '不可部署')" "1"
  # ③ 空输入必须报（零值守卫）
  t "★ 空字节数 ⇒ 必须报（-0 ⇒ 空输入）"      "$(id_check ok '' 12 | grep -c '产物为空')" "1"
  echo "=== build-omc-wasm 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}

# ── 预检（rc=3 级：环境问题不是结论）────────────────────────────────────────
precheck() {
  local bad=0
  [ -d "$UPSTREAM/OMCompiler/Compiler/.cmake" ] || { err "FATAL: 上游树不在 $UPSTREAM（先跑 build/provision-upstream.sh）"; bad=1; }
  for t in clang wasm-ld llvm-ar llvm-objdump; do
    [ -x "$TOOLS/bin/$t" ] || { err "FATAL: 缺 $TOOLS/bin/$t（先跑 build/113/provision-toolchain.sh install）"; bad=1; }
  done
  [ -s "$TOOLS/clang-resource/lib/wasi/libclang_rt.builtins-wasm32.a" ] || {
    err "FATAL: 缺 wasm32 builtins（上游 configure 会 FATAL；跑 provision-toolchain.sh）"; bad=1; }
  rustup run nightly-2026-05-31 rustc --version >/dev/null 2>&1 || {
    err "FATAL: 缺 rust nightly-2026-05-31（rustup toolchain install）"; bad=1; }
  for tg in wasm32-unknown-unknown wasm32-wasip1; do
    rustup target list --installed --toolchain nightly-2026-05-31 2>/dev/null | grep -qx "$tg" || {
      err "FATAL: rust nightly 缺 target $tg"; bad=1; }
  done
  cmake --version >/dev/null 2>&1 || { err "FATAL: 缺 cmake"; bad=1; }
  ninja --version >/dev/null 2>&1 || { err "FATAL: 缺 ninja"; bad=1; }
  node --version >/dev/null 2>&1 || { err "FATAL: 缺 node（跑 getVersion 探针要用）"; bad=1; }
  # 实编一次才叫"工具链能用"（不是看文件在不在）
  if [ "$bad" = 0 ] && [ "${SKIP_SMOKE:-0}" != 1 ]; then
    local T; T="$(mktemp -d)"
    printf 'int f(int x){return x;}\n' > "$T/t.c"
    PATH="$TOOLS/bin:$PATH" clang --target=wasm32-wasip1 -c "$T/t.c" -o "$T/t.o" 2>/dev/null \
      || { err "FATAL: clang 实编 wasm32-wasip1 失败（wrapper/overlay 坏了？跑 provision-toolchain.sh status）"; bad=1; }
    rm -rf "$T"
  fi
  return "$bad"
}

# ── 构建（两步官方链）──────────────────────────────────────────────────────
do_build() {
  mkdir -p "$OUT"
  local S1="$OUT/stage1" S2="$OUT/stage2" ART="$OUT/wasm-artifacts"
  export PATH="$TOOLS/bin:$PATH"          # 稳定入口：wrapper 的 clang/wasm-ld 先于系统
  export RUSTUP_TOOLCHAIN=nightly-2026-05-31
  # cargo 的 registry 已换 rsproxy（~/.cargo/config.toml）；构建期下载走代理
  export http_proxy="${http_proxy:-http://127.0.0.1:2080}"
  export https_proxy="${https_proxy:-http://127.0.0.1:2080}"
  export no_proxy="${no_proxy:-127.0.0.1,localhost}"

  log "== ① 前置：RuntimeSources.mo（wasm 模式跳过它的唯一生成点，缺了 mmtorust **静默半缺**）"
  sh "$REPO/build/113/gen-runtime-sources-mo.sh" generate || { err "FATAL: RuntimeSources.mo 没生成"; return 1; }
  [ -s "$UPSTREAM/OMCompiler/SimulationRuntime/c/RuntimeSources.mo" ] || {
    err "FATAL: RuntimeSources.mo 不在源树"; return 1; }

  log "== ② stage1：wasm 交接件（rust_codegen / rust_wasm_runtime / rust_wasm_artifacts）"
  # ⚠️ stage1 也开 OM_OMC_WASM=ON（**不是** native configure）：native 路径要 Fortran/minizip
  #    等一堆本机没有的 native 依赖（实测撞两次墙，无 root 装不了）。要它产的只有
  #    "wasm 交接件"（wasi-libc PIC sysroot / sundials-wasm / blobs），这三样在 wasm 模式下
  #    一样能产（RUST_OMC_WASM_ARTIFACTS_OUT 就是为它们设计的）。
  #    RuntimeSources.mo 由上面那条单独生成（官方 CI 就是把它 stash 出来的，R3）。
  log "   源码树 $UPSTREAM"
  cmake -S "$UPSTREAM" -B "$S1" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DOM_OMC_WASM=ON -DRUST_OMC_WASM_MODE="$MODE" -DRUST_OMC_CI=ON \
    -DRUST_OMC_WASM_ARTIFACTS_OUT="$ART" \
    -DRUST_OMC_WASM_OPT="$WASM_OPT" \
    -DRUST_OMC_MOLD=OFF -DOM_USE_CCACHE=OFF -DRUST_OMC_ENABLE_SUNDIALS=ON \
    > "$OUT/stage1.configure.log" 2>&1 || { err "FATAL: stage1 configure 失败（tail $OUT/stage1.configure.log）"; tail -30 "$OUT/stage1.configure.log" >&2; return 1; }
  cmake --build "$S1" --parallel "$JOBS" --target $STAGE1_TARGETS \
    > "$OUT/stage1.build.log" 2>&1 || { err "FATAL: stage1 build 失败（tail $OUT/stage1.build.log）"; tail -30 "$OUT/stage1.build.log" >&2; return 1; }
  log "   ① stage1 完成"
  [ -d "$ART/wasi-pic-sysroot" ] || { err "FATAL: 交接件缺 wasi-pic-sysroot（stage2 会缺 libc）"; return 1; }

  log "== ② stage2：wasm 包（OM_OMC_WASM=ON / RUST_OMC_WASM_MODE=$MODE / 吃交接件）"
  cmake -S "$UPSTREAM" -B "$S2" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DOM_OMC_WASM=ON -DRUST_OMC_WASM_MODE="$MODE" -DRUST_OMC_CI=ON \
    -DRUST_OMC_PREBUILT_WASM_DIR="$ART" \
    -DRUST_OMC_WASM_OPT="$WASM_OPT" \
    -DRUST_OMC_MOLD=OFF -DOM_USE_CCACHE=OFF \
    -DCMAKE_INSTALL_PREFIX="$OUT/install" \
    > "$OUT/stage2.configure.log" 2>&1 || { err "FATAL: stage2 configure 失败（tail $OUT/stage2.configure.log）"; tail -40 "$OUT/stage2.configure.log" >&2; return 1; }
  cmake --build "$S2" --parallel "$JOBS" --target install \
    > "$OUT/stage2.build.log" 2>&1 || { err "FATAL: stage2 build 失败（tail $OUT/stage2.build.log）"; tail -40 "$OUT/stage2.build.log" >&2; return 1; }
  log "   ② stage2 完成"

  # ── 收口：把可跑的 web/ 目录摊到 OUT/web（Node 侧 layout：omc-cli.js + pkg-nodejs/ + wasm-blobs/）
  local WEB_SRC="$OUT/install/share/omc/web"
  [ -d "$WEB_SRC" ] || WEB_SRC="$S2/OMCompiler/Compiler/web"
  [ -d "$WEB_SRC" ] || { err "FATAL: 找不到 web 包（$WEB_SRC）"; return 1; }
  rm -rf "$OUT/web"; mkdir -p "$OUT/web"
  cp -a "$WEB_SRC/." "$OUT/web/"
  log "   web 包 → $OUT/web（$(find "$OUT/web" -type f | wc -l) 个文件）"
  return 0
}

# ── 身份证（生产侧初值 unverified；--verify 实核后才写 ok）───────────────────
write_id() {  # $1=verdict  $2=探针输出
  local wasm="" sha="" bytes="" nver=""
  wasm="$(find "$OUT/web" -name '*_bg.wasm' | head -1)"
  [ -n "$wasm" ] && { sha="$(sha256sum "$wasm" | cut -d' ' -f1)"; bytes="$(stat -c%s "$wasm")"; }
  nver="$(rustup run nightly-2026-05-31 rustc --version 2>/dev/null | cut -d' ' -f2)"
  local wasm_p="${wasm:-}" bytes_v="${bytes:-0}"
  cat > "$OUT/omc.build.json" <<EOF
{
  "schema": 1,
  "tool": {"name": "build-omc-wasm.sh", "script_sha256": "$(sha256sum "$0" | cut -d' ' -f1)",
           "clang": "$("$TOOLS/bin/clang" --version 2>/dev/null | head -1)",
           "rustc": "$nver"},
  "build": {"when": "$(date -Iseconds)", "out": "$OUT", "mode": "$MODE",
            "upstream": "$UPSTREAM", "upstream_commit": "$(git -C "$UPSTREAM" rev-parse HEAD 2>/dev/null)"},
  "declared": {"mode": "$MODE", "stage1_targets": "$STAGE1_TARGETS", "host": "host-direct"},
  "measured": {"files": {"omc_bg_wasm": {"path": "$wasm_p", "sha256": "$sha", "bytes": $bytes_v}},
               "web_files": $(find "$OUT/web" -type f 2>/dev/null | wc -l)},
  "verdict": "$1",
  "probe": $(printf '%s' "${2:-}" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""'),
  "checked": {"when": "$(date -Iseconds)", "by": "build-omc-wasm.sh --verify"}
}
EOF
}

# ── verify：只核不写（读身份证 + 重跑探针 + 架构纯度）───────────────────────
do_verify() {
  local bad=0
  local W="$OUT/web/omc-cli.js"
  [ -f "$W" ] || { err "FATAL: 缺 $W（还没构建？跑 build）"; return 1; }
  [ -f "$OUT/omc.build.json" ] || { err "FATAL: 缺 $OUT/omc.build.json（还没构建？）"; return 1; }
  # ① 探针：Node 里 getVersion() 出串（需求 A3 的判据）
  local PROBE_OUT PROBE_RC
  PROBE_OUT="$(cd "$OUT/web" && timeout 300 node omc-cli.js 'getVersion()' 2>&1)"; PROBE_RC=$?
  log "   探针: getVersion() rc=$PROBE_RC out='$PROBE_OUT'"
  [ "$PROBE_RC" = 0 ] || bad=1
  # 判据：非空 + 是版本形状。⚠️ 别只认 'OpenModelica|1.x'：本仓产物实测吐 `"-rust"`
  # （构建树无 git tag ⇒ 上游 omc_git_revision.cmake 走 SOURCE_REVISION=unknown 降级路径）。
  # 且**反向**必须能红：空输出/报错文本不算过（下面两条 + id_check 的空产物守卫一起管）。
  printf '%s' "$PROBE_OUT" | grep -qE '^-?"?[A-Za-z0-9_.+-]+"?$' || { err "   探针输出不是单个版本串：$PROBE_OUT"; bad=1; }
  printf '%s' "$PROBE_OUT" | grep -qiE 'error|traceback|cannot|failed' && { err "   探针输出里有错误字样"; bad=1; }
  # ② 产物 sha/字节（从磁盘读出来）
  local wasm sha bytes
  wasm="$(find "$OUT/web" -name '*_bg.wasm' | head -1)"
  [ -n "$wasm" ] || { err "   FATAL: web 里没有 *_bg.wasm"; bad=1; }
  sha="$(sha256sum "$wasm" | cut -d' ' -f1)"; bytes="$(stat -c%s "$wasm")"
  # ⚠️ 别用 ${var:0:16}（bash 专属子串）：本脚本用 `sh` 跑（dash 会报 Bad substitution）
  local sha16; sha16="$(printf '%s' "$sha" | cut -c1-16)"
  log "   产物: $wasm ($bytes 字节, sha256=$sha16…)"
  # ③ 架构纯度（一线一架构；本档 = wasm32）
  local NVER=$([ "$bad" = 0 ] && echo 0 || echo 1)
  local V; V="$(verdict_of 0 "$NVER")"
  local IC; IC="$(id_check "$V" "${bytes:-0}" "$(find "$OUT/web" -type f 2>/dev/null | wc -l)")"
  if [ "$IC" != ok ]; then err "   FATAL: 身份证判据不过：$IC"; bad=1; fi
  if [ "$bad" = 0 ]; then
    # 附属模块：node 包里的 blobs（liblapack / libc_pic / ModelicaUtilities）——与宿主**同档**。
    # 闸门的零值守卫要求至少一个 --mod（喂空会**正确地**报"没查到东西"）。
    # ⚠️ 用 `sh` 兼容写法（本脚本被 dash 跑）：不要数组、不要 <(...)。
    MODS=""
    for b in "$OUT"/web/wasm-blobs/*.wasm; do
      [ -f "$b" ] || continue
      MODS="$MODS --mod $b"
    done
    if [ -n "$MODS" ]; then
      # shellcheck disable=SC2086  # 故意按空格拆成多个 --mod（路径无空格：/mnt/hdd 下）
      python3 "$REPO/build/113/check-lane-purity.py" --lane wasm32 --host "$wasm" $MODS \
        || { err "   FATAL: 架构纯度闸门红（错档产物）"; bad=1; }
      log "   架构纯度: --lane wasm32 --host + $(printf '%s' "$MODS" | grep -o '\-\-mod' | wc -l) 个附属模块 ⇒ 过"
    else
      err "   ⚠️ web/wasm-blobs 里没有 .wasm ⇒ 只查宿主（零值守卫会报'没查到'）"
      python3 "$REPO/build/113/check-lane-purity.py" --lane wasm32 --host "$wasm" || { err "   FATAL: 架构纯度闸门红"; bad=1; }
    fi
  fi
  if [ "$bad" = 0 ]; then
    write_id ok "$PROBE_OUT"
    log "   ✅ verdict=ok 已写入 $OUT/omc.build.json"
  else
    err "   ❌ 核对不过 —— 身份证保持 $([ -f "$OUT/omc.build.json" ] && python3 -c "import json;print(json.load(open('$OUT/omc.build.json')).get('verdict'))" 2>/dev/null || echo '(无)')"
  fi
  return "$bad"
}

# ── main ────────────────────────────────────────────────────────────────────
case "${1:-build}" in
  --selftest) selftest; exit $? ;;
  --dry-run)
    log "== dry-run：要做什么 =="
    log "  上游树   : $UPSTREAM ($(git -C "$UPSTREAM" rev-parse --short HEAD 2>/dev/null || echo '(无)'))"
    log "  产物     : $OUT"
    log "  工具链   : $TOOLS/bin/{clang,wasm-ld,llvm-ar}"
    log "  模式     : RUST_OMC_WASM_MODE=$MODE  并行=$JOBS"
    log "  stage1   : cmake -DOM_OMC_ENABLE_RUST=ON -DRUST_OMC_CI=ON -DRUST_OMC_WASM_ARTIFACTS_OUT=$OUT/wasm-artifacts"
    log "             --target $STAGE1_TARGETS"
    log "  stage2   : cmake -DOM_OMC_WASM=ON -DRUST_OMC_WASM_MODE=$MODE -DRUST_OMC_PREBUILT_WASM_DIR=$OUT/wasm-artifacts --target install"
    log "  预检     : rust nightly-2026-05-31 + [wasm32-unknown-unknown, wasm32-wasip1] + builtins + 实编冒烟"
    if precheck; then log "  ✅ 预检通过（rc=0）"; else err "  ❌ 预检不过（rc=3）"; exit 3; fi
    ;;
  build)
    precheck || { err "环境问题（rc=3）：修好上面点名的再跑"; exit 3; }
    do_build || exit 1
    write_id unverified ""
    log "构建完成。下一步：--verify（实核并写 verdict=ok）"
    ;;
  --verify)
    do_verify || exit 1
    ;;
  *) err "用法: build-omc-wasm.sh --dry-run|build|--verify|--selftest"; exit 2 ;;
esac
