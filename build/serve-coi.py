#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — 开发站点服务（**必须**带头：COOP/COEP）。

为什么不能用 `python3 -m http.server`：它发不出 `Cross-Origin-Opener-Policy` 与
`Cross-Origin-Embedder-Policy` ⇒ 浏览器不给 `crossOriginIsolated` ⇒
SharedArrayBuffer / 多线程档**静默**落回基础档（不报错）。姊妹仓实测教训，本仓照抄纪律。

**只发静态文件，不做任何计算**（纯客户端铁律：omc 恒跑在浏览器 wasm 内）。

## 缓存头：`no-cache` + `ETag`（必须重验），**不是** `no-store`（2026-10-29 实测改）

原来这里发的是 `Cache-Control: no-store`，而它上面那行注释写的是 **MIME** —— 头放错了位置。
后果（实测，`test/browser/measure-omc-boot.mjs`，CDP `fromDiskCache` + `encodedDataLength`）：

| 响应头 | 第 1 次 | 第 2/3 次刷新（同一 profile） |
|---|---|---|
| `no-store` | 整份走网络 | **整份再走网络**（缓存被禁用） |
| 不发缓存头 | 整份 | 视 `Last-Modified` 启发式，不可靠 |
| 只 `no-cache`、无 ETag | 整份 | **整份**（要求重验却没凭据可带） |
| **`no-cache` + `ETag`（本仓用这个）** | 整份 | **几百字节**（条件请求 → 304） |

74 MB 的引擎**每次刷新都重下**是不可接受的产品行为（弱网下 boot 以分钟计）。

⚠️ `ETag` 与 `Cache-Control: no-cache` **成对才有效**。只发 `no-cache` 是"要求重验却不给
凭据"，浏览器只能整份拿（宿主 mail/031 §2 实测过这个形状）。

为什么选 `no-cache` 而不是"允许缓存"：本仓纪律是**"改完程序用老产物跑"必须不可能**。
`no-cache` = 每次回来问一句，没变就 304，变了就 200。

用法：python3 build/serve-coi.py [端口] [站点目录] [--quiet]
       python3 build/serve-coi.py --selftest
