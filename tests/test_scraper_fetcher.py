import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.services.scraper.fetcher import fetch, fetch_static, fetch_dynamic
from app.services.scraper.scraper_config import STATIC_LENGTH_THRESHOLD


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/dead":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/short":
            body = b"<html><body>hi</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        long_text = "Real content here. " * 60
        body = ("<html><head><title>Test Page</title></head><body><h1>Hello World</h1>"
                f"<p>{long_text}</p></body></html>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class TestServer:
    def __enter__(self):
        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        return "http://127.0.0.1:%d" % self.port

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()


def test_fetch_static_good():
    with TestServer() as base:
        html, status = asyncio.run(fetch_static(base + "/"))
    assert status == 200
    assert "Hello World" in html
    print("test_fetch_static_good OK")


def test_fetch_static_404_returns_empty():
    with TestServer() as base:
        html, status = asyncio.run(fetch_static(base + "/dead"))
    assert html == ""
    assert status == 404
    print("test_fetch_static_404_returns_empty OK")


def test_fetch_static_short_page():
    with TestServer() as base:
        html, status = asyncio.run(fetch_static(base + "/short"))
    assert html != ""
    assert status == 200
    assert len(html) < STATIC_LENGTH_THRESHOLD
    print("test_fetch_static_short_page OK")


def test_fetch_good_returns_html():
    with TestServer() as base:
        html = asyncio.run(fetch(base + "/"))
    assert "Hello World" in html
    print("test_fetch_good_returns_html OK")


def test_fetch_short_falls_back_to_dynamic():
    with TestServer() as base:
        html = asyncio.run(fetch(base + "/short"))
    assert "hi" in html and html != ""
    print("test_fetch_short_falls_back_to_dynamic OK")


def test_fetch_dead_returns_empty():
    with TestServer() as base:
        html = asyncio.run(fetch(base + "/dead"))
    assert html == ""  # 404 returns empty, not a rendered DOM
    print("test_fetch_dead_returns_empty OK")


def test_fetch_static_dead_returns_empty():
    with TestServer() as base:
        html, status = asyncio.run(fetch_static(base + "/dead"))
    assert html == ""
    assert status == 404
    print("test_fetch_static_dead_returns_empty OK")


if __name__ == "__main__":
    test_fetch_static_good()
    test_fetch_static_404_returns_empty()
    test_fetch_static_short_page()
    test_fetch_good_returns_html()
    test_fetch_short_falls_back_to_dynamic()
    test_fetch_dead_returns_empty()
    test_fetch_static_dead_returns_empty()
    print("ALL TESTS PASSED")
