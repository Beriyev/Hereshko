import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.services.scraper.links import normalize_url, is_same_domain, extracted_links


def check(name, actual, expected):
    status = "OK" if actual == expected else "FAIL"
    print(f"{status}: {name} -> {actual!r}")
    return status == "OK"


all_ok = True

all_ok &= check(
    "normalize trailing slash + strip fragment + default port",
    normalize_url("https://example.com/"),
    "https://example.com/",
)
all_ok &= check(
    "normalize drop default https port 443",
    normalize_url("https://example.com:443/path#frag"),
    "https://example.com/path",
)
all_ok &= check(
    "normalize keep non-default port",
    normalize_url("http://example.com:8080/path"),
    "http://example.com:8080/path",
)
all_ok &= check(
    "is_same_domain true",
    is_same_domain("https://example.com/", "https://example.com/a"),
    True,
)
all_ok &= check(
    "is_same_domain false (subdomain)",
    is_same_domain("https://example.com/", "https://evil.com/"),
    False,
)

html = """
<html><body>
<a href="/about">about</a>
<a href="https://example.com/contact#top">contact</a>
<a href="https://external.com/x">external</a>
<a href="javascript:void(0)">js</a>
<a href="mailto:a@b.com">mail</a>
<a href="#fragment">frag</a>
<a href="/about">dup about</a>
</body></html>
"""
links = extracted_links(html, "https://example.com/")
all_ok &= check(
    "extracted_links content (includes same-origin + external; crawler filters origin)",
    links,
    {"https://example.com/about", "https://example.com/contact", "https://external.com/x"},
)

print("ALL OK" if all_ok else "SOME FAILED")
