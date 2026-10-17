#!/usr/bin/env python3
# OpenModelica-Full-Wasm — **架构纯度闸门**：一条线只许一个架构（用户点令 2026-10-12）
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# ── 为什么要它（从姊妹仓 Octave-Full-Wasm 的实测教训搬来，判据同形）──────────────
# 混编的失败模式是"**两边都建成功、自检全绿、运行期才炸**"：
#   · wasm32 对象链进 wasm64（`ida.c.o: wasm32 object file can't be linked in wasm64 mode`）；
#   · 错档模块进宿主（加载器只给 `incorrect architecture (wasm32 vs wasm64)`，
#     与"缺符号"的 `reading 'value'` 混在一起时无法区分）。
# ⇒ 判据必须**可执行**，且**反向断言**（喂错档必须红）。
#
# ── 本仓的档表（一线一架构）──────────────────────────────────────────────────
#   master 线              → 产物 wasm64，只编 wasm64
#   wasm32 线              → 产物 wasm32，只编 wasm32
#   ⚠️ 2026-10-14 用户点令：原 `IllegalPerformance`（性能）线**已删除** ——
#      性能线只有在 wasm64 做到生产级后才是"脱离官方树的开发"。线删了，但
#      **档表里的 `ilperf` 档名保留**：wasm64 生产级后重建该线时用它（档 = wasm64，
#      性能优化不改架构）。今天没有任何现役产物喂这个档名。
#
# ⚠️ 与姊妹仓的差异：那边查的是 `.oct`（dlopen 的 side module）；本仓查的是
#    **宿主 wasm + 附属 wasm 模块**（omc.wasm / coderuntime / FMU 之类）。
#    ⇒ 参数名用 `--mod`（可多次），谓词是"每个 wasm 的架构都等于本档期望"。
#
# 用法：
#   python3 build/113/check-lane-purity.py --lane w64    --host omc.wasm --mod omc-runtime.wasm
#   python3 build/113/check-lane-purity.py --lane wasm32 --host omc.wasm
#   python3 build/113/check-lane-purity.py --selftest
import argparse
import os
import shutil
import subprocess
import sys

# 档 → 期望架构。w64/wasm64/master = 64 位；wasm32/wasm32-final = 32 位。
LANE_EXPECT = {
    "w64": "wasm64",
    "wasm64": "wasm64",
    "master": "wasm64",
    "w64-base": "wasm64",
    "ilperf": "wasm64",            # 原 IP 线的**产物**档（性能优化不改架构）；线已删，档名留给重建
    "wasm32": "wasm32",
    "wasm32-final": "wasm32",
    "product": "wasm32",
    "base": "wasm32",
}


def expected_arch(lane):
    return LANE_EXPECT.get(lane)


def _readobj():
    for c in ("llvm-objdump", "llvm-objdump-19", "llvm-objdump-18", "wasm-objdump"):
        p = shutil.which(c)
        if p:
            return p
    return None


