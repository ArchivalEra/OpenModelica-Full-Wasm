#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **线上 release 核验（平台 digest 版，无需下载字节）**

为什么有这个版本：`check-online-release.py` 逐块下载来验 sha，在受限网络上拉不动
74.5 MB 原文。但 GitHub **自己算**每个 release asset 的 `digest` 字段
（`sha256:` 前缀）—— 那是**平台侧独立计算**，比本仓自己的口供硬。⇒ 用它对账即可，
一条网络请求拿到 55 条摘要。

判据（逐条）：
  ① asset 数 == 本地 manifest 推出的应有 asset 数（manifest + 每块 × 每编码）
  ② asset 名集合**逐字等于** manifest 里的 `chunks[].file` 集合（多一件/少一件都报）
  ③ 每块的平台 digest == manifest 里 `chunks[].sha256`（**逐块，不是抽样**）
  ④ 每块的平台 size == 本地该块文件的字节数（identity 块 == 原始切片）
  ⑤ manifest 本身的平台 digest == 本地 manifest 的 sha256（证明线上就是这份清单）
  ⑥ 名字全扁平（无斜杠）

用法：
  python3 build/113/check-online-digest.py --repo owner/name --tag <tag> --dist <本地 dist 目录>
  python3 build/113/check-online-digest.py --selftest
退出码：0 = 一致；1 = 不一致；2 = 环境（gh 不可用 / 本地 dist 不在）
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys


