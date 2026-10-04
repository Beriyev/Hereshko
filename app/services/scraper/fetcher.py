from playwright.async_api import async_playwright
from app.services.scraper.scraper_config import FETCH_TIMEOUT, RENDER_TIMEOUT, USER_AGENT
import httpx
from bs4 import BeautifulSoup

async def fetch_static(url: str) -> tuple[str,int]:
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(url=url)
            response.raise_for_status()
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {url}: {e}")
            return "",0
        except httpx.HTTPStatusError as e:
            print(f"Error response {e.response.status_code} while requesting {url}: {e}")
            return "",e.response.status_code
        return response.text,response.status_code

async def fetch_dynamic(url: str) -> str:
    async with async_playwright() as client:
        browser = await client.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            response = await page.goto(url=url, timeout=RENDER_TIMEOUT)
            await page.wait_for_load_state("networkidle")
            if response is None or response.status>=400:
                return ""
            content = await page.content()
            return content
        except Exception as e:
            print(f"An error occurred while requesting {url}: {e}") 
            return ""
        finally:
            await browser.close()

async def fetch(url: str) -> str:
    html,status = await fetch_static(url=url)
    if (status not in (0, 200)) or (html == "" and status == 0):
        return ""
    soup = BeautifulSoup(html,"html.parser")
    tags_to_remove = ["script","style","noscript","head","template"]

    for removal_tag in tags_to_remove:
        for tag in soup.find_all(removal_tag):
            tag.decompose()

    text = "".join(soup.stripped_strings)

    if text == "":
        html = await fetch_dynamic(url=url)

    return html
