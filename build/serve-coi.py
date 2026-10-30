#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — 开发站点服务（**必须**带头：COOP/COEP）。

为什么不能用 `python3 -m http.server`：它发不出 `Cross-Origin-Opener-Policy` 与
`Cross-Origin-Embedder-Policy` ⇒ 浏览器不给 `crossOriginIsolated` ⇒
SharedArrayBuffer / 多线程档**静默**落回基础档（不报错）。姊妹仓实测教训，本仓照抄纪律。

**只发静态文件，不做任何计算**（纯客户端铁律：omc 恒跑在浏览器 wasm 内）。

## 缓存头：`no-cache`（必须重验），**不是** `no-store`（2026-10-29 实测改）

原来这里发的是 `Cache-Control: no-store`，而它上面那行注释写的是 **MIME** —— 头放错了位置。
后果（实测，`test/browser/measure-omc-boot.mjs`，CDP `fromDiskCache` + `encodedDataLength`）：

| `Cache-Control` | 第 1 次 | 第 2/3 次刷新（同一 profile） |
|---|---|---|
| `no-store` | 74,579,787 B 走网络 | **74,579,787 B 再走网络**（缓存被禁用） |
| 不发该头 | 74,579,686 B | 0 B（磁盘缓存命中） |
| `no-cache` | 74,579,711 B | **213 B**（条件请求 → 304） |

74 MB 的引擎**每次刷新都重下**是不可接受的产品行为（弱网下 `OMC_BOOT_KBPS=600` 实测
boot 中位数 **199,926 ms**，其中 wasm 传输 121,406 ms）。

为什么选 `no-cache` 而不是干脆不发头（沿用浏览器的启发式缓存）：本仓的纪律是
**"改完程序用老产物跑"必须不可能**（三层 SHA / 全量回归的前提）。`no-cache` 的语义是
"**每次都要回来问一句**"——没变 ⇒ 304 只花 213 B；变了 ⇒ 200 拉新字节。
启发式缓存（不发头）会在 `Last-Modified` 老旧时**直接用旧的且不问**，正好踩那条纪律。

⚠️ `no-cache` 依赖 `Last-Modified` 准确。用 rsync 铺站点时**别带 `-t`/`--times` 保留旧时间戳**
（那会让"文件换了、时间没变"⇒ 304 ⇒ 浏览器拿旧的）。本仓 `build/promote-site.sh` 走的是
`--verify` 逐件 sha 对账，产物换了 sha 必然变；这是那道闸门存在的理由。

用法：python3 build/serve-coi.py [端口] [站点目录] [--quiet]
       python3 build/serve-coi.py --selftest
