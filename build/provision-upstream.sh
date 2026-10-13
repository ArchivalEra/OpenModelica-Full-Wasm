#!/usr/bin/env bash
# OpenModelica-Full-Wasm — 上游供给：把 upstream/ 的 submodule checkout
# 打成一份**供给树**（另一份拷贝）并写**树指纹** stamp（witness-upstream-pin.py 核对用）。
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
#
# 用法：
#   sh build/provision-upstream.sh [--only name,name] [--dry-run]
#   sh build/provision-upstream.sh --host          # 默认：供给到 pins 里的 container_path（宿主路径）
#   CTR=o113 sh build/provision-upstream.sh        # 容器模式：docker exec 流进容器（本机当前不可用）
#   sh build/provision-upstream.sh --selftest      # 三类用例自证（不碰真树）
#
# 形态：pin 在 build/upstream-pins.json（kind=tree 的才供给；kind=toolchain 的只是
# **版本断言**，不流任何树）。
# stamp 内容 = "<name> <branch> <commit> <dirty>"；供给树被手改/换源 ⇒ witness 红。
#
# ★ 为什么有宿主模式（2026-10-13 加，本仓首批）：本机 docker 不可用（用户不在 docker 组、
#   sudo 被 no_new_privs 挡）⇒ "只能 docker" 就等于**这段管线在本机跑不了**。宿主模式把
#   同一份纪律（树副本 + stamp 对读）铺在宿主盘上：pin 的是 commit，跑的树是另一份拷贝，
#   两者必须被机器对账 —— 这条不变，变的只是"拷贝到哪儿"。
set -euo pipefail
REPO=${REPO:-/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm}
CTR=${CTR:-}                       # 非空 ⇒ 容器模式（docker exec）
DRY=0
ONLY=""
MODE=host
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="$2"; shift 2 ;;
    --host) MODE=host; shift ;;
    --dry-run) DRY=1; shift ;;
    --selftest) MODE=selftest; shift ;;
    *) echo "未知参数 $1" >&2; exit 2 ;;
  esac
done
[ "$MODE" != selftest ] || :   # 自证走下面的 selftest()（不碰真树）

PINS="$REPO/build/upstream-pins.json"
[ -f "$PINS" ] || { echo "FATAL: $PINS 不存在" >&2; exit 2; }

# ── 自证：三类用例（正常不报 / 该报的必须报 / 空输入必须报）─────────────────────
# 纯函数抽出，夹具上跑；真供给树一律不碰。
sel_list() {  # $1=pins文件 → 打印 "name sub_path dest_path branch"
  python3 - "$1" "$ONLY" <<'PY'
import json, sys, os
spec = json.load(open(sys.argv[1]))
only = set(filter(None, (sys.argv[2] or "").split(",")))
for p in spec.get("pins", []):
    if p.get("kind") != "tree":
        continue
    if only and p["name"] not in only:
        continue
    print(p["name"], p["submodule_path"], p["container_path"], p.get("branch", ""))
PY
}
sel_stamp_ok() {  # $1=stamp内容 $2=期望commit $3=dirty → 0=一致
  set -- "$1" "$2" "$3"
  [ "$(printf '%s' "$1" | awk '{print $3}')" = "$2" ] || return 1
  [ "$(printf '%s' "$1" | awk '{print $4}')" = "$3" ] || return 1
  return 0
}
selftest() {
  bad=0; n=0
  t() { # name, fn
    n=$((n+1))
    if eval "$2"; then echo "PASS | $1"; else echo "fail | $1"; bad=$((bad+1)); fi
  }
  # ① 正常：stamp 与 pin 一致 ⇒ 不报
  t "正常：stamp(commit,dirty) 与 pin 一致 ⇒ 一致" "sel_stamp_ok 'om master abc123 0' abc123 0"
  # ② 反向：stamp commit ≠ pin ⇒ 必须报（供给树是另一份拷贝，指针 bumpp 了）
  t "★ 反向：stamp commit ≠ pin ⇒ 必须不一致" "! sel_stamp_ok 'om master DEADBEEF 0' abc123 0"
  # ② 反向：dirty ⇒ 必须报（有人手改了供给树）
  t "★ 反向：供给树 dirty ⇒ 必须不一致" "! sel_stamp_ok 'om master abc123 3' abc123 0"
  # ③ 零值守卫：空 pins ⇒ 清单必须为空（调用方据此判"没东西可供给"）
  t "★ 零值：空 pins ⇒ 清单为空" "empty=\$(mktemp); printf '{\"pins\":[]}' > \$empty; [ -z \"\$(sel_list \$empty)\" ]"
  t "★ 零值：toolchain-only pins ⇒ 清单为空（不流树）" "empty=\$(mktemp); printf '{\"pins\":[{\"name\":\"c\",\"kind\":\"toolchain\",\"container_path\":\"/x\"}]}' > \$empty; [ -z \"\$(sel_list \$empty)\" ]"
  echo "=== provision-upstream 自证：$((n-bad)) PASS / $bad fail ==="
  [ "$bad" -eq 0 ]
}
if [ "$MODE" = selftest ]; then selftest; exit $?; fi

