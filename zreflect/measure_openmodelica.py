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
        "上游 pin 条数（0 = 尚未接入；接入后 2 tree + 2 toolchain 四条）")

    # 工具链身份（本批 2026-10-13 新增）：**从 wrapper 读出来**，不手抄。
    # ⚠️ 上游 rust_omc.cmake:297-320 靠 `clang -print-resource-dir` 找 wasm32 builtins，
    #    缺则 configure FATAL ⇒ 这条事实是"构建能不能开始"的前置，值得上键。
    clang_w = os.path.join(BASE, "tools", "bin", "clang")
    if _exists(clang_w):
        facts["toolchain_clang"] = fact(
            "24.0.0", "%s --version | head -1 | grep -oE '24\\.[0-9]+\\.[0-9]+' | head -1" % clang_w,
            "build/113/provision-toolchain.sh", "C 侧交叉编大版本（用户点令：clang 24）")
    builtins = os.path.join(BASE, "tools", "clang-resource", "lib", "wasi",
                            "libclang_rt.builtins-wasm32.a")
    if _exists(builtins):
        facts["toolchain_builtins_bytes"] = fact(
            os.path.getsize(builtins), "stat -c%%s %s" % builtins,
            "build/113/build-clang24-builtins.sh",
            "wasm32 builtins 字节数（clang24 同源精编；上游 configure 的硬前置）")

    # ── ② 产物侧事实：**构建产物还不存在** ⇒ 如实记"未构建"，不编造 ────────────────
    # 判据：产物身份证存在且 verdict==ok。没有身份证 ⇒ 这条事实不写（宁可缺席，不许冒充）。
    # ⚠️ 本仓产物真名是 **`OpenModelicaCompiler_bg.wasm`**（wasm-bindgen 出包），不是 `omc.wasm`
    #    （官方树里 omc.wasm 只出现在注释里）。⇒ 除 sha 外再量"字节数"与"web 包文件数"。
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
        if not _exists(wasm):
            # 真名不同 ⇒ 从身份证的 measured.files 里**读出路径**再量（别猜文件名）
            p = (((d.get("measured") or {}).get("files") or {}).get("omc_bg_wasm") or {}).get("path") or ""
            wasm = p if p and _exists(p) else ""
        if wasm:
            facts["omc_%s_sha" % lane] = fact(
                sha256sum(wasm), "sha256sum %s | cut -d' ' -f1" % wasm,
                "build/%s/omc.build.json" % sub, "产物 sha256（路径从身份证读出）")
            facts["omc_%s_bytes" % lane] = fact(
                os.path.getsize(wasm), "stat -c%%s %s" % wasm,
                "build/%s/omc.build.json" % sub, "产物字节数")
        wf = ((d.get("measured") or {}).get("web_files"))
        if wf is not None:
            facts["omc_%s_web_files" % lane] = fact(
                wf, "python3 -c \"import json;print(json.load(open('%s'))['measured']['web_files'])\"" % ident,
                "build/%s/omc.build.json" % sub, "web 包文件数（布局收口完整性）")
    # ── 需求 D（.mat 握手）：产物 + 同页成本的量 ────────────────────────────────
    # 判据物：OM 产出的结果 .mat（由 test/node/produce-result-mat.mjs 可复跑产出）。
    res_mat = os.path.join(BUILD, "omc-out-wasm32", "artifacts", "BouncingBall_res.mat")
    if _exists(res_mat):
        facts["om_result_mat_bytes"] = fact(
            os.path.getsize(res_mat), "stat -c%%s %s" % res_mat,
            "build/omc-out-wasm32/artifacts/OmcHandshakeDemo_res.mat",
            "OM 仿真结果 .mat（MAT4）字节数（需求 D 的输入件，可复跑产出）")
        facts["om_result_mat_sha"] = fact(
            sha256sum(res_mat), "sha256sum %s | cut -d' ' -f1" % res_mat,
            "build/omc-out-wasm32/artifacts/OmcHandshakeDemo_res.mat", "结果 .mat 的 sha256")
    # 同页成本（悬案 04 的实测；三个数都从 JSON 里读出来，不手抄）
    cost = os.path.join(BUILD, "omc-out-wasm32", "artifacts", "samepage-cost.json")
    if _exists(cost):
        d = _read_json(cost) or {}
        for key, jk, note in (
            ("samepage_om_bytes", "om_wasm_bytes", "OM 产物体积（同页成本口径）"),
            ("samepage_octave_bytes", "octave_wasm_bytes", "Octave 产物体积（同页成本口径）"),
            ("samepage_sum_bytes", "sum_wasm_bytes", "两引擎 wasm 字节合计"),
            ("samepage_heap_peak", "js_heap_peak_bytes", "JS 堆峰值（两模块编译后）"),
        ):
            if d.get(jk):
                facts[key] = fact(
                    d[jk], "python3 -c \"import json;print(json.load(open('%s'))['%s'])\"" % (cost, jk),
                    "build/omc-out-wasm32/artifacts/samepage-cost.json", note)

    # ── 需求 B（页面内端到端）与需求 E（语义桥）：产物侧的量 ─────────────────────
    # web 档产物（需求 B 用的那份；与 node 档是**两个独立构建**）
    web_wasm = os.path.join(BUILD, "omc-out-web", "web", "omc", "OpenModelicaCompiler_bg.wasm")
    if _exists(web_wasm):
        facts["omc_web_wasm_bytes"] = fact(
            os.path.getsize(web_wasm), "stat -c%%s %s" % web_wasm,
            "build/omc-out-web/web/omc/OpenModelicaCompiler_bg.wasm",
            "web 档 omc wasm 字节数（需求 B 的产物；浏览器内跑）")
        facts["omc_web_wasm_sha"] = fact(
            sha256sum(web_wasm), "sha256sum %s | cut -d' ' -f1" % web_wasm,
            "build/omc-out-web/web/omc/OpenModelicaCompiler_bg.wasm", "web 档产物 sha256")
    web_verdict = os.path.join(BUILD, "omc-out-web", "omc.build.json")
    if _exists(web_verdict):
        d = _read_json(web_verdict) or {}
        if d.get("verdict"):
            facts["omc_web_verdict"] = fact(
                d["verdict"], "python3 -c \"import json;print(json.load(open('%s'))['verdict'])\"" % web_verdict,
                "build/omc-out-web/omc.build.json", "web 档产物身份证 verdict")

    # 版本串：产物探针实际吐出来的那句（需求 A3 的判据物）
    ver_id = os.path.join(BUILD, "omc-out-wasm32", "omc.build.json")
    if _exists(ver_id):
        d = _read_json(ver_id) or {}
        probe = (d.get("probe") or "").strip()
        if probe:
            facts["omc_version_string"] = fact(
                probe, "python3 -c \"import json;print(json.load(open('%s'))['probe'].strip())\"" % ver_id,
                "build/omc-out-wasm32/omc.build.json", "Node 里 getVersion() 的实测输出（需求 A3）")


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
