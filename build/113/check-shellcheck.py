#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **shell 面 shellcheck 闸门**（电话网工具落实批次的常驻判据件）
Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later

为什么有它：2026-11-13 电话网二轮广播点名 omc「gates/selftest 的 sh 壳跑 shellcheck，
进 gates-selftest.sh 名单并补 --selftest 三类用例」。一次性修复不常驻 ⇒ 壳还会再坏。
本闸门把 shellcheck 变成本仓提交路径上的常驻判据：**任何 shell 面出现新 finding ⇒ 红**。

判据（逐条）：
  ① shellcheck 在盘（不在 ⇒ 环境问题 rc=2，不是结论——"量不到"不是"不存在"）；
  ② `git ls-files '*.sh'` + 两个无后缀钩子壳（reflect-hooks/pre-commit、pre-push）
     构成 shell 面（**读出来**，不手抄清单）；
  ③ 每个文件跑 shellcheck（severity=style，本仓基线：零 finding）；
  ④ 任何输出含 `SC\\d+ \\(` ⇒ 红，点名文件、行号、码。

为什么收 style 级：基线是在 style 级下打到 0 的（37 → 0），
收 warning 级等于把基线偷偷放松——不许。

用法：
  python3 build/113/check-shellcheck.py                # 全量扫（提交路径判据）
  python3 build/113/check-shellcheck.py --selftest     # 三类用例自证
退出码：0 = 零 finding；1 = 有 finding；2 = 环境（shellcheck 不在盘）。
"""
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FINDING = re.compile(r"SC\d+ \(")
# 无后缀 shell 壳（git ls-files '*.sh' 看不见它们；名单变更时这里跟着改）
EXTRA_HOOKS = ["reflect-hooks/pre-commit", "reflect-hooks/pre-push"]


def shell_surface(repo):
    """shell 面 = git ls-files '*.sh' + 无后缀钩子壳。返回存在的文件列表（读出来，不猜）。"""
    out = subprocess.run(["git", "ls-files", "*.sh"], cwd=repo,
                         capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError("git ls-files 失败：" + (out.stderr or "").strip()[:200])
    files = [ln for ln in out.stdout.splitlines() if ln.strip()]
    for rel in EXTRA_HOOKS:
        if os.path.isfile(os.path.join(repo, rel)):
            files.append(rel)
    return files


def scan(repo, files):
    """逐文件跑 shellcheck（style 级）。返回 (finding 列表, shellcheck 可用性)。"""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    present = [f for f in files if os.path.isfile(os.path.join(repo, f))]
    out = subprocess.run(["shellcheck", "--severity=style"] + present,
                         cwd=repo, capture_output=True, text=True, timeout=300, env=env)
    findings = []
    for ln in out.stdout.splitlines():
        m = FINDING.search(ln)
        if m:
            findings.append(ln)
    return findings, True


def _have_shellcheck():
    """shellcheck 在盘判定。不用 `which`（uv Python 无外部 which 二进制），用 shutil.which。"""
    import shutil
    return shutil.which("shellcheck") is not None


def judge(repo):
    """返回 (ok, 摘要, 明细)。shellcheck 不在盘 ⇒ (False, 环境, [])，rc 由调用方定 2。"""
    if not _have_shellcheck():
        return False, "环境：shellcheck 不在盘（'量不到'不是'不存在'——装上再跑）", []
    files = shell_surface(repo)
    if not files:
        return False, "shell 面为空（git ls-files 零命中）——这本身就是异常", []
    findings, _ = scan(repo, files)
    if findings:
        return False, "shellcheck %d 条 finding（基线：零）" % len(findings), findings
    return True, "shellcheck 零 finding（%d 个 shell 面，style 级）" % len(files), []


def _selftest():
    """三类用例：正常不报 / 该报的必须报 / 空输入必须报。"""
    ok, bad = [], []

    def t(label, cond):
        (ok if cond else bad).append(label)

    # ① 正常不报：本仓真 shell 面 ⇒ 零 finding（这是基线本身，反向断言见 ②③）
    good, msg, _ = judge(REPO)
    t("正常：本仓 shell 面（%d 个文件）⇒ 零 finding" %
      len(shell_surface(REPO)), good)
    # ② 该报的必须报：造一个真带 finding 的临时 sh（cat 未加引号展开，SC2015 肯定红）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        badsh = os.path.join(td, "bad.sh")
        with open(badsh, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nV=$(ls /tmp | head -1)\n[ -n \"$V\" ] && echo yes || echo no\n")
        out = subprocess.run(["shellcheck", "--severity=style", badsh],
                             capture_output=True, text=True, timeout=60)
        t("★ 该报：SC2015 壳必须被 finder 识别（对临时坏壳）", FINDING.search(out.stdout) is not None)
        # ③ 空输入必须报：空文件列表与缺 shellcheck 两种空态都不得当"通过"
        findings, _ = scan(REPO, [])
        t("★ 空输入：空 shell 面 ⇒ 零 finding 但不得当'通过'（judge 层单独拦）",
          findings == [])
        t("★ 空输入：judge 对空 shell 面 ⇒ 必须红（零值守卫：空面不是供给成功）",
          _judge_empty_dir(td)[0] is False)
    # ④ 环境：shellcheck 不在盘 ⇒ judge 红且摘要点名"环境"（PATH 抽空模拟）
    env_bak = os.environ.get("PATH")
    os.environ["PATH"] = "/nonexistent-for-selftest"
    try:
        r = judge(REPO)
        t("★ 环境：shellcheck 不在盘 ⇒ 红且摘要点名（不是静默绿）", r[0] is False and "环境" in r[1])
    finally:
        os.environ["PATH"] = env_bak
    # ⑤ 反向：finder 正则对无 finding 输出不得误报
    t("反向：无 SC 码的普通输出行 ⇒ finder 不误报", FINDING.search("  done\n") is None)

    for x in ok:
        print("PASS | " + x)
    for x in bad:
        print("fail | " + x)
    print("=== check-shellcheck 自证：%d PASS / %d fail ===" % (len(ok), len(bad)))
    return not bad


def _judge_empty_dir(td):
    """空目录当 repo：git ls-files 在非 git 目录会失败 ⇒ shell_surface 抛 RuntimeError。
    judge 层要求对'面为空/环境坏'报红，这里显式构造空态走 judge 的空面分支。"""
    import types
    saved = shell_surface
    try:
        shell_surface.__globals__["shell_surface"] = lambda repo: []
        r = judge(td)
    finally:
        shell_surface.__globals__["shell_surface"] = saved
    return r


def main(argv):
    if argv and argv[0] == "--selftest":
        return 0 if _selftest() else 1
    if argv:
        print("用法: check-shellcheck.py [--selftest]", file=sys.stderr)
        return 2
    good, msg, details = judge(REPO)
    if not _have_shellcheck():
        print("FATAL: " + msg)
        return 2
    print("  " + msg)
    for d in details:
        print("    " + d)
    print("check-shellcheck：%s" % ("OK（零 finding）" if good else "FAIL"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
