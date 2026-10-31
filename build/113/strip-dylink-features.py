#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **dylink.0 target-features 子段剥离器**（mail/008 缺陷 1 的修法件）
Copyright (C) 2026 ArchivalEra · SPDX-License-Identifier: AGPL-3.0-or-later

── 为什么需要它（一次发信级缺陷的根因，逐字可复现）──────────────────────────
  **现象**（mail/008，钓鱼执法轮实测，两独立跑次）：站点 /simulator/ 页
  `Export FMU` → ~170ms 后红错：
    `` Error: Internal error CodegenWasmJit: FMI3 component link failed:
       failed to extract linking metadata from klu
       Caused by: unrecognized `dylink.0` subsection: 6 ``

  **根因链**（每环都实测过）：
    ① 本仓工具链的 **clang 24（wasm-ld）** 给每个 `-shared` wasm 的 `dylink.0`
       写 **subsection 6**（payload `06 "wasm32"` = tool-conventions 的
       complimentary-info / target-features 声明）。实测：`clang --target=wasm32-wasip1
       -shared -Wl,--experimental-pic -Wl,--no-entry` 最小 C 文件即可复现。
    ② FMU 导出走的 `wit-component 0.259`（`linking::Linker` → `Metadata::try_new`，
       依赖 `wasmparser 0.259`）**只认子段 1–5**（dylink0.rs 的常量表：
       MEM_INFO/NEEDED/EXPORT_INFO(旧)/IMPORT_INFO/RUNTIME_PATH），未知子段 ⇒
       `bail!("unrecognized ''dylink.0'' subsection: {ty}")`。
    ③ ⇒ 官方 CI 的 clang 不写子段 6（或上游从未用新 clang 走这条链）⇒ 上游无感；
       我们 clang24 编的 14 个 blob（solver 全家 + libc_pic + ModelicaUtilities +
       usertab_dylink）全部带 6 ⇒ **FMU 链接必炸**。
    ④ 连锁后果：FMI Simulator 页拿不到任何可加载 FMU（站点不带示例 FMU，
       自产通道又断）⇒ 该客户端对普通访客完全不可用。

  **修法**（产物侧后处理，不动上游源、不动上游依赖版本）：
    把 blob 的 `dylink.0` 里的 **subsection 6 剥掉**。语义无损——子段 6 只是
    target-features **声明**（"wasm32"），而 wasm32 是 dylink 的默认档；
    链接器需要的是子段 1（mem-info）/4（import-info）等。剥后 wasmparser
    0.259 逐字验证通过（判据层复现：未剥 FAIL / 剥后 OK）。

── 用法 ──────────────────────────────────────────────────────────────────────
  python3 build/113/strip-dylink-features.py <file.wasm> [file.wasm …]   # 原地剥（幂等）
  python3 build/113/strip-dylink-features.py --check <file…>             # 只查不写（rc=1=还有 6）
  python3 build/113/strip-dylink-features.py --selftest                 # 三类用例自证

