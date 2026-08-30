import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import uvicorn
from app.main import app


class SiteHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        page_html = {
            "/": (
                "<html><body><p>"
                + ("Home page content for testing the crawler. " * 40)
                + "</p>"
                '<a href="/about">about</a>'
                '<a href="/contact">contact</a>'
                '<a href="https://external.com/x">external</a>'
                "</body></html>"
            ),
            "/about": "<html><body><p>" + ("About content here. " * 40) + "</p></body></html>",
            "/contact": "<html><body><p>" + ("Contact content here. " * 40) + "</p></body></html>",
        }

        if self.path == "/dead":
            self.send_response(404)
            self.end_headers()
            return

        body = page_html.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


class EmptyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<html><body></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class DeadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


class TestServer:
    def __init__(self, handler):
        self.handler = handler

    def __enter__(self):
        self.server = HTTPServer(("127.0.0.1", 0), self.handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        return "http://127.0.0.1:%d" % self.port

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()


def post(api_base, url):
    return httpx.post(
        f"{api_base}/ingest/website",
        data={"url": url, "notebook_id": "nb-1"},
    )


def main():
    app_server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    t = threading.Thread(target=app_server.run, daemon=True)
    t.start()
    time.sleep(2)
    port = app_server.servers[0].sockets[0].getsockname()[1]
    api_base = f"http://127.0.0.1:{port}"

    with TestServer(SiteHandler) as site_base:
        r = post(api_base, site_base + "/")
        print("success status:", r.status_code, "body:", r.json())
        assert r.status_code == 200, r.text
        ids = r.json()["document_ids"]
        assert r.json()["status"] == "success"
        assert len(ids) == 3, f"expected 3, got {len(ids)}"
        print("OK: success path -> 3 document_ids")

    with TestServer(EmptyHandler) as site_base:
        r = post(api_base, site_base + "/")
        print("empty status:", r.status_code, "body:", r.json())
        assert r.status_code == 400, r.text
        print("OK: empty-content site -> 400")

    with TestServer(DeadHandler) as site_base:
        r = post(api_base, site_base + "/")
        print("dead status:", r.status_code, "body:", r.json())
        assert r.status_code == 400, r.text
        print("OK: 404 site -> 400")

    app_server.should_exit = True
    time.sleep(1)
    print("ROUTE TESTS OK")


if __name__ == "__main__":
    main()
