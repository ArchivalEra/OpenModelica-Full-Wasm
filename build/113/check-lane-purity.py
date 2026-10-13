#!/usr/bin/env python3
# OpenModelica-Full-Wasm — **架构纯度闸门**：一条线只许一个架构（用户点令 2026-10-12）
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# ── 为什么要它（从姊妹仓 Octave-Full-Wasm 的实测教训搬来，判据同形）──────────────
# 混编的失败模式是"**两边都建成功、自检全绿、运行期才炸**"：
#   · wasm32 对象链进 wasm64（`ida.c.o: wasm32 object file can't be linked in wasm64 mode`）；
#   · 错档模块进宿主（加载器只给 `incorrect architecture (wasm32 vs wasm64)`，
#     与"缺符号"的 `reading 'value'` 混在一起时无法区分）。
# ⇒ 判据必须**可执行**，且**反向断言**（喂错档必须红）。
#
# ── 本仓的档表（一线一架构）──────────────────────────────────────────────────
#   master 线              → 产物 wasm64，只编 wasm64
#   wasm32 线              → 产物 wasm32，只编 wasm32
#   IllegalPerformance 线  → 性能线；其产物档由 `--lane ilperf-host` 单独断言（见下）
#
# ⚠️ 与姊妹仓的差异：那边查的是 `.oct`（dlopen 的 side module）；本仓查的是
#    **宿主 wasm + 附属 wasm 模块**（omc.wasm / coderuntime / FMU 之类）。
#    ⇒ 参数名用 `--mod`（可多次），谓词是"每个 wasm 的架构都等于本档期望"。
#
# 用法：
#   python3 build/113/check-lane-purity.py --lane w64    --host omc.wasm --mod omc-runtime.wasm
#   python3 build/113/check-lane-purity.py --lane wasm32 --host omc.wasm
#   python3 build/113/check-lane-purity.py --selftest
import argparse
import os
import shutil
import subprocess
import sys

# 档 → 期望架构。w64/wasm64/master = 64 位；wasm32/wasm32-final = 32 位。
LANE_EXPECT = {
    "w64": "wasm64",
    "wasm64": "wasm64",
    "master": "wasm64",
    "w64-base": "wasm64",
    "ilperf": "wasm64",            # 本仓 IP 线的**产物**是 wasm64（性能优化，不是改架构）
    "wasm32": "wasm32",
    "wasm32-final": "wasm32",
    "product": "wasm32",
    "base": "wasm32",
}


def expected_arch(lane):
    return LANE_EXPECT.get(lane)


def _readobj():
    for c in ("llvm-objdump", "llvm-objdump-19", "llvm-objdump-18", "wasm-objdump"):
        p = shutil.which(c)
        if p:
            return p
    return None


