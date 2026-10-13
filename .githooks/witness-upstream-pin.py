#!/usr/bin/env python3
# OpenModelica-Full-Wasm — **上游 pin 见证**（fork 管线 §1 身份层；Einfacht #5 witness 档同族）
# Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later
# 从姊妹仓 Octave-Full-Wasm 移植（2026-10-13），**加宿主模式**：
#   · kind=tree  条目可带 `stamp_read`（shell 命令读供给树 stamp），缺省回退 docker exec cat；
#   · kind=toolchain 条目可带 `probe`（shell 命令读版本串），缺省回退 docker exec emcc。
#   为什么加：本机 2026-10-13 起 docker 不可用（用户不在 docker 组、sudo 被 no_new_privs 挡），
#   若只认 docker，这条闸门对本仓就**恒 SKIP** —— "读不到"看起来像"没问题"。
#   宿主模式让它在没有 docker 的机器上仍是**真断言**（stamp 与 submodule gitlink 对读）。
#
# 断言：「供给树（另一份拷贝）== build/upstream-pins.json 登记的 commit」。
# 为什么：submodule 指针 bump 了、供给树还是老拷贝——这种漂移不进任何 git 视图，
# 只能靠"每提交把供给树戳一次章"来抓。
#
# 判据（stdout 裸值契约）：`ok` / `DRIFT: …`；退出码恒 0（同 witness-build-inputs）。
# 读不到（docker 不在/树未供给）⇒ `SKIP: …`（"换机器不是错"，但**不是通过**）。
# 未启用（无 build/upstream-pins.json）⇒ 明说未启用退 0。
# 用法：python3 .githooks/witness-upstream-pin.py ／ --selftest
import json
import os
import sys

# ⚠️ 本文件在 .githooks/ 下（两层到根），别抄 build/113/ 里那套三层 dirname
REPO = os.environ.get("GATE_REPO") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SPEC = os.path.join(REPO, "build", "upstream-pins.json")
# 通用闸门（上游 zreflect/check_pins.py）的规格 —— **C4 对账**用：两份 pins 的
# `expect_version` 必须一致，否则两个闸门互相打架（一边说 6.0.12 对、另一边说漂移）。
GENERIC_SPEC = os.path.join(REPO, "build", "pins.json")


