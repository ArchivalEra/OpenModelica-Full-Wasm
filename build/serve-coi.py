#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — 开发站点服务（**必须**带头：COOP/COEP）。

为什么不能用 `python3 -m http.server`：它发不出 `Cross-Origin-Opener-Policy` 与
`Cross-Origin-Embedder-Policy` ⇒ 浏览器不给 `crossOriginIsolated` ⇒
SharedArrayBuffer / 多线程档**静默**落回基础档（不报错）。姊妹仓实测教训，本仓照抄纪律。

**只发静态文件，不做任何计算**（纯客户端铁律：omc 恒跑在浏览器 wasm 内）。

用法：python3 build/serve-coi.py [端口] [站点目录] [--quiet]
"""
import http.server
import socketserver
import sys
import os


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    root = sys.argv[2] if len(sys.argv) > 2 else "/mnt/hdd/openmodelica-wasm-build/site-omc"
    quiet = "--quiet" in sys.argv

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

        def end_headers(self):
            # ★ 这三个头是硬要求（见文件头注释）
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
            self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
            # 允许**受控的**跨源取件（同页集成时会用到两个站点；同源部署则用不到）
            self.send_header("Access-Control-Allow-Origin", "*")
            # wasm 要按 MIME 正确服务（有些浏览器对 application/wasm 严格）
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def guess_type(self, path):
            if path.endswith(".wasm"):
                return "application/wasm"
            if path.endswith(".mjs"):
                return "text/javascript"
            return super().guess_type(path)

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
        print(f"serving {root} on http://127.0.0.1:{port}/ (COOP/COEP on)", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
