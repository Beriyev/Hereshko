from app.core.normalization import Document, SourceType
import uuid
from datetime import datetime, timezone
from app.core.exceptions import IngestionError
from app.services.scraper.crawler import crawl
from app.services.scraper.scraper import scrape

def _page_to_document(page: dict, notebook_id: str) -> Document | None:
    if not page.get("content"):
        return None

    return Document(
        document_id=str(uuid.uuid4()),
        notebook_id=notebook_id,
        content=page["content"],
        source_type=SourceType.WEBSITE,
        source_identifier=page["url"],
        title=page["title"] or page["url"],
        ingested_at=datetime.now(timezone.utc),
        raw_metadata={
            "url": page["url"],
            "description": page["description"],
            "author": page["author"],
        },
    )


async def extract_website(url: str, notebook_id: str) -> list[Document]:
    pages = await crawl(start_url=url)
    document_list: list[Document] = []

    for page in pages:
        document = _page_to_document(page, notebook_id)
        if document is not None:
            document_list.append(document)

    if not document_list:
        raise IngestionError("No extractable content found on the site")

    return document_list


async def extract_scraped_website(url: str, notebook_id: str) -> list[Document]:
    page = await scrape(url=url)
    document = _page_to_document(page, notebook_id) if page else None

    if document is None:
        raise IngestionError("No extractable content found on the page")

    return [document]