"""
import http.server
import socketserver
import sys
import os

# ── 契约字符串的**唯一产地**（GitRoll #22：MIME 字面量重复 ⇒ 写错会**静默**降级
#    instantiateStreaming 到非流式，正是上次踩过的坑类）──
MIME_WASM = "application/wasm"
MIME_MJS = "text/javascript"

# 自证夹具的固定形状（#23/#24：同一字面量重复 4 次 ⇒ 提出来）。它们是**夹具输入**，
# 不是被测对象；放一处，改一处即全改。
FIX_WASM_PATH = "/omc/x_bg.wasm"
FIX_ETAG = 'W/"1-2"'
DETAIL_SEP = "  ["                       # chk() 的 detail 前缀（#25 一族）
STATUS_FMT = "status=%s"                 # #27


# ── 头逻辑（纯函数：自证可注入，不必起服务器）────────────────────────────────
def extra_headers(etag=None):
    """返回 [(名字, 值)] 的**有序**列表；`end_headers` 照单发送。

    ★ 形参里**没有** path（GitRoll #78）：这些头（COI / CORS / 缓存）与请求路径无关
    —— 带个不用的形参只会让下一个人以为"头会随路径变"。MIME 才按路径判，
    那在 `content_type_override`。

    `etag` 给了才发 `ETag` + `Cache-Control: no-cache` —— **二者成对**（理由见文件头）。
    """
    out = [
        # ★ 这三个头是硬要求（见文件头注释）
        ("Cross-Origin-Opener-Policy", "same-origin"),
        ("Cross-Origin-Embedder-Policy", "require-corp"),
        ("Cross-Origin-Resource-Policy", "cross-origin"),
        # 允许**受控的**跨源取件（同页集成时会用到两个站点；同源部署则用不到）
        ("Access-Control-Allow-Origin", "*"),
    ]
    if etag:
        # ★ 不许 no-store（会让 74 MB 每次重下）；只发 no-cache 而无 ETag 也无效（见上）
        out.append(("ETag", etag))
        out.append(("Cache-Control", "no-cache"))
    return out


def etag_for(st):
    """由 stat 结果派生的弱 ETag（size + mtime_ns）—— 不读文件内容（74 MB 不重复哈希）。"""
    return 'W/"%x-%x"' % (st.st_size, st.st_mtime_ns)


def content_type_override(path):
    """返回 MIME 覆盖或 None。wasm 必须是 `application/wasm`（instantiateStreaming 认它）。"""
    ext = os.path.splitext((path or "").split("?")[0])[1].lower()
    if ext == ".wasm":
        return MIME_WASM
    if ext == ".mjs":
        return MIME_MJS
    return None


def etag_of_path(path):
    """路径是常规文件 ⇒ 它的 ETag；否则 None。集中处理"stat 失败"这一种分支。"""
    try:
        if os.path.isfile(path):
            return etag_for(os.stat(path))
    except OSError:
        return None
    return None


# ── 自证（三类用例：正常不报 / 该报的必须报 / 空输入必须报）────────────────────
def selftest():
    fails = []
    ok = [0]

    def chk(name, cond, detail=""):
        if cond:
            ok[0] += 1
            print("ok   %s" % name)
        else:
            fails.append(name)
            print("FAIL %s%s" % (name, (DETAIL_SEP + detail + "]") if detail else ""))

    _selftest_headers(chk)
    _selftest_over_http(chk, ok, fails)

    print("=== %d PASS / %d fail ===" % (ok[0], len(fails)))
    return 1 if fails else 0


def _selftest_headers(chk):
    """纯字符串断言：证明"头拼对了"（不含行为）。"""
    h = dict(extra_headers(etag=FIX_ETAG))
    chk("有 COOP", h.get("Cross-Origin-Opener-Policy") == "same-origin")
    chk("有 COEP", h.get("Cross-Origin-Embedder-Policy") == "require-corp")
    chk("有 CORP", h.get("Cross-Origin-Resource-Policy") == "cross-origin")
    chk("给了 etag ⇒ 发 ETag", h.get("ETag") == FIX_ETAG, "实得 %r" % h.get("ETag"))
    chk("Cache-Control 是 no-cache（必须重验）", h.get("Cache-Control") == "no-cache",
        "实得 %r" % h.get("Cache-Control"))
    chk("★ 反向：不许发 no-store（74 MB 每次重下的根因）",
        "no-store" not in h.get("Cache-Control", ""), "实得 %r" % h.get("Cache-Control"))
    chk("二层 MIME：wasm ⇒ application/wasm",
        content_type_override(FIX_WASM_PATH) == MIME_WASM)
    chk("二层 MIME：mjs ⇒ text/javascript",
        content_type_override("/x.mjs") == MIME_MJS)

    # 该报的必须报：坏头套上去，必须被抓
    bad = dict(extra_headers(etag=FIX_ETAG))
    bad["Cache-Control"] = "no-store"
    chk("★ 该报（坏头 no-store）必须被抓", "no-store" in bad.get("Cache-Control", ""),
        "这条是自证仪器：坏了还报 ok 说明检查器恒真")

    # ★ 只发 no-cache 却没有 ETag —— 宿主 mail/031 §2 的实测形状：无凭据 ⇒ 整份重传
    honly = dict(extra_headers(etag=None))
    chk("★ 无 etag ⇒ 不发 Cache-Control（避免'让重验却没凭据'）",
        "Cache-Control" not in honly, "实得 %r" % honly.get("Cache-Control"))

    # 空输入必须报：路径为空/无扩展名时不崩、不丢 COI 头
    for p in ("", None, "/", "/noext", "/x.wasm?v=1"):
        hh = dict(extra_headers(etag=FIX_ETAG))
        chk("空输入 %r 仍有 COI 三件 + no-cache" % (p,),
            hh.get("Cross-Origin-Opener-Policy") == "same-origin"
            and hh.get("Cross-Origin-Embedder-Policy") == "require-corp"
            and hh.get("Cache-Control") == "no-cache")
        chk("空输入 %r 的 MIME 判定不崩" % (p,),
            content_type_override(p) in (None, MIME_WASM, MIME_MJS))
    chk("空输入：无扩展名 ⇒ 不覆盖 MIME", content_type_override("") is None)
    chk("空输入：查询串不干扰 MIME 判定",
        content_type_override(FIX_WASM_PATH + "?v=1") == MIME_WASM)
    # 空输入：etag_of_path 对不存在的路径必须回 None（不许编一个假 ETag）
    chk("空输入：不存在的路径 ⇒ ETag 为 None", etag_of_path("/nonexistent/xyz.bin") is None)


def _selftest_over_http(chk, ok, fails):
    """★ 端到端：真起服务、真发条件请求。

    为什么必须有这一组：上面那些都是**纯字符串断言** —— 它们证明"头拼对了"，却证明不了
    "客户端带 `If-None-Match` 时服务真的回 304、真的不传文件体"。mail/031 §2 的教训正是
    这个形状：发了 `no-cache` 却没有 ETag/304 路径 ⇒ 浏览器仍整份重传，而只看头的断言全绿。
    （"测了头 ≠ 测了行为"）
    """
    import tempfile
    import threading
    import urllib.request

    tmp = tempfile.mkdtemp()
    body = os.path.join(tmp, "a.bin")
    with open(body, "wb") as fh:
        fh.write(b"hello-wasm-body")

    handler = _make_handler(tmp, quiet=True)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d/a.bin" % port
    try:
        _selftest_http_cases(chk, base, body)
    except Exception as e:
        chk("端到端：跑通（异常 ⇒ 该红）", False, repr(e))
    finally:
        srv.shutdown()
        srv.server_close()
    return ok, fails


def _selftest_http_cases(chk, base, body):
    """端到端的三个方向：首请求 / 同 ETag ⇒ 304 / 异 ETag ⇒ 200。"""
    import urllib.request

    r1 = urllib.request.urlopen(base, timeout=10)
    chk("端到端：首请求 200", r1.status == 200, STATUS_FMT % r1.status)
    etag = r1.headers.get("ETag")
    chk("端到端：响应带 ETag", bool(etag), "ETag=%r" % etag)
    chk("端到端：no-cache", r1.headers.get("Cache-Control") == "no-cache")
    chk("端到端：首请求真的传了文件体",
        int(r1.headers.get("Content-Length") or 0) == os.path.getsize(body))
    chk("端到端：COI 三件齐",
        r1.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
        and r1.headers.get("Cross-Origin-Embedder-Policy") == "require-corp")
    r1.close()

    status2, payload2 = _conditional_get(base, etag)
    chk("★ 端到端：同 ETag ⇒ 304（真回，不是头拼对）", status2 == 304, STATUS_FMT % status2)
    chk("★ 端到端：304 不传文件体", len(payload2) == 0, "payload=%d B" % len(payload2))

    # 反向：换了 ETag ⇒ 必须 200 且带体（否则"永远 304"会静默发老产物）
    r3 = urllib.request.urlopen(
        urllib.request.Request(base, headers={"If-None-Match": 'W/"bogus-0"'}), timeout=10)
    chk("★ 反向：ETag 不匹配 ⇒ 200（不许恒 304）", r3.status == 200, STATUS_FMT % r3.status)
    chk("★ 反向：换了 ETag 必须传新体", len(r3.read()) == os.path.getsize(body))
    r3.close()


def _conditional_get(base, etag):
    """带 If-None-Match 发一次 GET，返回 (状态码, 响应体)。304 走异常分支取 code。"""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(base, headers={"If-None-Match": etag})
    try:
        r = urllib.request.urlopen(req, timeout=10)
        status, payload = r.status, r.read()
        r.close()
        return status, payload
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ── 正式服务：handler 由工厂建（`main()` 只做参数解析，复杂度不至于堆进去）────────
def _make_handler(root, quiet):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

        def end_headers(self):
            for name, value in extra_headers(etag_of_path(self.translate_path(self.path))):
                self.send_header(name, value)
            super().end_headers()

        def send_head(self):
            """补 304：带 If-None-Match 且与本文件当前 ETag 相同 ⇒ 只回 304，不传体。

            ⚠️ 只 `send_response(304)`，**别**再发 ETag/Cache-Control —— `end_headers`
            会按当前路径重发一遍（实测会出两份同名头）。
            """
            path = self.translate_path(self.path)
            inm = self.headers.get("If-None-Match")
            if inm and inm == etag_of_path(path):
                self.send_response(304)
                self.end_headers()
                return None
            return super().send_head()

        def guess_type(self, path):
            return content_type_override(path) or super().guess_type(path)

        def log_message(self, *a):
            # 故意不打印（`--quiet` 时）：验收脚本要读自己的机器行，访问日志只会刷屏。
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

    return H


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    root = sys.argv[2] if len(sys.argv) > 2 else "/mnt/hdd/openmodelica-wasm-build/site-omc"
    quiet = "--quiet" in sys.argv

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), _make_handler(root, quiet)) as httpd:
        print(f"serving {root} on http://127.0.0.1:{port}/ (COOP/COEP on, ETag + no-cache)",
              flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
