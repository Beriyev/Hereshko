from collections import deque
from app.services.scraper.links import normalize_url, extracted_links, is_same_domain
from app.services.scraper.fetcher import fetch
from app.services.scraper.scraper_config import MAX_CRAWL_PAGES
from app.services.scraper.extractor import extract_content

async def crawl(start_url: str) -> list[dict]:
    visited: set[str] = set()
    frontier: deque[str] = deque()
    results: list[dict] = []

    base_url = normalize_url(start_url)
    frontier.append(base_url)
    while frontier and len(results) < MAX_CRAWL_PAGES:
        url = frontier.popleft()
        url = normalize_url(url)

        if url in visited:
            continue

        visited.add(url)

        try:
            html: str = await fetch(url=url)
        except Exception as e:
            print(f"An error occurred while fetching {url}: {e}")
            continue

        if html == "":
            continue

        try:
            content: dict = extract_content(url=url, html=html)
        except Exception as e:
            print(f"An error occurred while extracting content from {url}: {e}")
            continue

        if not content["content"]:
            continue

        results.append(content)

        try:
            link_set = extracted_links(html=html, url=url)
        except Exception as e:
            print(f"An error occurred while extracting links from {url}: {e}")
            continue

        for link in link_set:
            if not is_same_domain(base=base_url, url=link):
                continue
            if link in visited:
                continue
            frontier.append(link)

    return results
