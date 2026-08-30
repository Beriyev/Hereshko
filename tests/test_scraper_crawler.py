import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.services.scraper.crawler import crawl


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        page_html = {
            "/": (
                '<html><body><p>Home page. ' +
                ("Site content for home. " * 40) +
                '</p>'
                '<a href="/about">about</a>'
                '<a href="/contact">contact</a>'
                '<a href="/">self</a>'
                '<a href="https://external.com/x">external</a>'
                '</body></html>'
            ),
            "/about": '<html><body><p>' + ("About content here. " * 40) + '</p></body></html>',
            "/contact": '<html><body><p>' + ("Contact content here. " * 40) + '</p></body></html>',
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


def test_crawl_site():
    with TestServer() as base:
        results = asyncio.run(crawl(start_url=base + "/"))
    urls = {r["url"] for r in results}
    assert base + "/" in urls, f"root missing from {urls}"
    assert base + "/about" in urls, f"about missing from {urls}"
    assert base + "/contact" in urls, f"contact missing from {urls}"
    assert base + "/dead" not in urls, "dead page should be excluded"
    assert "external.com" not in str(urls), "external link should be excluded"
    assert len(results) == len(urls), "duplicate urls in results"
    for r in results:
        assert r["content"], f"empty content for {r['url']}"
    assert len(results) <= 12, f"exceeded max pages: {len(results)}"
    print(f"RESULT URLS: {sorted(urls)}")
    print("test_crawl_site OK")


if __name__ == "__main__":
    test_crawl_site()
    print("ALL TESTS PASSED")