退出码：0 = 全部处理/干净；1 = --check 发现带 6 的文件 / 处理失败；2 = 用法。
"""
import sys


def _uleb_bytes(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _read_uleb(data, pos):
    r = 0
    sh = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        r |= (b & 0x7F) << sh
        if not (b & 0x80):
            return r, pos
        sh += 7
        if sh > 63:
            return None, pos
    return None, pos


def strip_bytes(data, drop_sub=6):
    """纯函数：剥 wasm 字节里 dylink.0 的指定子段。返回 (新字节 or None, 剥了几条)。

    返回 None = 没有可剥的（首段不是 dylink.0 custom 段，或没有该子段）——
    幂等的前提：对已干净的文件原样返回（不重写）。
    """
    if len(data) < 9 or data[:4] != b"\x00asm":
        return None, 0
    pos = 8
    if data[pos] != 0:                      # 首段不是 custom ⇒ 无 dylink.0
        return None, 0
    pos += 1
    size, pos = _read_uleb(data, pos)
    if size is None:
        return None, 0
    body_end = pos + size            # 起点就是 pos，不需要单独留一个变量
    if body_end > len(data):
        return None, 0
    nl = data[pos]
    p = pos + 1
    name = data[p:p + nl]
    p += nl
    if name != b"dylink.0":
        return None, 0
    kept = bytearray()
    n_stripped = 0
    while p < body_end:
        sub = data[p]
        p += 1
        ssz, p = _read_uleb(data, p)
        if ssz is None:
            return None, 0
        payload = data[p:p + ssz]
        p += ssz
        if sub == drop_sub:
            n_stripped += 1
        else:
            kept += bytes([sub]) + _uleb_bytes(ssz) + payload
    if not n_stripped:
        return None, 0
    new_body = _uleb_bytes(len(name)) + name + bytes(kept)
    new_sec = b"\x00" + _uleb_bytes(len(new_body)) + new_body
    return bytes(data[:8]) + new_sec + bytes(data[body_end:]), n_stripped


def strip_file(path, check_only=False):
    """处理一个文件。返回 (动作, 剥数)：stripped / clean / not-wasm / error。"""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as e:
        return "error:%s" % e, 0
    out, n = strip_bytes(data)
    if out is None:
        return "clean", 0
    if check_only:
        return "check-dirty", n
    try:
        with open(path, "wb") as fh:
            fh.write(out)
    except OSError as e:
        return "error:%s" % e, 0
    return "stripped", n


def _selftest():
    ok, bad = [], []

    def t(name, cond):
        (ok if cond else bad).append(name)

    # ── 夹具：手造带 subsection 6 的最小 dylink.0 wasm ──
    def fixture(subs):
        body = b"\x08dylink.0"
        for sub, payload in subs:
            body += bytes([sub]) + _uleb_bytes(len(payload)) + payload
        sec = b"\x00" + _uleb_bytes(len(body)) + body
        return b"\x00asm\x01\x00\x00\x00" + sec + b"\x01\x04\x01\x60\x00\x00"

    with6 = fixture([(1, b"\x00\x00\x00\x00"), (6, b"\x06wasm32")])
    without6 = fixture([(1, b"\x00\x00\x00\x00")])
    other_sub = fixture([(1, b"\x00\x00\x00\x00"), (2, b"\x01x")])
    not_wasm = b"ELF...."
    first_non_custom = b"\x00asm\x01\x00\x00\x00" + b"\x01\x04\x01\x60\x00\x00"

    # ① 正常不报（功能正例）
    out, n = strip_bytes(with6)
    t("正常：带 6 的 ⇒ 剥掉且计数 1", out is not None and n == 1)
    t("正常：剥后只剩子段 1（与无 6 夹具同形）", out is not None and strip_bytes(out) == (None, 0))
    t("正常：不带 6 的 ⇒ 原样（幂等键）", strip_bytes(without6) == (None, 0))
    t("正常：别的未知子段（如 2=NEEDED）不误伤", strip_bytes(other_sub) == (None, 0))
    # ② 该报的必须报（判据能证伪）
    out2, _ = strip_bytes(without6)
    t("★ 反向：无 6 时绝不重写（None）", out2 is None)
    # ③ 空输入必须报（零值守卫）
    t("★ 空输入 ⇒ (None, 0)", strip_bytes(b"") == (None, 0))
    t("★ 非 wasm ⇒ (None, 0)", strip_bytes(not_wasm) == (None, 0))
    t("★ 首段非 custom ⇒ (None, 0)", strip_bytes(first_non_custom) == (None, 0))

    # 端到端：真 wasm-ld 产物（如果本机 clang 在）剥后仍是合法 wasm
    import os, subprocess, tempfile
    clang = "/mnt/hdd/openmodelica-wasm-build/tools/bin/clang"
    if os.path.exists(clang):
        with tempfile.TemporaryDirectory() as d:
            c = os.path.join(d, "t.c")
            w = os.path.join(d, "t.wasm")
            open(c, "w").write("int f(void){return 1;}\n")
            r = subprocess.run([clang, "--target=wasm32-wasip1", "-shared", "-nostdlib",
                                "-fPIC", "-Wl,--no-entry", c, "-o", w],
                               capture_output=True, timeout=60)
            if r.returncode == 0:
                data = open(w, "rb").read()
                out, n = strip_bytes(data)
                t("★ 端到端：真 clang24 -shared 产物带 6（缺陷的复现前提）", n == 1)
                if out:
                    open(w, "wb").write(out)
                    v = subprocess.run(["/mnt/hdd/crossbuild-tools/wabt/bin/wasm-validate", w],
                                       capture_output=True, timeout=60)
                    t("★ 端到端：剥后 wasm-validate 过", v.returncode == 0)
    print("PASS | " + "\nPASS | ".join(ok))
    for b in bad:
        print("fail | " + b)
    print("=== strip-dylink-features 自证：%d PASS / %d fail ===" % (len(ok) - 0 if not bad else len(ok), len(bad)))
    return len(bad) == 0


def main(argv):
    if not argv:
        print("用法: strip-dylink-features.py [--check] <file.wasm…> | --selftest", file=sys.stderr)
        return 2
    if argv[0] == "--selftest":
        return 0 if _selftest() else 1
    check_only = False
    files = list(argv)
    if files[0] == "--check":
        check_only = True
        files = files[1:]
    if not files:
        print("FATAL: 没给文件（空清单不是通过）", file=sys.stderr)
        return 2
    dirty = stripped = 0
    for f in files:
        action, n = strip_file(f, check_only)
        if action == "stripped":
            stripped += 1
            print("  剥离 %-44s（%d 条子段 6）" % (f.split("/")[-1], n))
        elif action == "check-dirty":
            dirty += 1
            print("  ✗ 仍带子段 6: %s" % f)
        elif action.startswith("error"):
            print("  ✗ %s: %s" % (f, action[6:]))
            dirty += 1
    if check_only:
        if dirty:
            print("FAIL：%d 个文件仍带 dylink.0 subsection 6（先剥再发布）" % dirty)
            return 1
        print("OK：%d 个文件全部干净（无 dylink.0 subsection 6）" % len(files))
        return 0
    print("剥离完成：%d 个文件处理，%d 个原本就干净" % (stripped, len(files) - stripped))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
