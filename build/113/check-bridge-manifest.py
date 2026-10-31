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

# 协议路径（GitRoll #13/#14/#15：同一字面量重复 ⇒ 提常量）。写错一个字符 =
# 两侧静默失配（桥轮询永远读不到请求），所以"只该有一个产地"。
PROTO_REQUEST = "/tmp/omc_req.txt"
PROTO_RESPONSE = "/tmp/omc_res.txt"
PROTO_SEQ = "/tmp/omc_seq.txt"
PROTO_PATHS = {"request": PROTO_REQUEST, "response": PROTO_RESPONSE, "seq": PROTO_SEQ}
MANIFEST = os.path.join(BRIDGE, "manifest.json")
MIN_ENTRIES = 12
PROTOCOL_KEYS = ("request", "response", "seq")


def disk_files():
    if not os.path.isdir(BRIDGE):
        return None
    return sorted(f for f in os.listdir(BRIDGE) if f.endswith((".m", ".js")))


def check(manifest, files, root=BRIDGE, expect_protocol=True):
    """纯逻辑（自证注入 manifest/files/root）。返回问题列表（空 = 一致）。

    四组判据各自一个函数：清单→磁盘 / 磁盘→清单 / 件数下限 / 协议路径。
    这样每组都能单独读、单独改（原来一个大函数读不出边界）。
    """
    shape = _check_shape(manifest, files)
    if shape is not None:
        return shape
    listed = _index_entries(manifest["entries"])
    probs = _check_entries_shape(manifest["entries"])
    probs += _check_listed_vs_disk(listed, root)
    probs += _check_disk_vs_listed(files, listed)
    probs += _check_min_entries(manifest["entries"])
    probs += _check_protocol(manifest, expect_protocol)
    return probs


def _check_shape(manifest, files):
    """初筛：形状不对就早退（这些不是"结论"，是"没法判"）。"""
    if not isinstance(manifest, dict):
        return ["清单不是对象"]
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return ["清单缺 entries 数组"]
    if not entries:
        return ["清单 entries 为空（零值守卫：空清单不是通过）"]
    if files is None:
        return ["bridge/ 目录不存在（环境问题，不是结论）"]
    return None


def _index_entries(entries):
    """按文件名索引（顺手给缺 file 的条目点名）。"""
    listed = {}
    for i, e in enumerate(entries):
        if isinstance(e, dict) and e.get("file"):
            listed[e["file"]] = e
    return listed


def _check_entries_shape(entries):
    """缺 file 的条目（形状不对 ⇒ 没法按文件名对账，必须点名）。"""
    return ["条目[%d] 缺 file" % i
            for i, e in enumerate(entries)
            if not isinstance(e, dict) or not e.get("file")]


def _check_listed_vs_disk(listed, root):
    """① 清单 → 磁盘：每件必须存在，且 bytes / sha256 与磁盘逐字一致。"""
    probs = []
    for name, e in sorted(listed.items()):
        path = os.path.join(root, name)
        if not os.path.exists(path):
            probs.append("清单里的 `%s` 在磁盘上不存在（宿主播过去会缺件）" % name)
            continue
        with open(path, "rb") as fh:
            blob = fh.read()
        probs += _compare_one_entry(name, e, blob)
    return probs


def _compare_one_entry(name, entry, blob):
    """单件对账：bytes + sha256。"""
    probs = []
    if entry.get("bytes") != len(blob):
        probs.append("`%s` bytes 不符：清单 %r vs 磁盘 %d"
                     % (name, entry.get("bytes"), len(blob)))
    want = str(entry.get("sha256") or "")
    got = hashlib.sha256(blob).hexdigest()
    if want != got:
        probs.append("`%s` sha256 不符：清单 %s… vs 磁盘 %s…" % (name, want[:12], got[:12]))
    return probs


def _check_disk_vs_listed(files, listed):
    """② 磁盘 → 清单：多出来的件没人装（宿主会漏它）。"""
    return ["磁盘上有 `%s` 但清单没有（宿主不会装它）" % f
            for f in files if f not in listed]


def _check_min_entries(entries):
    """③ 件数下限（零值守卫的另一半）。"""
    if len(entries) < MIN_ENTRIES:
        return ["清单只有 %d 件，少于下限 %d（11 件 .m + 1 件宿主侧 .js）"
                % (len(entries), MIN_ENTRIES)]
    return []


