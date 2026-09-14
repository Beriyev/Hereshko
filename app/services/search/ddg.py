import asyncio
from ddgs import DDGS
from ddgs.exceptions import RatelimitException, DDGSException

def _search_sync(query: str, max_results: int) -> list[dict]:
    with DDGS() as ddgs:
        return ddgs.text(query, max_results=max_results, backend = "duckduckgo")

async def search_web(query: str, max_results: int = 8) -> list[dict]:
    search_results = []

    try:
        results = await asyncio.to_thread(_search_sync,query,max_results)
    except RatelimitException:
        return [{"error": "DuckDuckGo rate limit reached. Try again in a moment."}]
    except DDGSException as e:
        return [{"error": f"Search failed: {e}"}]

    for result in results:
        search_results.append(
            {
                "title" : result.get("title",""),
                "url" : result.get("href",""),
                "snippet" : result.get("body","")
            }
        )

    return search_results