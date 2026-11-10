"""Browser checks for inline citations and source previews with fixture data."""

import asyncio
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def respond(route):
            url = urlparse(route.request.url)
            if url.hostname == "citations.test":
                path = FRONTEND / url.path.lstrip("/")
                await route.fulfill(path=str(path)) if path.is_file() else await route.fulfill(status=404)
            elif url.hostname == "localhost":
                if url.path.endswith("/chat/l1"):
                    await route.fulfill(json={"answer": "A fact [1] and another [2].", "sources": [
                        {"marker": 1, "source_name": "Paper", "source_type": "pdf", "page_number": 3, "content": "Paper excerpt"},
                        {"marker": 2, "source_name": "Video", "source_type": "youtube", "timestamp_seconds": 0, "source_url": "https://example.com/watch", "content": "Video excerpt"},
                    ]})
                elif url.path.endswith("/sources"):
                    await route.fulfill(json={"sources": []})
                elif url.path.endswith("/summary"):
                    await route.fulfill(json={"title": "Notes", "summary": "Notes", "source_count": 0, "updated_at": "2026-10-12T00:00:00Z"})
                else:
                    await route.fulfill(json={"notebook_id": "test", "title": "Notes", "source_count": 0})
            else:
                await route.abort()

        await page.route("**/*", respond)
        await page.goto("http://citations.test/index.html?notebook_id=test")
        await page.locator("#chatInput").fill("Question")
        await page.locator("#chatForm").evaluate("form => form.requestSubmit()")
        buttons = page.locator(".chat-row.assistant .citation-marker")
        await expect(buttons).to_have_count(2)
        await buttons.first.click()
        await expect(page.locator("#sourcePreviewTitle")).to_have_text("Paper")
        await expect(page.locator("#sourcePreviewText")).to_have_text("Paper excerpt")
        await expect(page.locator("#sourcePreviewMetadata")).to_have_text("PDF · Page 3")
        await page.locator("#closeSourcePreview").click()
        await buttons.nth(1).click()
        await expect(page.locator("#sourcePreviewMetadata")).to_contain_text("Timestamp 0:00")
        await expect(page.locator("#sourcePreviewMetadata a")).to_have_attribute("href", "https://example.com/watch")
        await expect(page.locator(".answer-sources")).to_have_count(0)

        # Verify Markdown text, tables and code: only known citations outside code are buttons.
        await page.evaluate("""() => {
          window.marked = {setOptions() {}, parse() { return '<p>Text [7] [99] <code>[7]</code></p><table><tr><td>[7]</td></tr></table>'; }};
          window.DOMPurify = {sanitize: html => html};
          const target = document.createElement('div'); target.id = 'citation-test'; document.body.appendChild(target);
          renderFormattedText(target, '', [{marker: 7, source_name: 'Notes', source_type: 'docx', paragraph_index: 2, content: 'Paragraph excerpt'}]);
        }""")
        await expect(page.locator("#citation-test .citation-marker")).to_have_count(2)
        await expect(page.locator("#citation-test code")).to_have_text("[7]")
        await expect(page.locator("#citation-test")).to_contain_text("[99]")
        await page.locator("#citation-test .citation-marker").first.click()
        await expect(page.locator("#sourcePreviewMetadata")).to_have_text("DOCX · Paragraph 2")

        await page.set_viewport_size({"width": 390, "height": 844})
        await expect(page.locator("#sourcePreview")).to_be_visible()
        await page.evaluate("""() => showBottomPanel('Slides', 'Slide excerpt', {source_type: 'pptx', slide_number: 4})""")
        await expect(page.locator("#sourcePreviewMetadata")).to_have_text("PPTX · Slide 4")
        await page.evaluate("""() => showBottomPanel('Text', 'Plain excerpt')""")
        await expect(page.locator("#sourcePreviewMetadata")).to_be_hidden()
        assert not errors, errors
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
    print("Inline citation and source preview browser checks passed")