def _check_protocol(manifest, expect_protocol):
    """④ 协议路径：三项齐全、互不相同；★ 且必须逐字等于契约常量。

    ④b 只有把常量提到唯一产地才可判：否则"清单写一个、桥里写另一个"两侧静默失配
    （轮询永远读不到请求）。自证夹具用简写路径 ⇒ 传 expect_protocol=False 跳过。
    """
    pp = manifest.get("protocol_paths") or {}
    probs, vals = [], []
    for k in PROTOCOL_KEYS:
        v = str(pp.get(k) or "").strip()
        if not v:
            probs.append("协议路径缺 `%s`（两侧写死同名常量，缺一个桥就断）" % k)
            continue
        vals.append(v)
        if expect_protocol and v != PROTO_PATHS[k]:
            probs.append("协议路径 `%s` 与契约不一致：清单 %r ≠ 契约 %r"
                         % (k, v, PROTO_PATHS[k]))
    if len(vals) == len(PROTOCOL_KEYS) and len(set(vals)) != len(vals):
        probs.append("协议路径有重复（request/response/seq 必须是三个不同文件）")
    return probs


def _selftest():
    ok, bad = [], []

    def t(name, cond):
        (ok if cond else bad).append(name)

    files = ["a.m", "b.js"]
    # 自证夹具的路径是简写（真契约路径那三件在 PROTO_PATHS；夹具只需"三项不同"）
    FIXTURE_PATHS = {"request": "/tmp/r", "response": "/tmp/s", "seq": "/tmp/q"}
    # 用真磁盘做夹具（写临时目录）
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for f in files:
            open(os.path.join(d, f), "wb").write(b"Z")
        sha = hashlib.sha256(b"Z").hexdigest()
        FIX_GEN = "c%d.m"                # 夹具里"多出来的 10 件"（GitRoll #16）
        g = {"schema": 1,
             "protocol_paths": FIXTURE_PATHS,
             "entries": [{"file": f, "bytes": 1, "sha256": sha} for f in files] + [
                 {"file": FIX_GEN % i, "bytes": 1, "sha256": sha} for i in range(10)]}
        for i in range(10):
            open(os.path.join(d, FIX_GEN % i), "wb").write(b"Z")
        allf = sorted(files + [FIX_GEN % i for i in range(10)])

        # ① 正常不报
        t("正常：清单与磁盘逐件一致 ⇒ 无问题", check(g, allf, root=d, expect_protocol=False) == [])
        # ② 该报的必须报
        t("★ 清单缺磁盘上的件 ⇒ 必须报",
          any("清单没有" in x for x in check(g, allf + ["extra.m"], root=d, expect_protocol=False)))
        t("★ 清单里有磁盘没有的件 ⇒ 必须报", any("不存在" in x for x in
                                            check({**g, "entries": g["entries"] + [
                                                {"file": "ghost.m", "bytes": 1, "sha256": sha}]}, allf, root=d, expect_protocol=False)))
        t("★ sha 不符 ⇒ 必须报", any("sha256 不符" in x for x in
                                  check({**g, "entries": [dict(g["entries"][0], sha256="0"*64)] + g["entries"][1:]},
                                        allf, root=d, expect_protocol=False)))
        t("★ bytes 不符 ⇒ 必须报", any("bytes 不符" in x for x in
                                    check({**g, "entries": [dict(g["entries"][0], bytes=99)] + g["entries"][1:]},
                                          allf, root=d, expect_protocol=False)))
        t("★ 件数不足下限 ⇒ 必须报", any("少于下限" in x for x in check(
            {**g, "entries": g["entries"][:2]}, files, root=d, expect_protocol=False)))
        t("★ 协议路径缺一项 ⇒ 必须报", any("协议路径缺" in x for x in check({**g, "protocol_paths": {"request": "/tmp/r", "response": "/tmp/s"}}, allf, root=d, expect_protocol=False)))
        t("★ 协议路径重复 ⇒ 必须报", any("重复" in x for x in check(
            {**g, "protocol_paths": {"request": "/tmp/r", "response": "/tmp/r", "seq": "/tmp/q"}}, allf, root=d, expect_protocol=False)))
        # ④b ★ 新判据自己的反向（AGENTS：新契约至少配一条"该报的必须报"）：
        #   三种不同但**不是契约那三个**的路径 ⇒ 必须报「与契约不一致」。
        #   这是"清单与桥两侧同名常量"这条不变式的机器判据 —— 没有它，常量提了也白提。
        t("★ 协议路径与契约不一致 ⇒ 必须报", any("与契约不一致" in x for x in check(
            {**g, "protocol_paths": {"request": "/tmp/x1", "response": "/tmp/x2", "seq": "/tmp/x3"}},
            allf, root=d)))
        # ③ 空输入必须报
        t("★ 空 entries ⇒ 必须报", check({"entries": []}, []) != [])
        t("★ 清单非对象 ⇒ 必须报", check(None, []) != [])
        # ★ 条目缺 file ⇒ 必须报（拆函数时这条一度被我弄丢，补回并给它反例：
        #   没有反例的判据 = 没人盯着它 —— 正是 AGENTS「断言要能证伪」要拦的形状）
        t("★ 条目缺 file ⇒ 必须报", any("缺 file" in x for x in check(
            {"entries": [{"bytes": 1, "sha256": "0" * 64}],
             "protocol_paths": FIXTURE_PATHS}, [], root=d, expect_protocol=False)))
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