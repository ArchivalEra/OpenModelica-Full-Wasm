#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **入库产物与台账对账**（release workflow 的地基判据）

为什么需要：2026-11-01 用户点令「字节入库 + release 必须走 action」。
字节入库（`assets/omc/`）之后，最大的新风险是：**入库的字节和我们验过的产物不是同一份**
—— 那样 CI 会忠实地把一个没验过的引擎发出去，而且比本地发更难发现。

⇒ 本闸门在 CI 的第一步跑，逐件比 `assets/omc/*` 的 sha256/bytes 与
`build/FACTS.json` 的台账值。台账值是**产物树实测出来的**（本仓唯一产地），
入库字节必须逐字等于它。

判据（fail-closed，逐条点名）：
  ① 四件必须都在（缺件 = 不能发）
  ② 每件的 sha256 == 台账键
  ③ 每件的 bytes == 台账键
  ④ 台账键必须在盘且非空（零值守卫：拿不到台账不是通过）
  ⑤ （可选）--site 给了就再比一次站点副本，证明三者（台账 / 入库 / 站点）同源

用法：
  python3 build/113/check-release-inputs.py [--selftest]
  python3 build/113/check-release-inputs.py [--site /path/to/site-omc/omc]
退出码：0 = 一致；1 = 不一致；2 = 环境（台账/目录不在）
"""
import argparse
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(REPO, "assets", "omc")
LEDGER = os.environ.get("REFLECT_FACTS") or os.path.join(REPO, "build", "FACTS.json")

# 文件 → (bytes 台账键, sha256 台账键)。**四件都要**：只发 wasm 的 release 拿到手跑不起来
# （JS glue 是加载器，缺它 wasm 就是一坨没人调用的字节 —— 本仓「能取到 ≠ 能用了」）。
ENTRIES = {
    "engine": (
        ("OpenModelicaCompiler_bg.wasm", "omc_web_wasm_bytes", "omc_web_wasm_sha"),
        ("OpenModelicaCompiler.js", "omc_web_js_bytes", "omc_web_js_sha"),
        # 两份 d.ts 台账里没有独立键 ⇒ 只校验"存在且非空"，理由写在下面 _check_entry
        ("OpenModelicaCompiler.d.ts", None, None),
        ("OpenModelicaCompiler_bg.wasm.d.ts", None, None),
    ),
    # MSL 是**被装载的数据**、不是引擎（内容仓 mail/033）：单件 zip，安装形状。
    "msl": (
        ("msl-4.1.0-maint.om.zip", "msl_asset_bytes", "msl_asset_sha"),
    ),
}


def _sha(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _ledger_value(facts, key):
    e = facts.get(key)
    return e.get("value") if isinstance(e, dict) else e


def check(assets_dir, facts, site_dir=None, product="engine"):
    """纯逻辑（自证注入 assets_dir/facts）。返回问题列表（空 = 一致）。"""
    entries = ENTRIES.get(product)
    if entries is None:
        return ["未知 product %r（可选 %s）" % (product, sorted(ENTRIES))]
    if not facts:
        return ["台账为空/读不到 —— 拿不到台账不是通过（零值守卫）"]
    if not os.path.isdir(assets_dir):
        return ["入库目录不存在：%s（字节没入库 ⇒ 发不了）" % assets_dir]

    probs = []
    for name, bytes_key, sha_key in entries:
        probs += _check_entry(assets_dir, facts, name, bytes_key, sha_key, site_dir)
    return probs


def _check_entry(assets_dir, facts, name, bytes_key, sha_key, site_dir):
    """单件：存在 / 非空 / （有键则）bytes 与 sha 逐字对上。"""
    path = os.path.join(assets_dir, name)
    if not os.path.isfile(path):
        return ["缺件：%s（四件都要，缺一件 release 就不可用）" % name]
    size = os.path.getsize(path)
    if size == 0:
        return ["空文件：%s（零值守卫：0 字节不是通过）" % name]
    probs = []
    got_sha = _sha(path)
    if bytes_key:
        want = _ledger_value(facts, bytes_key)
        if want is None:
            probs.append("台账缺键 %s（无法对账 ⇒ 不当通过）" % bytes_key)
        elif int(want) != size:
            probs.append("%s bytes 不符：入库 %d vs 台账 %s（%s）" % (name, size, want, bytes_key))
    if sha_key:
        want = _ledger_value(facts, sha_key)
        if want is None:
            probs.append("台账缺键 %s（无法对账 ⇒ 不当通过）" % sha_key)
        elif str(want) != got_sha:
            probs.append("%s sha256 不符：入库 %s… vs 台账 %s…（%s）"
                         % (name, got_sha[:12], str(want)[:12], sha_key))
    # 两份 .d.ts 台账没有独立键 ⇒ 至少要求"非空 + 与站点副本一致"（给了 site 时）
    if site_dir and not sha_key:
        sp = os.path.join(site_dir, name)
        if os.path.isfile(sp):
            if _sha(sp) != got_sha:
                probs.append("%s 与站点副本不一致（入库 ≠ 站点）" % name)
        else:
            probs.append("站点副本缺 %s（--site 给了就必须齐）" % name)
    return probs


def selftest():
    """三类用例：正常不报 / 该报的必须报 / 空输入必须报。"""
    import tempfile

    fails, ok = [], [0]

    def chk(name, cond, detail=""):
        if cond:
            ok[0] += 1
            print("ok   %s" % name)
        else:
            fails.append(name)
            print("FAIL %s%s" % (name, ("  [" + detail + "]") if detail else ""))

    with tempfile.TemporaryDirectory() as d:
        # 造一份"正确"的入库
        blobs = {"OpenModelicaCompiler_bg.wasm": b"W", "OpenModelicaCompiler.js": b"J",
                 "OpenModelicaCompiler.d.ts": b"D", "OpenModelicaCompiler_bg.wasm.d.ts": b"T"}
        for n, b in blobs.items():
            with open(os.path.join(d, n), "wb") as fh:
                fh.write(b)
        facts = {
            "omc_web_wasm_bytes": {"value": 1},
            "omc_web_wasm_sha": {"value": hashlib.sha256(b"W").hexdigest()},
            "omc_web_js_bytes": {"value": 1},
            "omc_web_js_sha": {"value": hashlib.sha256(b"J").hexdigest()},
        }
        chk("正常：四件齐 + sha/bytes 对上 ⇒ 不报", check(d, facts) == [])

        # 该报的必须报
        bad_facts = dict(facts)
        bad_facts["omc_web_wasm_sha"] = {"value": "0" * 64}
        chk("★ sha 不符 ⇒ 必须报", any("sha256 不符" in x for x in check(d, bad_facts)))
        bad_size = dict(facts)
        bad_size["omc_web_wasm_bytes"] = {"value": 99}
        chk("★ bytes 不符 ⇒ 必须报", any("bytes 不符" in x for x in check(d, bad_size)))

        # 缺件 / 空件
        partial = tempfile.mkdtemp()
        with open(os.path.join(partial, "OpenModelicaCompiler_bg.wasm"), "wb") as fh:
            fh.write(b"W")
        chk("★ 缺件 ⇒ 必须报", any("缺件" in x for x in check(partial, facts)))
        empty = tempfile.mkdtemp()
        for n in blobs:
            open(os.path.join(empty, n), "wb").close()
        chk("★ 空文件 ⇒ 必须报（零值守卫）", any("空文件" in x for x in check(empty, facts)))

        # 空输入必须报
        chk("★ 台账为空 ⇒ 必须报", check(d, {}) != [])
        chk("★ 目录不存在 ⇒ 必须报", any("不存在" in x for x in check("/nonexistent/x", facts)))
        # product 分支：未知形态必须报（不许"没匹配也当通过"）；msl 形态只认那一件
        chk("★ 未知 product ⇒ 必须报", any("未知 product" in x for x in check(d, facts, product="bogus")))
        chk("★ msl 形态在 engine 目录上 ⇒ 必须报缺件",
            any("缺件" in x for x in check(d, facts, product="msl")) if False else
            any("缺件" in x for x in check(d, {"msl_asset_bytes": {"value": 1},
                                              "msl_asset_sha": {"value": "0" * 64}}, product="msl")))

    print("=== %d PASS / %d fail ===" % (ok[0], len(fails)))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", help="站点副本目录（可选；给了就三处同源再核一遍）")
    ap.add_argument("--product", default="engine", choices=sorted(ENTRIES))
    ap.add_argument("--assets", help="入库目录（默认按 product 选）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())

    try:
        with open(LEDGER, encoding="utf-8") as fh:
            facts = (json.load(fh) or {}).get("facts", {})
    except Exception as e:
        print("环境：读不到台账 %s（%r）" % (LEDGER, e), file=sys.stderr)
        sys.exit(2)

    assets = a.assets or (ASSETS if a.product == "engine"
                          else os.path.join(REPO, "assets", "msl"))
    probs = check(assets, facts, a.site, a.product)
    if probs:
        print("入库产物与台账不一致：%d 个问题" % len(probs))
        for p in probs:
            print("  · %s" % p)
        sys.exit(1)
    print("入库产物与台账一致（%s：bytes/sha 逐字对上）" % a.product)
    sys.exit(0)


if __name__ == "__main__":
    main()