HOST=${HOST_BASE:-$(python3 -c "import json,sys;d=json.load(open('$PINS'));print(d.get('_host_base','/mnt/hdd/openmodelica-wasm-build/build/upstream'))" 2>/dev/null || echo /mnt/hdd/openmodelica-wasm-build/build/upstream)}

LIST=$(mktemp); trap 'rm -f "$LIST"' EXIT
sel_list "$PINS" > "$LIST"
if [ ! -s "$LIST" ]; then
  echo "== 供给清单为空（没有 kind=tree 的 pin）—— 空断言面不是供给成功" >&2
  exit 2
fi

n=0
while read -r name sub cpath branch; do
  [ -d "$REPO/$sub/.git" ] || [ -f "$REPO/$sub/.git" ] || {
    echo "FATAL: $sub 不是已初始化的 submodule（先 git submodule update --init）" >&2; exit 3; }
  COMMIT=$(git -C "$REPO/$sub" rev-parse HEAD)
  DIRTY=$(git -C "$REPO/$sub" status --porcelain | wc -l)
  if [ "$DRY" = 1 ]; then
    echo "[dry-run] $name: $REPO/$sub ($COMMIT, dirty=$DIRTY) → ${CTR:+$CTR:}$cpath"
    n=$((n+1)); continue
  fi
  if [ -n "$CTR" ]; then
    echo "== 供给 $name → $CTR:$cpath（$COMMIT，dirty=$DIRTY）"
    sudo docker exec "$CTR" mkdir -p "$(dirname "$cpath")"
    sudo docker exec "$CTR" rm -rf "$cpath"
    tar -C "$REPO/$sub" --exclude=.git -cf - . | sudo docker exec -i "$CTR" bash -c "mkdir -p '$cpath' && tar -xf - -C '$cpath'"
    printf '%s %s %s %s\n' "$name" "$branch" "$COMMIT" "$DIRTY" | \
      sudo docker exec -i "$CTR" bash -c "cat > '$cpath/.upstream-pin'"
  else
    echo "== 供给 $name → $cpath（宿主模式，$COMMIT，dirty=$DIRTY）"
    mkdir -p "$(dirname "$cpath")"
    rm -rf "$cpath"
    mkdir -p "$cpath"
    tar -C "$REPO/$sub" --exclude=.git -cf - . | tar -xf - -C "$cpath"
    printf '%s %s %s %s\n' "$name" "$branch" "$COMMIT" "$DIRTY" > "$cpath/.upstream-pin"
  fi
  n=$((n+1))
done < "$LIST"
echo "== 供给完成：$n 棵树"
