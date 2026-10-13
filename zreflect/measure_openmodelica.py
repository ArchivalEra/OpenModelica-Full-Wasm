#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **本仓的数据层**（Einfacht 机制层之上的"你的部分"）。

Einfacht 的 `zreflect/facts.py` 只提供**机制**（守卫 / 渲染 / 收尾）；
这里放本仓真正要量的东西：产物身份证、三线 sha、构建输入、上游 pin 状态……全部照旧
（每条带复跑命令 + 出处）。

⚠️ 本模块**自包含**：不 import 姊妹仓的任何东西（那是另一棵仓）。

⚠️ **本仓当前状态：骨架期**（2026-10-13 建仓）。还没有构建产物 ⇒ 产物类事实
**量不到**。按本仓事实纪律（§5.5「断言有生命周期」）：**量不到就如实报"未构建"，
不许编造、也不许用 0 冒充"已量"**（零值守卫要能区分"量到 0"与"没得量"）。
"""
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import fact                                    # noqa: E402
from gate import module_meta                               # noqa: E402

# ★ C5：本仓数据层也必须在平台名册里声明自己，否则 registry 报 undeclared。
#   selftest=False：它是**数据**（量什么、怎么量），机制的自证在 zreflect/ 上游那批。
MODULE = module_meta("本仓数据层", "量本仓的产物/三线/上游 pin（数据 vs 机制分离）", selftest=False)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 产物根（待建；与姊妹仓的 /mnt/hdd/octave-wasm-build 平级）
BASE = os.environ.get("OMC_BASE", "/mnt/hdd/openmodelica-wasm-build")
BUILD = os.path.join(BASE, "build")          # 构建输出根（待建）
OUT = os.path.join(REPO, "build", "FACTS.json")


def sha256sum(path, chunk=1 << 20):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _exists(p):
    return os.path.exists(p)


def _read_json(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def measure():
    """量一遍全部事实。守卫与写盘由 zreflect/facts.py 的平台负责。"""
    facts = {}

    # ── ① 仓骨架期的自证事实（这些**现在就能量**，且每条都有复跑命令）────────────
    # 三线分支存在性：一线一架构（用户点令）—— 那是本仓的硬约束，先把它变成可量的事。
    def _branches():
        try:
            out = subprocess.run(["git", "branch", "--list", "--format=%(refname:short)"],
                                 cwd=REPO, capture_output=True, text=True, timeout=20).stdout
            return sorted(b.strip() for b in out.splitlines() if b.strip())
        except Exception:
            return []

    br = _branches()
    want = ["IllegalPerformance", "master", "wasm32"]
    facts["lane_branches_present"] = fact(
        sum(1 for w in want if w in br),
        # ⚠️ 用 awk 不用 grep -c：`grep -c` 零命中**退出 1** ⇒ 复跑闸门把它当"命令报错"。
        #    这条实测踩到过（建仓第一次提交时，分支还没 refs ⇒ 0 命中 ⇒ rc=1 ⇒ 提交被拦）。
        "git -C %s branch --list --format='%%(refname:short)' | "
        "awk '/^(master|wasm32|IllegalPerformance)$/{n++} END{print n+0}'" % REPO,
        "build/FACTS.json", "三线分支齐备数（一线一架构：master=wasm64 / wasm32 / IllegalPerformance）")

    # 白名单规则数（白名单仓库的硬约束）
    gi = os.path.join(REPO, ".gitignore")
    n_allow = 0
    if os.path.isfile(gi):
        with open(gi, encoding="utf-8", errors="replace") as fh:
            n_allow = sum(1 for l in fh if l.startswith("!"))
    facts["whitelist_rules"] = fact(
        n_allow, "grep -c '^!' %s/.gitignore" % REPO, "build/FACTS.json",
        "白名单放行规则数（新增文件必须同步加白线，否则 pre-commit 拒）")

    # 三份经验文档存在性（用户点令：需求书 + Einfacht 接入 + fork 管线与经验）
    docs = {"REQUIREMENTS": "docs/REQUIREMENTS.md",
            "EINFACHT-INTEGRATION": "docs/EINFACHT-INTEGRATION.md",
            "FORK-PIPELINE-AND-LESSONS": "docs/FORK-PIPELINE-AND-LESSONS.md"}
    n_docs = sum(1 for _, r in docs.items() if _exists(os.path.join(REPO, r)))
    facts["docs_present"] = fact(
        n_docs, "ls %s/docs/REQUIREMENTS.md %s/docs/EINFACHT-INTEGRATION.md "
        "%s/docs/FORK-PIPELINE-AND-LESSONS.md 2>/dev/null | wc -l" % (REPO, REPO, REPO),
        "build/FACTS.json", "三份经验文档齐备数（用户点令）")

    # 上游 pin 规格存在性（fork 管线的根）
    pins = _read_json(os.path.join(REPO, "build", "upstream-pins.json"))
    n_pins = len((pins or {}).get("pins", [])) if pins else 0
    facts["upstream_pins"] = fact(
        n_pins, "python3 -c \"import json,sys;d=json.load(open('%s/build/upstream-pins.json'));"
        "print(len(d['pins']))\"" % REPO, "build/FACTS.json",
        "上游 pin 条数（0 = 尚未接入；接入后 OM/3rdParty/OMBootstrapping 三条）")

    # ── ② 产物侧事实：**构建产物还不存在** ⇒ 如实记"未构建"，不编造 ────────────────
    # 判据：产物身份证存在且 verdict==ok。没有身份证 ⇒ 这条事实不写（宁可缺席，不许冒充）。
    for lane, sub in (("w64", "omc-out-w64"), ("wasm32", "omc-out-wasm32"),
                      ("ilperf", "omc-out-ilperf")):
        ident = os.path.join(BUILD, sub, "omc.build.json")
        if not _exists(ident):
            continue                       # 未构建：**不写这条**（缺席 ≠ 0）
        d = _read_json(ident) or {}
        facts["omc_%s_verdict" % lane] = fact(
            d.get("verdict"), "python3 -c \"import json;print(json.load(open('%s')).get('verdict'))\"" % ident,
            "build/%s/omc.build.json" % sub, "产物身份证 verdict（只有 ok 才可部署）")
        wasm = os.path.join(BUILD, sub, "omc.wasm")
        if _exists(wasm):
            facts["omc_%s_sha" % lane] = fact(
                sha256sum(wasm), "sha256sum %s | cut -d' ' -f1" % wasm,
                "build/%s/omc.wasm" % sub, "产物 sha256")

    # ── ③ 构建输入/工具链：能从产物或配置里**读出来**的才写 ─────────────────────────
    # ⚠️ 本仓工具链是 **Rust + wasm32-wasip1**（官方 CMake 目标），**不是 emsdk**——
    #    这条与姊妹仓不同，别照抄那边的 emcc 事实。
    for lane, sub in (("w64", "omc-out-w64"), ("wasm32", "omc-out-wasm32")):
        ident = os.path.join(BUILD, sub, "omc.build.json")
        d = _read_json(ident)
        if d and isinstance(d.get("tool"), dict):
            facts["omc_%s_rustc" % lane] = fact(
                d["tool"].get("rustc"),
                "python3 -c \"import json;print(json.load(open('%s'))['tool']['rustc'])\"" % ident,
                "build/%s/omc.build.json" % sub, "工具链身份（从产物身份证读，不手抄）")

    # ── ④ 回归汇总：sweep-logs 里最近一次全绿（与姊妹仓同规则）────────────────────
    logs = os.path.join(BASE, "sweep-logs")
    if os.path.isdir(logs):
        cand = []
        for d in sorted(os.listdir(logs), reverse=True):
            try:
                n = sum(1 for f in os.listdir(os.path.join(logs, d))
                        if f.startswith("accept-") and f.endswith(".log"))
            except OSError:
                continue
            if n >= 5:
                cand.append(d)
        for d in cand:
            suites = passes = fails = 0
            for f in glob.glob(os.path.join(logs, d, "accept-*.log")):
                try:
                    txt = open(f, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                m = re.findall(r"=== *(\d+) PASS / (\d+) FAIL *===", txt)
                if m:
                    suites += 1
                    passes += int(m[-1][0])
                    fails += int(m[-1][1])
            if suites and fails == 0:
                facts["accept_suites"] = fact(
                    suites, "数 %s/%s 里带汇总行的套件（且 0 FAIL）" % (logs, d),
                    "sweep-logs/%s" % d, "最近一次**全绿**扫描的套件数")
                facts["accept_pass"] = fact(
                    passes, "同上，把每个套件的 PASS 相加", "sweep-logs/%s" % d)
                break

    return facts
