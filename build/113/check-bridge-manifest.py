#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **E 线桥生产交付清单闸门**（mail/107 §4 第 1 问的判据件）
Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later

为什么需要：mail/107 实测出「Octave 产品里 omc_* 不存在」——我方验收是**运行时注入**
（`accept-omc-bridge.mjs` 逐件 injectFile + addpath），不是产品装配。
披露这类缺口的前提是**清单本身可查**：清单漏一件、多一件、内容漂了，宿主播过去的
就是错的。本闸门把 `bridge/manifest.json` 与磁盘真值逐件对账。

判据（逐条 fail-closed）：
  ① 清单里的每个文件在 `bridge/` 存在，且 bytes / sha256 与磁盘一致；
  ② 磁盘上每个 `bridge/*.m` 与 `bridge/*.js` 都在清单里（**多出来 = 没人装**）；
  ③ 件数 ≥ 12（11 件 .m + 1 件宿主侧 .js）——零值守卫：清单空不是通过；
  ④ 协议路径三项齐全且**互不相同**（request/response/seq，两侧写死同名常量）。

用法：python3 build/113/check-bridge-manifest.py [--selftest]
退出码：0 = 一致；1 = 不一致（逐条点名）；2 = 环境（清单/目录不在）。
"""
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE = os.path.join(REPO, "bridge")
MANIFEST = os.path.join(BRIDGE, "manifest.json")
MIN_ENTRIES = 12
PROTOCOL_KEYS = ("request", "response", "seq")


def disk_files():
    if not os.path.isdir(BRIDGE):
        return None
    return sorted(f for f in os.listdir(BRIDGE) if f.endswith((".m", ".js")))


def check(manifest, files, root=BRIDGE):
    """纯逻辑（自证注入 manifest/files/root）。返回问题列表（空 = 一致）。"""
    probs = []
    if not isinstance(manifest, dict):
        return ["清单不是对象"]
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return ["清单缺 entries 数组"]
    if not entries:
        return ["清单 entries 为空（零值守卫：空清单不是通过）"]
    if files is None:
        return ["bridge/ 目录不存在（环境问题，不是结论）"]
    listed = {}
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or not e.get("file"):
            probs.append("条目[%d] 缺 file" % i)
            continue
        listed[e["file"]] = e
    # ① 清单 → 磁盘
    for name, e in sorted(listed.items()):
        p = os.path.join(root, name)
        if not os.path.exists(p):
            probs.append("清单里的 `%s` 在磁盘上不存在（宿主播过去会缺件）" % name)
            continue
        b = open(p, "rb").read()
        if e.get("bytes") != len(b):
            probs.append("`%s` bytes 不符：清单 %r vs 磁盘 %d" % (name, e.get("bytes"), len(b)))
        want = str(e.get("sha256") or "")
        got = hashlib.sha256(b).hexdigest()
        if want != got:
            probs.append("`%s` sha256 不符：清单 %s… vs 磁盘 %s…" % (name, want[:12], got[:12]))
    # ② 磁盘 → 清单（多出来的件没人装）
    for f in files:
        if f not in listed:
            probs.append("磁盘上有 `%s` 但清单没有（宿主不会装它）" % f)
    # ③ 件数下限
    if len(entries) < MIN_ENTRIES:
        probs.append("清单只有 %d 件，少于下限 %d（11 件 .m + 1 件宿主侧 .js）"
                     % (len(entries), MIN_ENTRIES))
    # ④ 协议路径
    pp = manifest.get("protocol_paths") or {}
    vals = []
    for k in PROTOCOL_KEYS:
        v = str(pp.get(k) or "").strip()
        if not v:
            probs.append("协议路径缺 `%s`（两侧写死同名常量，缺一个桥就断）" % k)
        else:
            vals.append(v)
    if len(vals) == len(PROTOCOL_KEYS) and len(set(vals)) != len(vals):
        probs.append("协议路径有重复（request/response/seq 必须是三个不同文件）")
    return probs


def _selftest():
    ok, bad = [], []

    def t(name, cond):
        (ok if cond else bad).append(name)

    files = ["a.m", "b.js"]
    good = {"schema": 1, "protocol_paths": {"request": "/tmp/r", "response": "/tmp/s", "seq": "/tmp/q"},
            "entries": [{"file": f, "bytes": 1, "sha256": "x"} for f in files]}
    # 用真磁盘做夹具（写临时目录）
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for f in files:
            open(os.path.join(d, f), "wb").write(b"Z")
        sha = hashlib.sha256(b"Z").hexdigest()
        g = {"schema": 1,
             "protocol_paths": {"request": "/tmp/r", "response": "/tmp/s", "seq": "/tmp/q"},
             "entries": [{"file": f, "bytes": 1, "sha256": sha} for f in files] + [
                 {"file": "c%d.m" % i, "bytes": 1, "sha256": sha} for i in range(10)]}
        for i in range(10):
            open(os.path.join(d, "c%d.m" % i), "wb").write(b"Z")
        allf = sorted(files + ["c%d.m" % i for i in range(10)])

        # ① 正常不报
        t("正常：清单与磁盘逐件一致 ⇒ 无问题", check(g, allf, root=d) == [])
        # ② 该报的必须报
        t("★ 清单缺磁盘上的件 ⇒ 必须报",
          any("清单没有" in x for x in check(g, allf + ["extra.m"], root=d)))
        t("★ 清单里有磁盘没有的件 ⇒ 必须报", any("不存在" in x for x in
                                            check({**g, "entries": g["entries"] + [
                                                {"file": "ghost.m", "bytes": 1, "sha256": sha}]}, allf, root=d)))
        t("★ sha 不符 ⇒ 必须报", any("sha256 不符" in x for x in
                                  check({**g, "entries": [dict(g["entries"][0], sha256="0"*64)] + g["entries"][1:]},
                                        allf, root=d)))
        t("★ bytes 不符 ⇒ 必须报", any("bytes 不符" in x for x in
                                    check({**g, "entries": [dict(g["entries"][0], bytes=99)] + g["entries"][1:]},
                                          allf, root=d)))
        t("★ 件数不足下限 ⇒ 必须报", any("少于下限" in x for x in check(
            {**g, "entries": g["entries"][:2]}, files, root=d)))
        t("★ 协议路径缺一项 ⇒ 必须报", any("协议路径缺" in x for x in check(
            {**g, "protocol_paths": {"request": "/tmp/r", "response": "/tmp/s"}}, allf, root=d)))
        t("★ 协议路径重复 ⇒ 必须报", any("重复" in x for x in check(
            {**g, "protocol_paths": {"request": "/tmp/r", "response": "/tmp/r", "seq": "/tmp/q"}}, allf, root=d)))
        # ③ 空输入必须报
        t("★ 空 entries ⇒ 必须报", check({"entries": []}, []) != [])
        t("★ 清单非对象 ⇒ 必须报", check(None, []) != [])
        t("★ bridge 目录不在 ⇒ 必须报（环境）", check(g, None, root=d) != [])

    print("PASS | " + "\nPASS | ".join(ok))
    for b in bad:
        print("fail | " + b)
    print("=== check-bridge-manifest 自证：%d PASS / %d fail ===" % (len(ok), len(bad)))
    return not bad


def main(argv):
    if argv and argv[0] == "--selftest":
        return 0 if _selftest() else 1
    if argv:
        print("用法: check-bridge-manifest.py [--selftest]", file=sys.stderr)
        return 2
    files = disk_files()
    if files is None:
        print("FATAL: bridge/ 目录不存在（%s）" % BRIDGE, file=sys.stderr)
        return 2
    if not os.path.exists(MANIFEST):
        print("FATAL: 清单不在（%s）—— 先跑生成，或补上它" % MANIFEST, file=sys.stderr)
        return 2
    try:
        manifest = json.load(open(MANIFEST, encoding="utf-8"))
    except Exception as e:
        print("FATAL: 清单解析失败：%s" % e, file=sys.stderr)
        return 2
    probs = check(manifest, files)
    for p in probs:
        print("  ✗ " + p)
    if probs:
        print("交付清单不一致：%d 个问题（宿主播过去会缺件/错件）" % len(probs))
        return 1
    print("交付清单一致：%d 件（11 件 .m + 1 件宿主侧 .js），bytes/sha 逐件对上"
          % len(manifest["entries"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
