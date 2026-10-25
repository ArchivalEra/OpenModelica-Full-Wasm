#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **MSL content-list 出表自证**（mail/017 §3 的判据件）
Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later

本仓是 MSL 的**出表方**（producer）。表 = `build/extra-content/content-list.json`；
校验器产地 = 宿主 `Octave-Full-Wasm/build/extra-content/validate-content-list.py`
（**只读调用，不写宿主任一文件**）。

判据（三档齐备）：
  ① 正常不报：本仓表过宿主校验器（producer 态 + site 态都 ok）；
  ② 该报的必须报：五类形状违规逐条必须红（sha 格式 / 空表 / 未知 form / 非法 consumer /
     站点态绝对 URL）；
  ③ 空输入必须报：空表、表文件不存在 ⇒ 红。

★ 为什么还要自己包一层（不直接跑宿主校验器）：宿主校验器在**另一个仓**，
   CI 上没有它（产物树/邻仓不进本仓 git）⇒ 本仓 CI 跑不动它。本件做两件事：
   · 若宿主校验器在盘 ⇒ 真跑它（最忠实）；
   · 若不在 ⇒ 跑**本地等价判据**（同一 schema 的必填/词表/hex/同源相对），
     并**明说**用的是本地判据（不许假装跑过宿主件）。

用法：python3 build/113/check-msl-content-list.py [--selftest]
退出码：0 = 全过；1 = 判据红；2 = 用法/环境。
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIST = os.path.join(REPO, "build", "extra-content", "content-list.json")
HOST_VALIDATOR = "/mnt/hdd/zcode-projects/Octave-Full-Wasm/build/extra-content/validate-content-list.py"
PRODUCER = "openmodelica-full-wasm"
FORMS = {"pkg", "tree", "oct", "octdir", "file", "js"}
CONSUMERS = {"octave", "omc"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def local_problems(doc, site_mode=False):
    """本地等价判据（宿主校验器不在盘时用）。返回问题列表（空 = 过）。"""
    out = []
    if not isinstance(doc, dict):
        return ["表不是对象"]
    if doc.get("schema") != 2:
        out.append("schema 必须是 2（得到 %r）" % doc.get("schema"))
    if not doc.get("octave"):
        out.append("缺 octave")
    prod = doc.get("producer")
    if not isinstance(prod, dict) or not prod.get("id"):
        out.append("缺 producer.id（出表方自述）")
    elif prod["id"] != PRODUCER:
        out.append("producer.id 不符：期望 %r 得到 %r" % (PRODUCER, prod["id"]))
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        return out + ["entries 必须是非空数组（空表不是通过 —— 零值守卫）"]
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            out.append("条目[%d] 不是对象" % i)
            continue
        tag = "条目[%d] %r" % (i, e.get("name"))
        for f in ("name", "version", "sha256", "url"):
            if not e.get(f):
                out.append("%s 缺 %s" % (tag, f))
        sha = str(e.get("sha256") or "")
        if sha and not HEX64.match(sha):
            out.append("%s sha256 不是 64 位小写 hex（得到 %r）" % (tag, sha[:12]))
        form = e.get("form")
        if form is not None and form not in FORMS:
            out.append("%s form=%r 不在词表 %s 里" % (tag, form, sorted(FORMS)))
        cons = e.get("consumer")
        if cons is not None:
            if not isinstance(cons, list):
                out.append("%s consumer 必须是数组" % tag)
            else:
                bad = [c for c in cons if c not in CONSUMERS]
                if bad:
                    out.append("%s consumer 含未知值 %r（词表 %s）"
                               % (tag, bad[0], sorted(CONSUMERS)))
        url = str(e.get("url") or "")
        if site_mode and url and re.match(r"^[a-z]+://", url):
            out.append("%s 站点态 url 是绝对地址（%s…）⇒ 必须同源相对" % (tag, url[:40]))
    return out


def run_host_validator(path, site_mode=False):
    """真跑宿主校验器。返回 (rc, stdout)；不在盘 ⇒ (None, 说明)。"""
    if not os.path.exists(HOST_VALIDATOR):
        return None, "宿主校验器不在盘（%s）⇒ 用本地等价判据" % HOST_VALIDATOR
    cmd = ["python3", HOST_VALIDATOR, "--list", path, "--producer", PRODUCER]
    if site_mode:
        cmd.append("--site")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout + r.stderr).strip()