def arch_of(path, run=None):
    """读一个 wasm 文件的架构。返回 'wasm32' / 'wasm64' / None（读不到）。

    ⚠️ `.a`/多成员输入会有多行 `Arch:` ⇒ **取全集去重**而不是只看第一行
    （姊妹仓实测：只看 head -1 会漏掉"一包里混进一个错档"）。
    """
    ro = _readobj()
    if not ro:
        return None
    if run is not None:
        rc, out = run(f"{ro} -h {path}")
    else:
        try:
            p = subprocess.run([ro, "-h", path], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return None
        rc, out = p.returncode, p.stdout
    if rc != 0:
        return None
    arches = {ln.split(":", 1)[1].strip() for ln in out.splitlines()
              if ln.strip().startswith("Arch:")}
    if len(arches) == 1:
        return next(iter(arches))
    if len(arches) > 1:
        return "MIXED(" + ",".join(sorted(arches)) + ")"
    return None


def check(lane, host, mods, arch_of_=arch_of):
    """纯逻辑（自证注入 arch_of_）。返回 (problems, stats)。"""
    problems, stats = [], {}
    want = expected_arch(lane)
    if want is None:
        return ["车道名 %r 未知 ⇒ 不知道期望哪个架构（LANE_EXPECT 表里没有）" % lane], stats

    # ① 宿主
    if host:
        got = arch_of_(host)
        stats["host"] = got
        if got is None:
            problems.append("宿主读不到架构：%s（文件不在 / readobj 不可用）— fail-closed，不当通过"
                            % host)
        elif got != want:
            problems.append("宿主架构错档：期望 %s，实得 %s（%s）"
                            % (want, got, os.path.basename(host)))
    else:
        problems.append("没给 --host ⇒ 判据①没做（零值守卫：空断言面不是通过）")

    # ② 附属模块（每个都要同档；MIXED 一律红）
    n_mod = 0
    for m in mods:
        if not os.path.isfile(m):
            problems.append("附属模块不在：%s — fail-closed，不当通过" % m)
            continue
        got = arch_of_(m)
        n_mod += 1
        if got is None:
            problems.append("附属模块读不到架构：%s" % m)
        elif got != want:
            problems.append("附属模块错档：%s 期望 %s，实得 %s" % (os.path.basename(m), want, got))
    stats["mods"] = n_mod
    if not mods:
        problems.append("没给 --mod ⇒ 判据②没做（零值守卫）")
    return problems, stats


# ── 自证（F1：三类用例：正常不报 / 该报的必须报 / 空输入必须报）────────────────
def _fake(arch_map):
    def _a(p):
        return arch_map.get(os.path.basename(p))
    return _a


def _selftest():
    ok, bad = [], []
    t = "omc.wasm"
    tmp = []

    # ① 正常：w64 宿主 + 同档模块 ⇒ 不报
    d = os.path.join("/tmp", "lane-purity-fix")
    os.makedirs(d, exist_ok=True)
    for f in ("omc.wasm", "runtime.wasm"):
        open(os.path.join(d, f), "w").close()
        tmp.append(os.path.join(d, f))
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "wasm64", "runtime.wasm": "wasm64"}))
    ok.append(("w64 宿主 + 同档模块 ⇒ 不报", not p))

    # ② ★ 反向：wasm32 宿主冒充 w64 ⇒ 必须报
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "wasm32", "runtime.wasm": "wasm64"}))
    ok.append(("★ 宿主错档 ⇒ 必须报", any("宿主架构错档" in x for x in p)))

    # ③ ★ 反向：模块错档 ⇒ 必须报（宿主对）
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "wasm64", "runtime.wasm": "wasm32"}))
    ok.append(("★ 模块错档 ⇒ 必须报", any("附属模块错档" in x for x in p)))

    # ④ ★ MIXED ⇒ 必须报（一包里混档）
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "MIXED(wasm32,wasm64)", "runtime.wasm": "wasm64"}))
    ok.append(("★ MIXED ⇒ 必须报", any("错档" in x for x in p)))

    # ⑤ ★ 零值守卫：没给 host ⇒ 必须报
    p, _ = check("w64", "", [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"runtime.wasm": "wasm64"}))
    ok.append(("★ 没给 --host ⇒ 必须报（零值守卫）", any("零值守卫" in x for x in p)))

    # ⑥ ★ 零值守卫：没给 mod ⇒ 必须报
    p, _ = check("w64", os.path.join(d, t), [],
                 arch_of_=_fake({"omc.wasm": "wasm64"}))
    ok.append(("★ 没给 --mod ⇒ 必须报（零值守卫）", any("零值守卫" in x for x in p)))

    # ⑦ ★ 读不到架构 ⇒ fail-closed 报
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({}))
    ok.append(("★ 读不到架构 ⇒ fail-closed 报", any("读不到" in x for x in p)))

    # ⑧ ★ 未知档名 ⇒ 必须报
    p, _ = check("nonsense-lane", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "wasm64"}))
    ok.append(("★ 未知档名 ⇒ 必须报", any("未知" in x for x in p)))

    for f in tmp:
        try:
            os.unlink(f)
        except OSError:
            pass
    nbad = sum(1 for _, good in ok if not good)
    for name, good in ok:
        print(("PASS | " if good else "fail | ") + name)
    print("=== check-lane-purity 自证：%d PASS / %d fail ===" % (len(ok) - nbad, nbad))
    return nbad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="")
    ap.add_argument("--host", default="")
    ap.add_argument("--mod", action="append", default=[])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.lane:
        print("FATAL: 必须给 --lane", file=sys.stderr)
        return 2
    problems, stats = check(a.lane, a.host, a.mod)
    for p in problems:
        print("  ✗ %s" % p, file=sys.stderr)
    if problems:
        print("架构**不纯**（%d 条）⇒ 别上线" % len(problems), file=sys.stderr)
        return 1
    print("架构纯度 OK：lane=%s 期望=%s 宿主=%s 模块=%d 个" %
          (a.lane, expected_arch(a.lane), stats.get("host"), stats.get("mods", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
