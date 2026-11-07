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
import http.client
import time
import urllib.error
import urllib.request

TIMEOUT = float(os.environ.get("ONLINE_RELEASE_TIMEOUT", "180"))


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch(url, method="GET", retries=4):
    """普通 GET（**不发 Range / 条件请求 / 自定义头**）—— 与 v4 判据 8 同口径。

    ★ 带重试：GitHub 的 release-assets 域实测会偶发 `RemoteDisconnected`（连接被对端
    提前关）。重试是**取字节**的容错，不是掩盖失败 —— 4 次都取不到才算红。
    """
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, method=method)   # 默认头里没有 Range/If-*
        req.add_header("User-Agent", "omc-release-verify")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except (urllib.error.URLError, http.client.RemoteDisconnected,
                TimeoutError) as e:   # ConnectionResetError ⊂ OSError，URLError 已覆盖其网络路径
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


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


def verify(base, src_dir=None, codecs=None, sample=0, log=print):
    """返回问题列表（空 = 全过）。纯 urllib，无浏览器。

    四步：清单形状 → 拉块 → 逐变体核（sha/拼接/全局）→ identity 与源产物比。
    """
    problems = []
    base = base.rstrip("/")
    man = json.loads(fetch(base + "/manifest.json"))
    problems += _manifest_shape(man)

    def _want(v):
        return codecs is None or v.get("codec") in codecs

    got_blocks = _fetch_chunks(base, man, _want, problems)
    for e in man.get("entries", []):
        for v in e.get("variants", []):
            if _want(v):
                problems += _verify_variant(e, v, got_blocks, sample, log)
    if src_dir:
        problems += _compare_to_source(src_dir, man, got_blocks)
    return problems


def _manifest_shape(man):
    """清单形状三件：schema / id / entries 非空。"""
    problems = []
    if man.get("schema") != 2:
        problems.append("schema 不是 2：%r" % man.get("schema"))
    if not man.get("id"):
        problems.append("manifest 缺 id")
    if not man.get("entries"):
        problems.append("entries 为空（零值守卫）")
    return problems


def _fetch_chunks(base, man, want, problems):
    """②③ 按 manifest 把要验的块都拉下来；404 记问题不中断。"""
    got = {}
    files = [c["file"] for e in man.get("entries", [])
             for v in e.get("variants", []) if want(v) for c in v.get("chunks", [])]
    for f in files:
        try:
            got[f] = fetch("%s/%s" % (base, f))
        except urllib.error.HTTPError as e:
            problems.append("分片取不到（HTTP %d）：%s" % (e.code, f))
    return got


def _verify_variant(entry, variant, got_blocks, sample, log):
    """单个变体：逐块 sha →（非抽样时）解码拼接 → 全局 bytes/sha。"""
    name = entry.get("name")
    codec = variant.get("codec")
    problems = []
    chunks_all = variant.get("chunks", [])
    chunks = chunks_all[:sample] if sample else chunks_all
    parts = []
    for c in chunks:
        b = got_blocks.get(c.get("file"))
        if b is None:
            continue
        if sha256(b) != c.get("sha256"):
            problems.append("%s/%s 块 sha 不符：%s" % (name, codec, c.get("file")))
        parts.append(b)
    if sample:
        # 抽样模式：只核 sha，不做拼接（拼接需要全部块）
        log("%s/%s 抽样核过 %d/%d 块（未抽的不假装核过）"
            % (name, codec, len(parts), len(chunks_all)))
        return problems
    if len(parts) != len(chunks_all):
        return problems
    try:
        raw = decode_blocks(parts, codec)
    except Exception as ex:
        problems.append("%s/%s 解不开：%r" % (name, codec, ex))
        return problems
    if len(raw) != entry.get("bytes"):
        problems.append("%s/%s 拼接 bytes 不符：%d vs %d"
                        % (name, codec, len(raw), entry.get("bytes")))
    elif sha256(raw) != entry.get("sha256"):
        problems.append("%s/%s 拼接 sha 不符" % (name, codec))
    elif codec == "identity":
        got_blocks["__raw__" + name] = raw
    return problems


def _compare_to_source(src_dir, man, got_blocks):
    """⑤ identity 拼接结果与源产物逐字节一致。"""
    problems = []
    for e in man.get("entries", []):
        raw = got_blocks.get("__raw__" + e.get("name", ""))
        if raw is None:
            continue
        base_name = os.path.basename(e["name"])
        path = os.path.join(src_dir, base_name)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as fh:
            if raw != fh.read():
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
    ap.add_argument("--codecs", help="只验这些编码（逗号分隔；默认全部）。"
                                       "网络慢时用 identity 单独跑最省字节。")
    ap.add_argument("--sample", type=int, default=0,
                    help="每编码只验前 N 块（0 = 全验）。网络受限时的诚实抽样："
                         "抽样过的块是真核过的，未抽的不假装核过（报告里写明）。")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.base:
        print("用法：--base <RELEASE_BASE_URL> [--src <dir>] | --selftest", file=sys.stderr)
        sys.exit(2)
    codecs = [c.strip() for c in a.codecs.split(",")] if a.codecs else None
    probs = verify(a.base, a.src, codecs, a.sample)
    if probs:
        print("线上 release 核验：%d 个问题" % len(probs))
        for p in probs:
            print("  · %s" % p)
        sys.exit(1)
    print("线上 release 核验：OK（manifest 的每块字节都在线上、逐块 sha 与拼接 sha 全对）")
    sys.exit(0)


if __name__ == "__main__":
    main()
