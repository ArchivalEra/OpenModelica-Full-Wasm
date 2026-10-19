#!/bin/sh
# OpenModelica-Full-Wasm — **本仓专属闸门自证台**：每个闸门都必须能证明自己"会红"
# Copyright (C) 2026 ArchivalEra
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 为什么有它（从姊妹仓 Octave-Full-Wasm 搬来，实测教训同形）：
#   检查器里"能证明自己会红"的极少；其余闸门的可证伪性只以散文记着 ⇒ "闸门自己坏了"
#   **没有任何东西会响**。实测到的空转形状：三处站点同时缺同一文件 ⇒ 报"完全一致"；
#   `declared == {}` ⇒ 给出 `verdict:"ok"`；`0/0` 算"全过"；正则一改匹配 0 个而"全合规"恒真。
# ⇒ 本脚本跑每个闸门的 `--selftest`（三类用例：**正常不报 / 该报的必须报 / 空输入必须报**），
#    接进 pre-commit：闸门不能证明自己会红 ⇒ 提交被拦。
#
# 用法：sh build/gates-selftest.sh        # 全绿 exit 0；任一闸门自证不完整 exit 1
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

# ⚠️ 新增闸门时**必须**在这里登记，并在自己的 `--selftest` 里写"该红"用例。
#    名单外的闸门 = 没人盯着的闸门。
# ⚠️ 平台层闸门（zreflect/）由根 `gates-selftest.sh` 的**发现式**名录跑（不在这里手写）——
#    本名单只放**本仓专属**的、平台认不出来的那些。
LIST="$(mktemp)"
cat >"$LIST" <<'EOF'
.githooks/check-whitelist.py --selftest
.githooks/check-wants.py --selftest
.githooks/check-state.py --selftest
.githooks/witness-upstream-pin.py --selftest
build/113/check-lane-purity.py --selftest
build/113/strip-dylink-features.py --selftest
build/113/provision-toolchain.sh --selftest
build/113/build-clang24-builtins.sh --selftest
build/113/build-omc-wasm.sh --selftest
build/113/check-wasm64-upstream.sh --selftest
build/113/gen-runtime-sources-mo.sh --selftest
build/113/measure-samepage-cost.sh --selftest
build/113/ilperf-baseline.sh --selftest
build/113/build-w64-spike.sh --selftest
build/promote-site.sh --selftest
build/provision-upstream.sh --selftest
EOF
# ⚠️ 上面**故意不含** `.githooks/check-consistency.py`：那个检查器查的是**Octave 特有的
#    挂载根常量**（`build/assets.py` 的 OCTAVE_M 与 `bridge/assets-loader.js` 的一致性），
#    本仓没有那些文件 ⇒ 在本仓跑它恒红且无意义。等本仓有了"资产挂载"概念再照写一份自己的。
#    （这条注释就是"为什么名单短"的答案 —— 别照抄姊妹仓的名单。）

n=0; bad=0; badlist=""
# ⚠️ 从**文件**读，不用 `… | while`：管道是子壳，计数器传不出来。
while IFS= read -r line; do
  [ -n "$line" ] || continue
  script="${line%% *}"; args="${line#* }"
  [ "$args" = "$script" ] && args=""
  [ -f "$script" ] || { echo "  ❌ 闸门不存在：$script"; bad=$((bad + 1)); badlist="$badlist $script"; continue; }
  n=$((n + 1))
  case "$script" in
    *.py) out=$(python3 "$script" $args 2>&1) ;;
    *.sh) out=$(sh "$script" $args 2>&1) ;;
    *)    out=$("$script" $args 2>&1) ;;
  esac
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "  ❌ $script"
    printf '%s\n' "$out" | sed 's/^/      /' | tail -8
    bad=$((bad + 1)); badlist="$badlist $script"
  else
    # 末尾机器行（“=== N PASS / M fail ===”）里 N 必须 > 0 且 M == 0（零值守卫）
    tail1=$(printf '%s\n' "$out" | grep -E '===.*[0-9]+ *PASS' | tail -1)
    if [ -z "$tail1" ]; then
      echo "  ⚠️ $script 自证没有任何 PASS 行（空输入不是通过）"; bad=$((bad + 1)); badlist="$badlist $script"
    else
      echo "  ✅ $script  $tail1"
    fi
  fi
done <"$LIST"
rm -f "$LIST"

echo "================================================================================"
if [ "$bad" -eq 0 ]; then
  echo "本仓专属闸门自证：$n 个闸门全部能红 ✅"
  exit 0
fi
echo "❌ $bad/$n 个闸门自证不过：$badlist"
exit 1
