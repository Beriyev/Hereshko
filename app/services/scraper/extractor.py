import trafilatura

def extract_content(url: str, html: str) -> dict:
    content = trafilatura.extract(html,url)
    metadata = trafilatura.extract_metadata(html,default_url=url)
    return {
        "content":content,
        "title":metadata.title if metadata else None,
        "description":metadata.description if metadata else None,
        "author":metadata.author if metadata else None,
        "url":metadata.url if metadata else url,
    }