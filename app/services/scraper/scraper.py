from app.services.scraper.links import normalize_url
from app.services.scraper.fetcher import fetch
from app.services.scraper.extractor import extract_content

async def scrape(url: str) -> dict:
    url = normalize_url(url)

    try:
        html: str = await fetch(url=url)
    except Exception as e:
        print(f"An error occurred while fetching {url}: {e}")
        return {}

    if html == "":
        return {}

    try:
        content: dict = extract_content(url=url, html=html)
    except Exception as e:
        print(f"An error occurred while extracting content from {url}: {e}")
        return {}

    if not content["content"]:
        return {}

    return content
