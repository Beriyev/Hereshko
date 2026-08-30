from app.core.normalization import Document, SourceType
import uuid
from datetime import datetime, timezone
from app.core.exceptions import IngestionError
from app.services.scraper.crawler import crawl

async def extract_website(url: str, notebook_id: str) -> list[Document]:
    dict_set = await crawl(start_url=url)
    document_list: list[Document] = []

    for page in dict_set:
        if not page["content"]:
            continue

        document = Document(
            document_id=str(uuid.uuid4()),
            notebook_id=notebook_id,
            content=page["content"],
            source_type=SourceType.WEBSITE,
            source_identifier=page["url"],
            title=page["title"] if page["title"] else page["url"],
            ingested_at=datetime.now(timezone.utc),
            raw_metadata={
                "url": page["url"],
                "description": page["description"],
                "author": page["author"]
            }
        )
        document_list.append(document)

    if not document_list:
        raise IngestionError("No extractable content found on the site")

    return document_list