def crosscheck(generic_path=None, my_spec=None):
    """两份 pin 规格的**同名 pin 版本串**必须一致（上游 C4「必须一致的要配对账器」）。

    为什么需要：本仓同时挂**两个** pin 闸门——本仓专属的 `witness-upstream-pin.py`
    （读 `build/upstream-pins.json` 的 `expect_version`）与上游通用的
    `zreflect/check_pins.py`（读 `build/pins.json` 的 `expect_version`）。同一个
    emsdk 版本被抄了两份 ⇒ 迟早只改一份（升版时最容易）⇒ 一个闸门绿、另一个红，
    或者更坏：两个都绿但你不知道该信哪个。返回问题清单（空 = 一致）。
    """
    gp = generic_path if generic_path is not None else GENERIC_SPEC
    ms = my_spec if my_spec is not None else DEFAULT_SPEC
    problems = []
    try:
        gen = json.load(open(gp, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return ["通用规格 %s 读不了：%s" % (gp, e)]
    try:
        mine = json.load(open(ms, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return ["本仓规格 %s 读不了：%s" % (ms, e)]
    gv = {p.get("name"): p.get("expect_version")
          for p in (gen.get("pins") or []) if p.get("kind") == "version"}
    mv = {p.get("name"): p.get("expect_version")
          for p in (mine.get("pins") or []) if p.get("kind") == "toolchain"}
    if not gv and not mv:
        problems.append("两份规格里都没有带版本串的 pin（零值守卫：这条对账没查东西）")
    for n in sorted(set(gv) | set(mv)):
        if n not in gv:
            problems.append("%s：通用规格里没有这个 pin（只有本仓那份有）" % n)
        elif n not in mv:
            problems.append("%s：本仓规格里没有这个 pin（只有通用那份有）" % n)
        elif gv[n] != mv[n]:
            problems.append("%s：版本串不一致 —— 通用 %s ≠ 本仓 %s（改一份忘另一份？）"
                            % (n, gv[n], mv[n]))
    return problems


def _run(cmd):
    """runner 注入点（自证在夹具上跑，不碰真 docker）。返回 (rc, stdout)。"""
    import subprocess
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def check(spec, run=_run):
    """纯逻辑：返回见证输出串。docker 命令按宿主现实要 sudo。"""
    pins = [p for p in (spec.get("pins") or [])
            if p.get("kind") == "toolchain" and p.get("provisioned")] + \
           [p for p in (spec.get("pins") or [])
            if p.get("kind") == "tree" and p.get("provisioned")]
    if not (spec.get("pins") or []):
        return "DRIFT: pins 为空（零值守卫：空断言面不是通过）"
    drifts, skips = [], []
    for p in pins:
        if p["kind"] == "toolchain":
            if p.get("probe"):
                # 宿主模式：直接跑探针命令（本仓 2026-10-13 加，docker 不可用时的真断言路径）
                rc, out = run(["sh", "-c", p["probe"]])
                if rc != 0 or not out:
                    skips.append("%s: 版本探针读不到（%s）" % (p["name"], p["probe"][:60]))
                    continue
                if p.get("expect_version") and p["expect_version"] not in out.splitlines()[0]:
                    drifts.append("%s: 版本漂移（期望 %s，实测 %s）"
                                  % (p["name"], p["expect_version"], out.splitlines()[0][:60]))
                continue
            rc, out = run(["sudo", "-E", "docker", "exec", "o113", "emcc", "--version"])
            if rc != 0 or not out:
                skips.append("%s: 读不到容器 emcc" % p["name"])
                continue
            if p.get("expect_version") and p["expect_version"] not in out.splitlines()[0]:
                drifts.append("%s: emcc 版本漂移（期望 %s，容器 %s）"
                              % (p["name"], p["expect_version"], out.splitlines()[0][:40]))
        else:
            if p.get("stamp_read"):
                # 宿主模式：直接读供给树 stamp（路径写在 pins 里，跑完命令逐字复跑）
                rc, out = run(["sh", "-c", p["stamp_read"]])
                if rc != 0 or not out:
                    skips.append("%s: 读不到供给树 stamp（未供给？%s）"
                                 % (p["name"], p["stamp_read"][:60]))
                    continue
            else:
                rc, out = run(["sudo", "-E", "docker", "exec", "o113",
                               "cat", os.path.join(p["container_path"], ".upstream-pin")])
                if rc != 0 or not out:
                    skips.append("%s: 读不到容器树 stamp（未供给？）" % p["name"])
                    continue
            parts = out.split()
            want_commit = (run(["git", "-C", os.path.join(REPO, p["submodule_path"]),
                                "rev-parse", "HEAD"])[1] or "?")
            if len(parts) < 3 or parts[2] != want_commit:
                drifts.append("%s: 容器树 commit=%s ≠ submodule pin=%s（供给后指针 bump 了？）"
                              % (p["name"], parts[2] if len(parts) > 2 else "?", want_commit[:12]))
            elif len(parts) > 3 and parts[3] not in ("0", ""):
                drifts.append("%s: 容器树带本地改动（dirty=%s）" % (p["name"], parts[3]))
    if drifts:
        return "DRIFT: " + "；".join(drifts)
    if skips:
        return "SKIP: " + "；".join(skips) + "（读不到 ⇒ 本次未核对，不是通过）"
    return "ok（%d 个 pin 全部一致）" % len(pins)


# ── C4 对账的自证（2026-10-10）：两份规格一致 / 不一致必须能分辨 ────────────────
CROSS_CASES = [
    ("正常：两份规格的同名 pin 版本串一致 ⇒ 不报",
     lambda: (lambda d: crosscheck(d + "/g.json", d + "/m.json") == [])(
         _cross_fixture("6.0.12", "6.0.12"))),
    ("★ 版本串不一致 ⇒ 必须报（改一份忘另一份）",
     lambda: any("不一致" in x for x in crosscheck(
         _cross_fixture("6.0.12", "5.0.7") + "/g.json",
         _cross_fixture("6.0.12", "5.0.7") + "/m.json"))),
    ("★ 版本 pin 只在通用规格里（本仓那份没登记）⇒ 必须报",
     lambda: (lambda d: any("本仓规格里没有" in x for x in crosscheck(d + "/g.json", d + "/m.json")))(
         _cross_fixture("6.0.12", ""))),
    ("★ 两份都没有版本 pin ⇒ 必须报（零值守卫：这条对账没查东西）",
     lambda: any("零值守卫" in x for x in crosscheck(
         _cross_fixture("", "") + "/g.json", _cross_fixture("", "") + "/m.json"))),
    ("★ 规格文件读不了 ⇒ 必须报",
     lambda: bool(crosscheck("/tmp/definitely-missing-9d3f.json", "/tmp/x.json"))),
]


def _cross_fixture(gv, mv, generic_only=True, mine_only=True):
    """造一对夹具规格（返回目录）。gv/mv = 各自的版本串（空串 = 不放该 pin）。"""
    import tempfile
    d = tempfile.mkdtemp(prefix="pins-cross-")
    gen = {"pins": [{"name": "emsdk", "kind": "version", "expect_version": gv}]} if gv else {"pins": []}
    mine = {"pins": [{"name": "emsdk", "kind": "toolchain", "expect_version": mv}]} if mv else {"pins": []}
    json.dump(gen, open(d + "/g.json", "w"))
    json.dump(mine, open(d + "/m.json", "w"))
    return d


def selftest():
    ok_spec = {"pins": [
        {"name": "octave", "kind": "tree", "provisioned": True,
         "submodule_path": "upstream/octave", "container_path": "/x/oct"},
        {"name": "emsdk", "kind": "toolchain", "provisioned": True, "expect_version": "5.0.7"}]}
    empty = {"pins": []}
    # ★ 宿主模式（本仓 2026-10-13 加）：stamp_read / probe 直接跑命令
    host_spec = {"pins": [
        {"name": "openmodelica", "kind": "tree", "provisioned": True,
         "submodule_path": "upstream/openmodelica",
         "container_path": "/x/om", "stamp_read": "cat /x/om/.upstream-pin"},
        {"name": "rust-nightly", "kind": "toolchain", "provisioned": True,
         "expect_version": "1.98.0-nightly", "probe": "echo 1.98.0-nightly (x)"}]}
    host_drift = {"pins": [
        {"name": "openmodelica", "kind": "tree", "provisioned": True,
         "submodule_path": "upstream/openmodelica",
         "container_path": "/x/om", "stamp_read": "echo openmodelica master DEADBEEF 0"},
        {"name": "rust-nightly", "kind": "toolchain", "provisioned": True,
         "expect_version": "1.98.0-nightly", "probe": "echo 1.97.0-nightly (x)"}]}

    def runner(stamp, emcc):
        """夹具 runner：cat 类调用回 stamp，emcc 类调用回版本串。"""
        def _r(cmd):
            joined = " ".join(cmd)
            if " cat " in joined or joined.endswith(" .upstream-pin"):
                return 0, stamp                          # 容器树 stamp（可被改坏）
            if "emcc" in joined:
                return 0, emcc
            return 0, "abc123"                           # git rev-parse = submodule 真实 pin
        return _r

    def host_runner(stamp, probe):
        """宿主模式夹具：stamp_read → stamp；probe → probe 输出；rev-parse → abc123。"""
        def _r(cmd):
            joined = " ".join(cmd)
            if "cat /x/om/.upstream-pin" in joined:
                return 0, stamp
            if "echo 1.98.0-nightly" in joined or "echo 1.97.0-nightly" in joined:
                return 0, probe
            return 0, "abc123"
        return _r

    def host_unread(cmd):
        """供给树读不到：stamp 命令失败（rc=1），版本探针照常 ⇒ 必须 SKIP 不是 ok。"""
        joined = " ".join(cmd)
        if "cat /x/om/.upstream-pin" in joined:
            return 1, ""
        if "echo 1.98.0-nightly" in joined:
            return 0, "1.98.0-nightly (x)"
        return 0, "abc123"

    good = runner("octave wasm/11.3.0 abc123 0",
                  "emcc (Emscripten gcc/clang-like replacement) 5.0.7 (x)")
    drift_commit = runner("octave wasm/11.3.0 DEADBEEF 0",
                          "emcc (Emscripten gcc/clang-like replacement) 5.0.7 (x)")
    drift_dirty = runner("octave wasm/11.3.0 abc123 3",
                         "emcc (Emscripten gcc/clang-like replacement) 5.0.7 (x)")
    drift_ver = runner("octave wasm/11.3.0 abc123 0",
                       "emcc (Emscripten gcc/clang-like replacement) 6.0.10 (x)")
    def unread(cmd):
        joined = " ".join(cmd)
        if " cat " in joined or joined.endswith(" .upstream-pin"):
            return 1, ""                      # 读不到 stamp ⇒ SKIP
        return 0, "emcc (Emscripten gcc/clang-like replacement) 5.0.7 (x)"

    cases = [
        ("stamp commit == pin 且干净 ⇒ ok",
         lambda: check(ok_spec, run=good) == "ok（2 个 pin 全部一致）"),
        ("★ 容器树 commit ≠ pin ⇒ 必须 DRIFT（供给后指针 bump）",
         lambda: check(ok_spec, run=drift_commit).startswith("DRIFT")),
        ("★ 容器树 dirty ⇒ 必须 DRIFT（有人手改了供给树）",
         lambda: check(ok_spec, run=drift_dirty).startswith("DRIFT")),
        ("★ emcc 版本漂移 ⇒ 必须 DRIFT",
         lambda: check(ok_spec, run=drift_ver).startswith("DRIFT")),
        ("★ 读不到合法 stamp ⇒ SKIP（明说未核对，不是通过）",
         lambda: check(ok_spec, run=unread).startswith("SKIP")),
        ("★ pins 为空 ⇒ 必须 DRIFT（零值守卫）",
         lambda: check(empty).startswith("DRIFT")),
        # ── ★ 宿主模式（docker 不可用时的真断言路径；本仓 2026-10-13 加）──────
        ("正常（宿主）：stamp 与 probe 都对 ⇒ ok",
         lambda: check(host_spec, run=host_runner("openmodelica master abc123 0",
                                                  "1.98.0-nightly (x)")) == "ok（2 个 pin 全部一致）"),
        ("★ 宿主模式：stamp commit ≠ pin ⇒ 必须 DRIFT（供给树是另一份拷贝）",
         lambda: check(host_drift, run=host_runner("openmodelica master DEADBEEF 0",
                                                   "1.98.0-nightly (x)")).startswith("DRIFT")),
        ("★ 宿主模式：probe 版本漂移 ⇒ 必须 DRIFT",
         lambda: check(host_drift, run=host_runner("openmodelica master abc123 0",
                                                   "1.97.0-nightly (x)")).startswith("DRIFT")),
        ("★ 宿主模式：stamp 读不到 ⇒ SKIP（明说未核对，不是通过）",
         lambda: check(host_spec, run=host_unread).startswith("SKIP")),
    ]
    cases = cases + CROSS_CASES
    bad = 0
    for name, fn in cases:
        ok = bool(fn())
        print("%s | %s" % ("PASS" if ok else "fail", name))
        bad += 0 if ok else 1
    print("=== witness-upstream-pin 自证：%d PASS / %d fail ===" % (len(cases) - bad, bad))
    return 1 if bad else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    spec_path = next((a for a in argv if not a.startswith("-")), DEFAULT_SPEC)
    try:
        spec = json.load(open(spec_path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("未启用（%s 读不了：%s）" % (spec_path, e))
        return 0
    # ★ C4 对账先跑（两份规格不一致时，下面那条见证的结论不可信）
    xp = crosscheck()
    if xp:
        print("DRIFT: 两份 pin 规格不一致 —— " + "；".join(xp))
        return 0
    print(check(spec))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