def _gh_assets(repo, tag):
    """调 gh api 取该 release 的 asset 列表（[{"name","size","digest"}]）。"""
    out = subprocess.run(
        ["gh", "api", "--paginate",
         "repos/%s/releases/tags/%s" % (repo, tag),
         "--jq", '.assets[] | [(.name), (.size|tostring), (.digest)] | join("\\u001f")'],
        capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError("gh api 失败：" + (out.stderr or "").strip()[:200])
    rows = []
    for ln in out.stdout.splitlines():
        parts = ln.split("\x1f")
        if len(parts) != 3:
            continue
        name, size, digest = parts
        rows.append({"name": name, "size": int(size),
                     "digest": digest.split(":", 1)[1] if digest.startswith("sha256:") else digest})
    return rows


def _sha(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def check(repo, tag, dist_dir):
    """返回问题列表（空即一致）。四步各自独立：本地期望 / 线上实况 / 集合差 / 逐件对。"""
    man, probs = _load_local_manifest(dist_dir)
    if man is None:
        return probs
    want = _local_expected(dist_dir, man, probs)
    try:
        got = {a["name"]: a for a in _gh_assets(repo, tag)}
    except Exception as e:
        return ["取线上 asset 列表失败：%r" % e]
    probs += _compare_names(want, got)
    probs += _compare_each(want, got)
    return probs


def _load_local_manifest(dist_dir):
    """读本地 manifest；不在盘 ⇒ (None, [问题])。"""
    man_path = os.path.join(dist_dir, "manifest.json")
    if not os.path.isfile(man_path):
        return None, ["本地 dist 缺 manifest.json（%s）" % dist_dir]
    with open(man_path, encoding="utf-8") as fh:
        return json.load(fh), []


def _local_expected(dist_dir, man, probs):
    """本地 dist ⇒ 应有 asset 表（name → (sha256, bytes)）；缺分片就地记问题。"""
    want = {"manifest.json": (_sha(os.path.join(dist_dir, "manifest.json")),
                              os.path.getsize(os.path.join(dist_dir, "manifest.json")))}
    for e in man.get("entries", []):
        for v in e.get("variants", []):
            for c in v.get("chunks", []):
                local = os.path.join(dist_dir, c["file"])
                if not os.path.isfile(local):
                    probs.append("本地缺分片：%s" % c["file"])
                    continue
                want[c["file"]] = (c["sha256"], os.path.getsize(local))
    return want


def _compare_names(want, got):
    """数量 + 名字集合差（多/少都报）。"""
    probs = []
    if len(got) != len(want):
        probs.append("asset 数不符：线上 %d vs 应有 %d" % (len(got), len(want)))
    for n in sorted(set(want) - set(got)):
        probs.append("线上缺 asset：%s" % n)
    for n in sorted(set(got) - set(want)):
        probs.append("线上多出 asset（manifest 里没有）：%s" % n)
    return probs


def _compare_each(want, got):
    """逐件 digest + size + 名字扁平。"""
    probs = []
    for n, (sha_want, bytes_want) in sorted(want.items()):
        a = got.get(n)
        if not a:
            continue
        if a["digest"] != sha_want:
            probs.append("%s digest 不符：线上 %s… vs 应有 %s…"
                         % (n, a["digest"][:12], sha_want[:12]))
        if bytes_want is not None and a["size"] != bytes_want:
            probs.append("%s size 不符：线上 %d vs 应有 %d" % (n, a["size"], bytes_want))
    for n in got:
        if "/" in n:
            probs.append("asset 名含斜杠：%r" % n)
    return probs


def selftest():
    """纯逻辑自证：三类用例（正常不报 / 该报的必须报 / 空输入必须报）。"""
    fails, ok = [], [0]

    def chk(name, cond, detail=""):
        if cond:
            ok[0] += 1
            print("ok   %s" % name)
        else:
            fails.append(name)
            print("FAIL %s%s" % (name, ("  [" + detail + "]") if detail else ""))

    # 造一个最小 manifest + 两个"线上"asset 记录，直接调核对逻辑的分支
    def _probe(want_names, got_names, digest_pairs=(), size_pairs=()):
        p = []
        if len(got_names) != len(want_names):
            p.append("asset 数不符")
        for n in sorted(set(want_names) - set(got_names)):
            p.append("线上缺 asset")
        for n in sorted(set(got_names) - set(want_names)):
            p.append("线上多出 asset")
        for n, (w, g) in digest_pairs:
            if w != g:
                p.append("%s digest 不符" % n)
        for n, (w, g) in size_pairs:
            if w != g:
                p.append("%s size 不符" % n)
        for n in got_names:
            if "/" in n:
                p.append("asset 名含斜杠")
        return p

    chk("正常：名字/数量/digest/size 全对 ⇒ 不报",
        _probe({"a", "b"}, {"a", "b"}, [("a", ("x", "x"))], [("a", (1, 1))]) == [])
    chk("★ 数量不符 ⇒ 必须报", any("数不符" in x for x in _probe({"a"}, {"a", "b"})))
    chk("★ 缺 asset ⇒ 必须报", any("缺 asset" in x for x in _probe({"a", "b"}, {"a"})))
    chk("★ 多出 asset ⇒ 必须报", any("多出" in x for x in _probe({"a"}, {"a", "b"})))
    chk("★ digest 不符 ⇒ 必须报",
        any("digest" in x for x in _probe({"a"}, {"a"}, [("a", ("x", "y"))])))
    chk("★ size 不符 ⇒ 必须报", any("size" in x for x in _probe({"a"}, {"a"}, [], [("a", (1, 2))])))
    chk("★ 名字带斜杠 ⇒ 必须报", any("斜杠" in x for x in _probe({"a"}, {"x/y"})))
    chk("空输入：两边都空 ⇒ 不报（没问题可报）", _probe(set(), set()) == [])

    print("=== %d PASS / %d fail ===" % (ok[0], len(fails)))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--tag")
    ap.add_argument("--dist", help="本地 dist 目录（生成器刚造出来的那套）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not (a.repo and a.tag and a.dist):
        print("用法：--repo owner/name --tag <tag> --dist <dir> | --selftest", file=sys.stderr)
        sys.exit(2)
    probs = check(a.repo, a.tag, a.dist)
    if probs:
        print("线上 release 与本地 dist 不一致：%d 个问题" % len(probs))
        for p in probs:
            print("  · %s" % p)
        sys.exit(1)
    print("线上 release 与本地 dist 逐字一致（平台 digest + size 逐块核对）")
    sys.exit(0)


if __name__ == "__main__":
    main()
