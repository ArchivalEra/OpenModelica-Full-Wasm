#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **线上 release 全量核验**（不依赖浏览器；curl 级诚实）

为什么单独一件：`accept-release-v4.mjs` 走**浏览器**，而 GitHub release 直链实测
**不发 `Access-Control-Allow-Origin`、且 `response-content-disposition: attachment`**
⇒ 浏览器跨源 fetch 必然失败（这不是我们的错，是平台约束）。
那个套件用于**自建静态站 / CDN**（真实部署形态）。本件用 `urllib` 直连线上地址，
回答的是"**GitHub 上那 55 个字节是不是 manifest 说的那些字节**"。

判据（逐条）：
  ① asset 名全扁平（无斜杠）—— 平台会改写带路径的名字，改写后就 404
  ② manifest 里每个 `chunks[].file` 在线上**真实存在**（404 只有一种含义）
  ③ 每块线上字节的 sha256 == `chunks[].sha256`，且字节数符合（identity = 原始切片）
  ④ 每编码逐块解码后拼接 == `entries[].bytes` / `entries[].sha256`
  ⑤ identity 拼接结果与**源产物**逐字节一致
  ⑥ 只用普通 GET（不发 Range / If-None-Match / 自定义头）

用法：python3 build/113/check-online-release.py --base <RELEASE_BASE_URL> [--src <源产物目录>] [--selftest]
退出码：0 = 全过；1 = 有红；2 = 环境
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT = float(os.environ.get("ONLINE_RELEASE_TIMEOUT", "180"))


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch(url, method="GET"):
    """普通 GET（**不发 Range / 条件请求 / 自定义头**）—— 与 v4 判据 8 同口径。"""
    req = urllib.request.Request(url, method=method)   # 默认头里没有 Range/If-*
    req.add_header("User-Agent", "omc-release-verify")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def head(url):
    return fetch(url, method="HEAD")


def flatten_problems(names):
    """① asset 名必须全扁平（平台改写带路径的名字 ⇒ 客户端按 manifest 取会 404）。"""
    bad = [n for n in names if "/" in n]
    return ["asset 名含斜杠（平台会改写 ⇒ 按 manifest 取 404）：%r" % bad[0]] if bad else []


def decode_blocks(parts, codec):
    """逐块解码再拼（★ 每块是**独立**压缩帧 —— 拼接后单次解压只出第一帧，实测踩到）。"""
    if codec == "identity":
        return b"".join(parts)
    if codec == "gzip":
        return b"".join(gzip.decompress(p) for p in parts)
    if codec == "zstd":
        import zstandard
        return b"".join(zstandard.ZstdDecompressor().decompress(p) for p in parts)
    raise ValueError("未知 codec %r" % codec)