def _wasm_arch(path):
    """读 .wasm 的架构（memory64 标志）。返回 'wasm32'/'wasm64'/None（不是 wasm/读不到）。

    判据出处：WebAssembly core spec —— memory 段（section id 5）的 limits flags
    位 0x4 为 memory64 标志；其余位是 has_max(0x1) / shared(0x8)。64 位地址空间
    的模块就是 wasm64 档（`wasm64-unknown-unknown` / `-mmemory64`）。
    """
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as fh:
            data = fh.read(64 * 1024 * 1024)          # 够覆盖 memory 段前的头
    except OSError:
        return None
    if len(data) < 8 or data[:4] != b"\x00asm":
        return None
    pos = 8                                            # magic(4) + version(4)
    n = len(data)

    def _uleb(p):
        r = 0; sh = 0
        while p < n:
            b = data[p]; p += 1
            r |= (b & 0x7F) << sh
            if not (b & 0x80):
                return r, p
            sh += 7
            if sh > 63:
                return None, p
        return None, p

    while pos < n:
        sec_id = data[pos]; pos += 1
        size, pos = _uleb(pos)
        if size is None:
            return None
        if sec_id == 5:                                # memory section
            if pos >= n:
                return None
            cnt, p2 = _uleb(pos)
            if not cnt:
                return None
            flags = data[p2]
            return "wasm64" if (flags & 0x04) else "wasm32"
        if sec_id == 2:                                # import section（side module 走这）
            # ★ side module（`--experimental-pic --shared` 产的那种：liblapack / libc_pic /
            #   ModelicaUtilities）**没有自己的 memory 段**，它 import 宿主的 memory
            #   ⇒ 架构只能靠 import 的 memory 类型（同样是 limits flags 的 0x4 位）判。
            #   （实测：本仓 web/wasm-blobs/*.wasm 三个都是这种，没有 memory 段 ⇒
            #     旧判据返回 None ⇒ 闸门报"附属模块读不到架构"**假红**。）
            if pos >= n:
                return None
            n_imp, p2 = _uleb(pos)
            if n_imp is None:
                return None
            p2_end = pos + size
            for _ in range(n_imp):
                # import 条目 = **两个** name（module + 字段名）+ kind + 类型（spec §5.5.3）。
                # ⚠️ 只读一个 name 会错位（实测踩到：fmi 的
                #   js-component-bindgen-component.core2.wasm —— 38 个导入全在段里，
                #   只读一个 name 时字段错位漂移到 kind 字节 ⇒ 遇"未知 kind" break ⇒
                #   第 37 个 env.memory import 没被看到 ⇒ 闸门假红"读不到架构"）。
                for _names in range(2):               # module 名 + 字段名
                    if p2 >= p2_end:
                        break
                    ln, p2 = _uleb(p2)
                    if ln is None or p2 + ln > p2_end:
                        break
                    p2 += ln
                if p2 >= p2_end:
                    break
                kind = data[p2]; p2 += 1
                if kind == 0x00:                       # func: typeidx
                    _, p2 = _uleb(p2)
                elif kind == 0x01:                     # table: elemtype + limits
                    p2 += 1
                    fl = data[p2]; p2 += 1
                    _, p2 = _uleb(p2)
                    if fl & 0x01:
                        _, p2 = _uleb(p2)
                elif kind == 0x02:                     # memory: limits（**架构在这**）
                    fl = data[p2]; p2 += 1
                    _, p2 = _uleb(p2)
                    if fl & 0x01:
                        _, p2 = _uleb(p2)
                    return "wasm64" if (fl & 0x04) else "wasm32"
                elif kind == 0x03:                     # global: valtype + mut
                    p2 += 2
                else:
                    break
            # ⚠️ 别在这里 return None：**主模块**也有 import 段（函数 import），但它的架构
            #    由**后面的 memory 段**决定 ⇒ 必须继续走（实测踩到：宿主 wasm 的 import 段
            #    7727 字节、没有 import memory，早返回 ⇒ 连宿主都读不到）。
            pos += size
            continue
        pos += size
    return None                                        # 既无 memory 段也无 import memory ⇒ 读不到


def _dylink_arch(path):
    """读 **dylink.0 side module** 的架构。返回 'wasm32'/'wasm64'/None。

    ⚠️ 为什么单独一条（本仓 2026-10-13 实测）：`--experimental-pic --shared` 产的 side module
    （本仓 web/wasm-blobs/{libc_pic,liblapack,ModelicaUtilities}.wasm）**既没有 memory 段、
    也没有 import memory** —— 它的内存由加载器按 dylink.0 的 mem_size 分配（实测段表：
    custom(dylink.0) / type / import / func / table / global / export / elem / code / data …，
    无 id=5）。⇒ 从字节流**判不出** 32/64（那是客观事实，不是判据坏了）。

    这里的判据是**同档要求**：side module 由宿主加载，它**必须**是宿主的档；宿主是 wasm32 时
    side module 也必须是 wasm32 编出来的。实现：dylink.0 的 mem_size / mem_p2align 不携带
    位数信息 ⇒ 只能靠**名字**或**调用者给出的期望**。⇒ 本函数返回 "SIDE"（需要宿主档），
    由 check() 把宿主的期望档套上去（见下面 check 里对 "SIDE" 的处理）。
    """
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as fh:
            data = fh.read(4096)
    except OSError:
        return None
    if len(data) < 8 or data[:4] != b"\x00asm":
        return None
    # custom 段（id=0）的名字里出现 "dylink" ⇒ 这是 side module
    return "SIDE" if b"dylink" in data[:2048] else None