def judge(path, site_mode=False):
    """一条判据：返回 (ok, 说明)。宿主件在盘就跑它，否则本地等价。"""
    rc, msg = run_host_validator(path, site_mode)
    if rc is not None:
        return rc == 0, "宿主校验器 rc=%d：%s" % (rc, msg.splitlines()[0] if msg else "")
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return False, "读不到/解析不了：%s" % e
    probs = local_problems(doc, site_mode)
    return (not probs), ("本地等价判据：%s" % (probs[0] if probs else "ok"))


def _selftest():
    ok, bad = [], []

    def t(name, cond):
        (ok if cond else bad).append(name)

    good = {
        "schema": 2, "octave": "11.3.0",
        "producer": {"id": PRODUCER, "pin": "release:v0"},
        "entries": [{
            "name": "msl", "version": "4.1.0+maint.om", "form": "file",
            "sha256": "a" * 64, "url": "assets/msl/msl.zip", "size": 1,
            "content": [], "consumer": ["omc"], "role": "package", "deps": [],
        }],
    }

    def with_(mut):
        import copy
        d = copy.deepcopy(good)
        mut(d)
        return d

    # ① 正常不报
    t("正常：合法表 ⇒ 无问题", local_problems(good) == [])
    t("正常：站点态同源相对 url ⇒ 无问题", local_problems(good, site_mode=True) == [])
    # ② 该报的必须报（五类形状违规）
    t("★ sha 格式非法 ⇒ 必须报",
      any("sha256" in x for x in local_problems(with_(lambda d: d["entries"][0].update(sha256="nope")))))
    t("★ 未知 form ⇒ 必须报",
      any("form=" in x for x in local_problems(with_(lambda d: d["entries"][0].update(form="bogus")))))
    t("★ 非法 consumer ⇒ 必须报",
      any("consumer" in x for x in local_problems(with_(lambda d: d["entries"][0].update(consumer=["matlab"])))))
    t("★ 站点态绝对 URL ⇒ 必须报",
      any("绝对地址" in x for x in local_problems(
          with_(lambda d: d["entries"][0].update(url="https://x/y.zip")), site_mode=True)))
    t("★ producer.id 不符 ⇒ 必须报",
      any("producer.id" in x for x in local_problems(with_(lambda d: d["producer"].update(id="other")))))
    t("★ 缺 sha ⇒ 必须报",
      any("缺 sha256" in x for x in local_problems(with_(lambda d: d["entries"][0].pop("sha256")))))
    # ③ 空输入必须报（零值守卫）
    t("★ 空表 ⇒ 必须报", any("空表" in x for x in local_problems({"schema": 2, "octave": "x",
                                                             "producer": {"id": PRODUCER},
                                                             "entries": []})))
    t("★ 表不是对象 ⇒ 必须报", local_problems(None) != [])
    t("★ 文件不存在 ⇒ 判据必须红", judge("/tmp/definitely-missing-content-list.json")[0] is False)

    print("PASS | " + "\nPASS | ".join(ok))
    for b in bad:
        print("fail | " + b)
    print("=== check-msl-content-list 自证：%d PASS / %d fail ===" % (len(ok), len(bad)))
    return not bad


def main(argv):
    if argv and argv[0] == "--selftest":
        return 0 if _selftest() else 1
    if argv:
        print("用法: check-msl-content-list.py [--selftest]", file=sys.stderr)
        return 2
    ok1, msg1 = judge(LIST)
    ok2, msg2 = judge(LIST, site_mode=True)
    print("  producer 态：%s —— %s" % ("ok" if ok1 else "FAIL", msg1))
    print("  site 态    ：%s —— %s" % ("ok" if ok2 else "FAIL", msg2))
    if ok1 and ok2:
        print("content-list 出表自证：OK（本仓 %s 的表两种模式都过）" % PRODUCER)
        return 0
    print("content-list 出表自证：FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