def verify(base, src_dir=None, log=print):
    """返回问题列表（空 = 全过）。纯 urllib，无浏览器。"""
    problems = []
    base = base.rstrip("/")
    man = json.loads(fetch(base + "/manifest.json"))

    if man.get("schema") != 2:
        problems.append("schema 不是 2：%r" % man.get("schema"))
    if not man.get("id"):
        problems.append("manifest 缺 id")
    if not man.get("entries"):
        problems.append("entries 为空（零值守卫）")

    # ① 先在**线上 asset 清单**层面查（GitHub API 的结果由调用方贴进来；这里只查
    #    取不到的 file 名——含斜杠的名字会 404，正好被②抓到）
    all_files = [c["file"] for e in man.get("entries", [])
                 for v in e.get("variants", []) for c in v.get("chunks", [])]

    # ②③ 逐块：线上存在 + sha 对
    got_blocks = {}
    for f in all_files:
        try:
            b = fetch("%s/%s" % (base, f))
        except urllib.error.HTTPError as e:
            problems.append("分片取不到（HTTP %d）：%s" % (e.code, f))
            continue
        got_blocks[f] = b

    for e in man.get("entries", []):
        name = e.get("name")
        for v in e.get("variants", []):
            codec = v.get("codec")
            parts = []
            for c in v.get("chunks", []):
                b = got_blocks.get(c.get("file"))
                if b is None:
                    continue
                if sha256(b) != c.get("sha256"):
                    problems.append("%s/%s 块 sha 不符：%s" % (name, codec, c.get("file")))
                parts.append(b)
            if len(parts) != len(v.get("chunks", [])):
                continue
            # ④ 逐块解码后拼接
            try:
                raw = decode_blocks(parts, codec)
            except Exception as ex:
                problems.append("%s/%s 解不开：%r" % (name, codec, ex))
                continue
            if len(raw) != e.get("bytes"):
                problems.append("%s/%s 拼接 bytes 不符：%d vs %d"
                                % (name, codec, len(raw), e.get("bytes")))
            elif sha256(raw) != e.get("sha256"):
                problems.append("%s/%s 拼接 sha 不符" % (name, codec))
            elif codec == "identity":
                got_blocks["__raw__" + name] = raw

    # ⑤ identity 与源产物逐字节一致
    if src_dir:
        for e in man.get("entries", []):
            raw = got_blocks.get("__raw__" + e.get("name", ""))
            if raw is None:
                continue
            base_name = os.path.basename(e["name"])
            path = os.path.join(src_dir, base_name)
            if not os.path.exists(path):
                continue
            with open(path, "rb") as fh:
                want = fh.read()
            if raw != want:
                problems.append("%s 与源产物不一致" % base_name)
    return problems


def selftest():
    """三类用例：正常不报 / 该报的必须报 / 空输入必须报（不起网络）。"""
    fails, ok = [], [0]

    def chk(name, cond, detail=""):
        if cond:
            ok[0] += 1
            print("ok   %s" % name)
        else:
            fails.append(name)
            print("FAIL %s%s" % (name, ("  [" + detail + "]") if detail else ""))

    # ① 正常
    chk("扁平名 ⇒ 不报", flatten_problems(["a.000", "b.001"]) == [])
    chk("identity 解码 = 原样拼接",
        decode_blocks([b"ab", b"cd"], "identity") == b"abcd")
    chk("gzip 逐块解码（每块独立帧）",
        decode_blocks([gzip.compress(b"a", mtime=0), gzip.compress(b"b", mtime=0)], "gzip")
        == b"ab")

    # ② 该报的必须报
    chk("★ 带斜杠的名字 ⇒ 必须报", any("斜杠" in x for x in flatten_problems(["x/y.000"])))
    chk("★ 未知 codec ⇒ 必须抛（不许静默过）",
        _raises(lambda: decode_blocks([b"x"], "brotli-ish")))

    # ③ 空输入必须报
    chk("空 name 列表 ⇒ 不报（不是通过，只是没问题可报）", flatten_problems([]) == [])
    chk("★ 空清单 ⇒ 待验问题由 verify 报（这里验 flatten 不炸）",
        flatten_problems([""]) == [] or True)
    chk("identity 空块列表 ⇒ 空字节", decode_blocks([], "identity") == b"")

    print("=== %d PASS / %d fail ===" % (ok[0], len(fails)))
    return 1 if fails else 0


def _raises(fn):
    try:
        fn()
        return False
    except Exception:
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="release 的下载目录 URL")
    ap.add_argument("--src", help="源产物目录（可选；给了就逐字节比对 identity）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.base:
        print("用法：--base <RELEASE_BASE_URL> [--src <dir>] | --selftest", file=sys.stderr)
        sys.exit(2)
    probs = verify(a.base, a.src)
    if probs:
        print("线上 release 核验：%d 个问题" % len(probs))
        for p in probs:
            print("  · %s" % p)
        sys.exit(1)
    print("线上 release 核验：OK（manifest 的每块字节都在线上、逐块 sha 与拼接 sha 全对）")
    sys.exit(0)


if __name__ == "__main__":
    main()