def arch_of(path, run=None):
    """读一个 wasm 文件的架构。返回 'wasm32' / 'wasm64' / 'MIXED(...)' / None（读不到）。

    ⚠️ `.a`/多成员输入会有多行 `Arch:` ⇒ **取全集去重**而不是只看第一行
    （姊妹仓实测：只看 head -1 会漏掉"一包里混进一个错档"）。

    ★ 本仓 2026-10-13 加 **wasm 专用判据**（为什么必须加，实测）：
       · wasm 格式**没有** `Arch:` 头 —— `llvm-objdump -h` 与 wabt `wasm-objdump -h`
         对 .wasm 都不吐那一行（实测：分别输出 `file format wasm` / `file format wasm 0x1`）
         ⇒ 旧的"只认 Arch: 行"逻辑在本仓产物上**恒**返回 None ⇒ 闸门恒 fail-closed 报
         "读不到架构"（那是**假红**：产物没问题，是判据不适用）。
       · wasm 的架构由 **memory64 标志**决定（WebAssembly spec）：memory 段的
         limits flags 位 0x4 = memory64 ⇒ 64 位地址空间；否则 wasm32。
       · 实现：读字节流找 memory 段（id=5）的 limits 标志位。（不引入新依赖。）
    """
    if run is None:
        a = _wasm_arch(path)
        if a is not None:
            return a
        d = _dylink_arch(path)
        if d is not None:
            return d                                   # "SIDE"：需宿主档（见 check 的处理）
    ro = _readobj()
    if not ro:
        return None
    if run is not None:
        rc, out = run(f"{ro} -h {path}")
    else:
        try:
            p = subprocess.run([ro, "-h", path], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return None
        rc, out = p.returncode, p.stdout
    if rc != 0:
        return None
    arches = {ln.split(":", 1)[1].strip() for ln in out.splitlines()
              if ln.strip().startswith("Arch:")}
    if len(arches) == 1:
        return next(iter(arches))
    if len(arches) > 1:
        return "MIXED(" + ",".join(sorted(arches)) + ")"
    return None


def check(lane, host, mods, arch_of_=arch_of):
    """纯逻辑（自证注入 arch_of_）。返回 (problems, stats)。"""
    problems, stats = [], {}
    want = expected_arch(lane)
    if want is None:
        return ["车道名 %r 未知 ⇒ 不知道期望哪个架构（LANE_EXPECT 表里没有）" % lane], stats

    # ① 宿主
    if host:
        got = arch_of_(host)
        stats["host"] = got
        if got is None:
            problems.append("宿主读不到架构：%s（文件不在 / readobj 不可用）— fail-closed，不当通过"
                            % host)
        elif got != want:
            problems.append("宿主架构错档：期望 %s，实得 %s（%s）"
                            % (want, got, os.path.basename(host)))
    else:
        problems.append("没给 --host ⇒ 判据①没做（零值守卫：空断言面不是通过）")

    # ② 附属模块（每个都要同档；MIXED 一律红）
    n_mod = 0
    for m in mods:
        if not os.path.isfile(m):
            problems.append("附属模块不在：%s — fail-closed，不当通过" % m)
            continue
        got = arch_of_(m)
        n_mod += 1
        if got is None:
            problems.append("附属模块读不到架构：%s" % m)
        elif got == "SIDE":
            # side module（dylink.0）：字节流里**没有**架构信息（实测：无 memory 段、
            # 无 import memory）⇒ 只能断言"它由宿主加载 ⇒ 必须与宿主同档"。
            # 宿主缺档/错档时上面 ① 已经报过 ⇒ 这里只要宿主对，就按宿主档接受，
            # 并**记录**（stats）让报告能看出"这条是靠宿主档推的，不是直接读出来的"。
            hg = stats.get("host")
            if hg == "SIDE":
                problems.append("附属模块 %s 是 side module，但宿主也是 side module ⇒ "
                                "没有可推出的档（判据退化）" % os.path.basename(m))
            else:
                stats.setdefault("side_mods", []).append(os.path.basename(m))
        elif got != want:
            problems.append("附属模块错档：%s 期望 %s，实得 %s" % (os.path.basename(m), want, got))
    stats["mods"] = n_mod
    if not mods:
        problems.append("没给 --mod ⇒ 判据②没做（零值守卫）")
    return problems, stats


# ── 自证（F1：三类用例：正常不报 / 该报的必须报 / 空输入必须报）────────────────
def _fake(arch_map):
    def _a(p):
        return arch_map.get(os.path.basename(p))
    return _a


def _selftest():
    ok, bad = [], []
    t = "omc.wasm"
    tmp = []

    # ① 正常：w64 宿主 + 同档模块 ⇒ 不报
    d = os.path.join("/tmp", "lane-purity-fix")
    os.makedirs(d, exist_ok=True)
    for f in ("omc.wasm", "runtime.wasm"):
        open(os.path.join(d, f), "w").close()
        tmp.append(os.path.join(d, f))
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "wasm64", "runtime.wasm": "wasm64"}))
    ok.append(("w64 宿主 + 同档模块 ⇒ 不报", not p))

    # ② ★ 反向：wasm32 宿主冒充 w64 ⇒ 必须报
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "wasm32", "runtime.wasm": "wasm64"}))
    ok.append(("★ 宿主错档 ⇒ 必须报", any("宿主架构错档" in x for x in p)))

    # ③ ★ 反向：模块错档 ⇒ 必须报（宿主对）
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "wasm64", "runtime.wasm": "wasm32"}))
    ok.append(("★ 模块错档 ⇒ 必须报", any("附属模块错档" in x for x in p)))

    # ④ ★ MIXED ⇒ 必须报（一包里混档）
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "MIXED(wasm32,wasm64)", "runtime.wasm": "wasm64"}))
    ok.append(("★ MIXED ⇒ 必须报", any("错档" in x for x in p)))

    # ⑤ ★ 零值守卫：没给 host ⇒ 必须报
    p, _ = check("w64", "", [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"runtime.wasm": "wasm64"}))
    ok.append(("★ 没给 --host ⇒ 必须报（零值守卫）", any("零值守卫" in x for x in p)))

    # ⑥ ★ 零值守卫：没给 mod ⇒ 必须报
    p, _ = check("w64", os.path.join(d, t), [],
                 arch_of_=_fake({"omc.wasm": "wasm64"}))
    ok.append(("★ 没给 --mod ⇒ 必须报（零值守卫）", any("零值守卫" in x for x in p)))

    # ⑦ ★ 读不到架构 ⇒ fail-closed 报
    p, _ = check("w64", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({}))
    ok.append(("★ 读不到架构 ⇒ fail-closed 报", any("读不到" in x for x in p)))

    # ⑧ ★ 未知档名 ⇒ 必须报
    p, _ = check("nonsense-lane", os.path.join(d, t), [os.path.join(d, "runtime.wasm")],
                 arch_of_=_fake({"omc.wasm": "wasm64"}))
    ok.append(("★ 未知档名 ⇒ 必须报", any("未知" in x for x in p)))

    # ⑨ ★★ wasm 专用判据（本仓 2026-10-13 加）：用**真 wasm 字节**造夹具，不只测假函数。
    #   为什么必须真字节：这条判据的存在理由就是"wasm 文件没有 Arch: 头" ⇒ 用假的 arch_of_
    #   测它等于什么都没测（"替身不能比真实对象松"）。
    def _wasm_bytes(memory64=False, with_max=True):
        """编一个最小 wasm：magic+version + memory 段（id=5, 1 个 memory, limits flags）。"""
        flags = 0x00 | (0x01 if with_max else 0) | (0x04 if memory64 else 0)
        body = bytes([0x01]) + bytes([flags])
        if with_max:
            body += bytes([0x01, 0x01])       # min=1(pages), max=1 —— LEB128 单字节
        else:
            body += bytes([0x01])
        sec = bytes([0x05]) + bytes([len(body)]) + body
        return b"\x00asm\x01\x00\x00\x00" + sec

    def _side_module_bytes(memory64=False):
        """造一个 **side module（dylink.0）夹具**：与真实产物同形 —— custom 段名含 "dylink"，
        **无 memory 段、无 import memory**（实测本仓 web/wasm-blobs/*.wasm 就是这个段表）。
        字节流的架构信息**不存在**于这种模块里 ⇒ 判据只能是"必须与宿主同档"。
        """
        name = b"dylink.0"
        custom = bytes([len(name)]) + name + b"\x00\x00\x00\x00"
        sec = bytes([0x00]) + bytes([len(custom)]) + custom
        # 再来一个空 export 段，让段表更像真的
        sec += bytes([0x07, 0x01, 0x00])
        return b"\x00asm\x01\x00\x00\x00" + sec

    f32 = os.path.join(d, "fix32.wasm"); f64 = os.path.join(d, "fix64.wasm")
    with open(f32, "wb") as fh: fh.write(_wasm_bytes(memory64=False))
    with open(f64, "wb") as fh: fh.write(_wasm_bytes(memory64=True))
    tmp += [f32, f64]
    ok.append(("★ wasm 判据：真 wasm32 字节 ⇒ 读成 wasm32", arch_of(f32) == "wasm32"))
    ok.append(("★ wasm 判据：真 wasm64 字节（memory64 标志）⇒ 读成 wasm64", arch_of(f64) == "wasm64"))
    ok.append(("★ wasm 判据：无 memory64 标志的都判 wasm32（不给错档放行）",
               arch_of(f32) != "wasm64"))
    junk = os.path.join(d, "junk.wasm")
    with open(junk, "wb") as fh: fh.write(b"not a wasm at all")
    tmp.append(junk)
    ok.append(("★ wasm 判据：非 wasm 字节 ⇒ 读不到（None，不许猜成 wasm32）", arch_of(junk) is None))
    empty = os.path.join(d, "empty.wasm")
    open(empty, "wb").close(); tmp.append(empty)
    ok.append(("★ wasm 判据：空文件 ⇒ 读不到（零值守卫）", arch_of(empty) is None))
    ok.append(("★ wasm 判据：不存在的路径 ⇒ 读不到（不许抛异常）",
               arch_of(os.path.join(d, "definitely-missing.wasm")) is None))
    # ★★ side module（import 宿主 memory 的形态；本仓 web/wasm-blobs/*.wasm 实测就是这种）
    sm32 = os.path.join(d, "side32.wasm"); sm64 = os.path.join(d, "side64.wasm")
    with open(sm32, "wb") as fh: fh.write(_side_module_bytes(memory64=False))
    with open(sm64, "wb") as fh: fh.write(_side_module_bytes(memory64=True))
    tmp += [sm32, sm64]
    ok.append(("★ wasm 判据：side module ⇒ 标记 SIDE（由宿主档定，不瞎猜）",
               arch_of(sm32) == "SIDE"))

    # ★★ import-memory 形态（2026-10-15 真产物暴露的解析 bug 回归用例）：
    #   fmi-simulator/vendor/js-component-bindgen-component.core2.wasm import 了
    #   env.memory（flags=0x00）⇒ 架构应从 **import 段**读出。旧解析**漏读第二个
    #   name**（spec：每条 import = module 名 + 字段名**两个**字符串）⇒ 字段错位
    #   ⇒ 遇"未知 kind" break ⇒ env.memory 永远读不到 ⇒ 闸门假红"读不到架构"。
    #   用同形字节夹具钉住：多导入 + 双 name + import memory 在**最后**一条。
    def _import_mem_bytes(memory64=False, n_func_imports=3):
        """造一个 import 段里既有函数导入又有 memory 导入的最小 wasm（无 memory 段）。"""
        imps = b""
        # 函数导入垫背：module="wasi:io/streams@0.2.3" name="f<i>"（**两个 name**）
        for i in range(n_func_imports):
            mod = b"wasi:io/streams@0.2.3"
            nm = b"f%d" % i
            imps += bytes([len(mod)]) + mod + bytes([len(nm)]) + nm + b"\x00\x00"  # kind=func, typeidx=0
        # memory 导入：module="env" name="memory" kind=0x02 limits
        mflags = 0x01 | (0x04 if memory64 else 0)      # has_max (+ memory64)
        mem = b"\x03env\x06memory" + b"\x02" + bytes([mflags, 0x01, 0x01])  # min=1,max=1
        imps += mem
        body = bytes([1 + n_func_imports]) + imps      # 导入计数（uleb 单字节）
        sec = bytes([0x02]) + bytes([len(body)]) + body
        # type 段垫底（func typeidx=0 要存在才算同形；判据不读它，只为形状真）
        #   段体 = count(1) + 0x60(params=0)(results=0)
        tsec = bytes([0x01, 0x04, 0x01, 0x60, 0x00, 0x00])
        return b"\x00asm\x01\x00\x00\x00" + tsec + sec
    im32 = os.path.join(d, "impmem32.wasm"); im64 = os.path.join(d, "impmem64.wasm")
    with open(im32, "wb") as fh: fh.write(_import_mem_bytes(memory64=False))
    with open(im64, "wb") as fh: fh.write(_import_mem_bytes(memory64=True))
    tmp += [im32, im64]
    ok.append(("★ wasm 判据：import 段 memory（双 name）⇒ 读成 wasm32（core2.wasm 假红的回归用例）",
               arch_of(im32) == "wasm32"))
    ok.append(("★ wasm 判据：import 段 memory 带 memory64 标志 ⇒ 读成 wasm64",
               arch_of(im64) == "wasm64"))
    # 端到端：import-memory 模块配 wasm32 档 ⇒ 不报（它自己的架构读得出来了）
    p_im, _ = check("wasm32", f32, [im32], arch_of_=arch_of)
    ok.append(("★ 端到端：import-memory 模块 + wasm32 档 ⇒ 不报", not p_im))
    # 反向：import-memory **wasm64** 模块喂 wasm32 档 ⇒ 必须报
    p_im64, _ = check("wasm32", f32, [im64], arch_of_=arch_of)
    ok.append(("★ 反向：import-memory wasm64 模块喂 wasm32 档 ⇒ 必须报", bool(p_im64)))

    # 端到端：side module 配同档宿主 ⇒ 不报；且 stats 里能看出"这是靠宿主档推的"
    p_side, st_side = check("wasm32", f32, [sm32], arch_of_=arch_of)
    ok.append(("★ 端到端：side module + wasm32 宿主 ⇒ 不报（同档要求满足）", not p_side))
    ok.append(("★ 端到端：报告里记明 side module 是靠宿主档推的",
               os.path.basename(sm32) in st_side.get("side_mods", [])))
    # ★ 反向：宿主也是 side module ⇒ 判据退化，必须报（不许"两个都读不到"算过）
    p_deg, _ = check("wasm32", sm32, [sm32], arch_of_=arch_of)
    ok.append(("★ 反向：宿主自己也是 side module ⇒ 必须报（判据退化不许放行）",
               any("判据退化" in x for x in p_deg)))
    # 端到端：wasm64 夹具喂 w64 档 ⇒ 不报（正例）；喂 wasm32 档 ⇒ 必须报（反向）
    p32, _ = check("wasm32", f32, [f32], arch_of_=arch_of)
    ok.append(("★ 端到端：真 wasm32 夹具喂 wasm32 档 ⇒ 不报", not p32))
    p64bad, _ = check("wasm32", f64, [f64], arch_of_=arch_of)
    ok.append(("★ 端到端：真 wasm64 夹具喂 wasm32 档 ⇒ 必须报", any("错档" in x for x in p64bad)))

    for f in tmp:
        try:
            os.unlink(f)
        except OSError:
            pass
    nbad = sum(1 for _, good in ok if not good)
    for name, good in ok:
        print(("PASS | " if good else "fail | ") + name)
    print("=== check-lane-purity 自证：%d PASS / %d fail ===" % (len(ok) - nbad, nbad))
    return nbad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="")
    ap.add_argument("--host", default="")
    ap.add_argument("--mod", action="append", default=[])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.lane:
        print("FATAL: 必须给 --lane", file=sys.stderr)
        return 2
    problems, stats = check(a.lane, a.host, a.mod)
    for p in problems:
        print("  ✗ %s" % p, file=sys.stderr)
    if problems:
        print("架构**不纯**（%d 条）⇒ 别上线" % len(problems), file=sys.stderr)
        return 1
    print("架构纯度 OK：lane=%s 期望=%s 宿主=%s 模块=%d 个" %
          (a.lane, expected_arch(a.lane), stats.get("host"), stats.get("mods", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
