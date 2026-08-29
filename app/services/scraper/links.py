from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag, urlunparse

def normalize_url(url: str) -> str:
    parsed = urlparse(url=url)
    scheme = parsed.scheme
    host = parsed.hostname
    path = parsed.path
    port = parsed.port

    if not path:
        path = '/'

    if port is None or (scheme=='https' and port==443) or (scheme=='http' and port==80):
        netloc = host
    else:
        netloc = f"{host}:{port}"

    normalized_url = urlunparse(
        (
            scheme,
            netloc,
            path,
            parsed.params,
            parsed.query,
            ""
        )
    )

    return normalized_url

def is_same_domain(base: str, url: str) -> bool:
    base_parsed = urlparse(base)
    base_url = urlparse(url)

    base_host = base_parsed.hostname
    url_host = base_url.hostname

    if base_host is None:
        return False
    if base_host == url_host:
        return True
    else:
        return False


def extracted_links(html: str, url: str) -> set[str]:
    soup = BeautifulSoup(html,"html.parser")
    link_set: set[str] = set()

    for tag in soup.find_all('a'):
        href = tag.get("href")

        if not isinstance(href,str):
            continue

        href = href.strip()

        if not href or href.startswith("#"):
            continue

        link = urljoin(url,href)

        if not link.startswith(("https://","http://")):
            continue

        clean_url,_ = urldefrag(link)
        clean_url = normalize_url(clean_url)
        link_set.add(clean_url)

    return link_set

        