"""
import http.server
import socketserver
import sys
import os

# ── 头逻辑（纯函数：自证可注入，不必起服务器）────────────────────────────────
# 返回 [(名字, 值)] 的**有序**列表；`end_headers` 照单发送。
def extra_headers(path):
    ext = os.path.splitext((path or "").split("?")[0])[1].lower()
    out = [
        # ★ 这三个头是硬要求（见文件头注释）
        ("Cross-Origin-Opener-Policy", "same-origin"),
        ("Cross-Origin-Embedder-Policy", "require-corp"),
        ("Cross-Origin-Resource-Policy", "cross-origin"),
        # 允许**受控的**跨源取件（同页集成时会用到两个站点；同源部署则用不到）
        ("Access-Control-Allow-Origin", "*"),
        # ★ 必须重验、不许静默用缓存（理由见文件头）；**不许** no-store（会让 74 MB 每次重下）
        ("Cache-Control", "no-cache"),
    ]
    return out


def content_type_override(path):
    """返回 (mime,) 覆盖或 None。wasm 必须 application/wasm（instantiateStreaming 认它）。"""
    ext = os.path.splitext((path or "").split("?")[0])[1].lower()
    if ext == ".wasm":
        return "application/wasm"
    if ext == ".mjs":
        return "text/javascript"
    return None


def selftest():
    """三类用例：正常不报 / 该报的必须报 / 空输入必须报。返回退出码。"""
    fails = []
    ok = [0]

    def chk(name, cond, detail=""):
        if cond:
            ok[0] += 1
            print("ok   %s" % name)
        else:
            fails.append(name)
            print("FAIL %s%s" % (name, ("  [" + detail + "]") if detail else ""))

    # ① 正常：COI 三件 + no-cache，且**没有** no-store
    h = dict(extra_headers("/omc/x_bg.wasm"))
    chk("wasm 有 COOP", h.get("Cross-Origin-Opener-Policy") == "same-origin")
    chk("wasm 有 COEP", h.get("Cross-Origin-Embedder-Policy") == "require-corp")
    chk("wasm 有 CORP", h.get("Cross-Origin-Resource-Policy") == "cross-origin")
    chk("Cache-Control 是 no-cache（必须重验）", h.get("Cache-Control") == "no-cache",
        "实得 %r" % h.get("Cache-Control"))
    chk("★ 反向：不许发 no-store（74 MB 每次重下的根因）",
        "no-store" not in h.get("Cache-Control", ""), "实得 %r" % h.get("Cache-Control"))
    chk("二层 MIME：wasm ⇒ application/wasm",
        content_type_override("/omc/x_bg.wasm") == "application/wasm")
    chk("二层 MIME：mjs ⇒ text/javascript",
        content_type_override("/x.mjs") == "text/javascript")

    # ② 该报的必须报：把断言套到**已知坏**的形状上，它必须红
    bad = dict(extra_headers("/omc/x_bg.wasm")); bad["Cache-Control"] = "no-store"
    chk("★ 该报（坏头 no-store）必须被抓",
        not ("no-store" not in bad.get("Cache-Control", "")),
        "这条是自证仪器：坏了还报 ok 说明检查器恒真")

    # ③ 空输入必须报：路径为空/无扩展名时不能崩，也不能丢 COI 头
    for p in ("", None, "/", "/noext", "/x.wasm?v=1"):
        try:
            hh = dict(extra_headers(p))
        except Exception as e:
            chk("空输入 %r 不许崩" % (p,), False, repr(e))
            continue
        chk("空输入 %r 仍有 COI 三件 + no-cache" % (p,),
            hh.get("Cross-Origin-Opener-Policy") == "same-origin"
            and hh.get("Cross-Origin-Embedder-Policy") == "require-corp"
            and hh.get("Cache-Control") == "no-cache")
    chk("空输入：无扩展名 ⇒ 不覆盖 MIME", content_type_override("") is None)
    chk("空输入：查询串不干扰 MIME 判定",
        content_type_override("/omc/x_bg.wasm?v=1") == "application/wasm")

    print("=== %d PASS / %d fail ===" % (ok[0], len(fails)))
    return 1 if fails else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    root = sys.argv[2] if len(sys.argv) > 2 else "/mnt/hdd/openmodelica-wasm-build/site-omc"
    quiet = "--quiet" in sys.argv

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

        def end_headers(self):
            for name, value in extra_headers(self.path):
                self.send_header(name, value)
            super().end_headers()

        def guess_type(self, path):
            override = content_type_override(path)
            return override or super().guess_type(path)

        def log_message(self, *a):
            if not quiet:
                super().log_message(*a)

        def do_HEAD(self):
            # 支持 HEAD（验收/探针用 `curl -sI` 读头）
            try:
                f = self.send_head()
                if f:
                    f.close()
            except (ConnectionResetError, BrokenPipeError):
                pass

        def handle_one_request(self):
            # 单请求的连接重置（客户端提前断开，curl -sI 常见）**不许**打死整个服务
            # （实测踩到：一个 ConnectionResetError 让 ThreadingTCPServer 的进程退出了）
            try:
                super().handle_one_request()
            except (ConnectionResetError, BrokenPipeError, TimeoutError):
                self.close_connection = True

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), H) as httpd:
        print(f"serving {root} on http://127.0.0.1:{port}/ (COOP/COEP on, Cache-Control: no-cache)", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()