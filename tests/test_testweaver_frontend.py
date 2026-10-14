"""Testweaver browser checks with fixture APIs; no Gemini requests or saved data."""

import asyncio
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect


FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
SOURCES = [
    {"document_id": "doc-1", "title": "Biology.pdf", "source_type": "pdf", "metadata": {}},
    {"document_id": "doc-2", "title": "Field notes.txt", "source_type": "txt", "metadata": {}},
]
MCQS = [
    {"question_id": "q-1", "question": "Which pigment absorbs light?", "difficulty": "easy",
     "options": ["Chlorophyll", "Starch", "Glucose", "Cellulose"], "correct_option": "Chlorophyll",
     "explanation": "Chlorophyll absorbs light for photosynthesis."},
    {"question_id": "q-2", "question": "Which process converts light energy into chemical energy?", "difficulty": "hard",
     "options": ["Photosynthesis", "Evaporation", "Diffusion", "Transpiration"], "correct_option": "Photosynthesis",
     "explanation": "Photosynthesis converts light into chemical energy."},
]
PAIRS = [
    [{"question_id": f"s-{index}", "question": f"Explain concept {index} and its relationships.",
      "difficulty": difficulty}, f"Expected answer for concept {index}."]
    for index, difficulty in enumerate(("easy", "medium", "hard"), 1)
]


async def main():
    screenshots = Path(tempfile.mkdtemp(prefix="testweaver-preview-"))
    calls = []
    state = {"fail_generation": False, "fail_grading": False, "malformed": False}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def respond(route):
            url = urlparse(route.request.url)
            if url.hostname == "testweaver.test":
                path = FRONTEND / url.path.lstrip("/")
                await route.fulfill(path=str(path)) if path.is_file() else await route.fulfill(status=404)
                return
            if url.hostname != "localhost":
                await route.abort()
                return
            if "/testweaver/" in url.path:
                calls.append({"path": url.path, "query": parse_qs(url.query),
                              "body": route.request.post_data_json, "method": route.request.method})
                await asyncio.sleep(.3)
                if (url.path.endswith("/generate") and state["fail_generation"]) or (url.path.endswith("/submit") and state["fail_grading"]):
                    await route.fulfill(status=503, json={"detail": "Fixture service unavailable"})
                    return
                if url.path == "/testweaver/objective/generate":
                    payload = MCQS if not state["malformed"] else []
                elif url.path == "/testweaver/subjective/generate":
                    payload = PAIRS
                elif url.path == "/testweaver/objective/submit":
                    body = route.request.post_data_json
                    payload = [{"correctness": "correct" if answer == question["correct_option"] else "incorrect",
                                "score": 10 if answer == question["correct_option"] else 0,
                                "mcq_explanation": question["explanation"], "points_to_improve": None}
                               for question, answer in zip(body["question_list"], body["provided_answers_list"])]
                else:
                    payload = [{"correctness": "partially_correct", "score": 7,
                                "points_to_improve": ["Explain the relationship.", "Include the definition."], "mcq_explanation": None},
                               {"correctness": "partially_correct", "score": 8, "points_to_improve": None, "mcq_explanation": None},
                               {"correctness": "correct", "score": 10, "points_to_improve": [], "mcq_explanation": None}]
            elif url.path.startswith("/ingest/"):
                await asyncio.sleep(.4)
                payload = {"document_ids": ["fixture-document"]}
            elif url.path.endswith("/sources"):
                payload = {"sources": SOURCES}
            elif url.path.endswith("/summary"):
                payload = {"title": "Biology", "summary": "Biology study notes.", "source_count": 2, "updated_at": "2026-10-14T00:00:00Z"}
            else:
                payload = {"notebook_id": "nb-test", "title": "Biology", "source_count": 2}
            await route.fulfill(json=payload)

        await page.route("**/*", respond)
        await page.goto("http://testweaver.test/index.html?notebook_id=nb-test")
        await expect(page.locator("#mindMapSource option")).to_have_count(2)
        await page.locator("#testweaverButton").click()
        await expect(page.locator("#testweaverModal")).to_be_visible()
        await expect(page.locator("#testweaverSource option")).to_have_count(2)
        await expect(page.locator(".tw-orbit")).to_have_count(0)
        await expect(page.locator("#testweaverEmpty h3")).to_have_text("Generate a Test.")
        await page.wait_for_function("getComputedStyle(document.getElementById('testweaverModal')).opacity === '1'")
        await page.screenshot(path=str(screenshots / "setup.png"))

        await page.locator("#testweaverCount").fill("2")
        await page.locator("#generateTestweaver").click()
        await expect(page.locator("#testweaverLoading")).to_be_visible()
        await expect(page.locator("#generateTestweaver")).to_be_disabled()
        await expect(page.locator("#testweaverSource")).to_be_disabled()
        await expect(page.locator("#testweaverLoading .chat-loading-dots i")).to_have_count(3)
        await expect(page.locator("#testweaverLoading .chat-loading-dots")).to_be_visible()
        for dot in await page.locator("#testweaverLoading .chat-loading-dots i").all():
            bounds = await dot.bounding_box()
            assert bounds and bounds["width"] == bounds["height"] == 5
            assert await dot.evaluate("element => getComputedStyle(element).animationName") == "tw-dot"
        assert await page.locator('#testweaverSetup input[type="radio"]:disabled').first.evaluate("element => getComputedStyle(element).opacity") == "0"
        await expect(page.locator("#testweaverLoading p")).to_have_text("Generating your test. This may take a while.")
        await page.screenshot(path=str(screenshots / "loading.png"))
        await expect(page.locator(".tw-question")).to_have_count(2)
        assert await page.locator(".tw-question").first.evaluate("element => getComputedStyle(element).animationName") == "tw-slide"
        assert await page.locator(".tw-question").nth(1).evaluate("element => getComputedStyle(element).animationDelay") == "0.09s"
        await expect(page.locator(".tw-feedback")).to_have_count(0)
        await expect(page.locator("#submitTestweaver")).to_be_disabled()
        assert calls[0]["query"] == {"document_id": ["doc-1"], "notebook_id": ["nb-test"], "number_of_questions": ["2"]}
        assert calls[0]["method"] == "POST"
        await page.locator('input[name="tw-answer-0"]').nth(0).check()
        await expect(page.locator("#testweaverProgressText")).to_have_text("1 of 2 answered")
        await page.locator('input[name="tw-answer-1"]').nth(2).check()
        await expect(page.locator("#submitTestweaver")).to_be_enabled()
        await page.screenshot(path=str(screenshots / "objective.png"))
        await page.locator("#submitTestweaver").click()
        await expect(page.locator("#testweaverAnswers")).to_have_attribute("aria-busy", "true")
        await expect(page.locator("#testweaverScoreValue")).to_have_text("5")
        await expect(page.locator(".tw-feedback")).to_have_count(2)
        await expect(page.locator(".tw-correct")).to_have_count(2)
        await expect(page.locator(".tw-wrong")).to_have_count(1)
        await expect(page.locator("#submitTestweaver")).to_be_disabled()
        assert calls[1]["body"]["provided_answers_list"] == ["Chlorophyll", "Diffusion"]
        assert calls[1]["body"]["question_list"] == MCQS
        await page.screenshot(path=str(screenshots / "objective-results.png"))

        await page.get_by_role("radio", name="Subjective", exact=True).check()
        await expect(page.locator("#testweaverCount")).to_have_attribute("max", "3")
        await page.locator("#testweaverCount").fill("3")
        await page.locator("#testweaverSource").select_option("doc-2")
        await page.locator("#generateTestweaver").click()
        await expect(page.locator(".tw-written-answer")).to_have_count(3)
        await expect(page.locator("#testweaverScore")).to_be_hidden()
        await expect(page.locator("#testweaverTestTitle")).to_contain_text("Field notes.txt")
        await expect(page.locator(".tw-difficulty.medium")).to_have_count(2)
        for index in range(3):
            await page.locator(f"#tw-answer-{index}").fill(" " if index == 2 else f"My reasoning {index}.")
        await expect(page.locator("#submitTestweaver")).to_be_disabled()
        await page.locator("#tw-answer-2").fill("My reasoning 2.")
        state["fail_grading"] = True
        await page.locator("#submitTestweaver").click()
        await expect(page.locator("#testweaverStatus")).to_contain_text("Your answers are still here")
        await expect(page.locator("#tw-answer-0")).to_have_value("My reasoning 0.")
        await expect(page.locator("#submitTestweaver")).to_be_enabled()
        state["fail_grading"] = False
        await page.locator("#submitTestweaver").click()
        await expect(page.locator("#testweaverScoreValue")).to_have_text("8.3")
        await expect(page.locator(".tw-feedback li")).to_have_count(2)
        assert calls[-1]["body"]["pairs_list"] == PAIRS
        assert calls[-1]["body"]["answer_list"] == [f"My reasoning {index}." for index in range(3)]
        await page.locator(".tw-feedback summary").first.click()
        await expect(page.locator(".tw-feedback details[open]")).to_contain_text("Expected answer for concept 1.")
        await page.screenshot(path=str(screenshots / "subjective-results.png"))

        await page.keyboard.press("Escape")
        await expect(page.locator("#testweaverModal")).to_be_hidden()
        await expect(page.locator("#testweaverButton")).to_be_focused()
        await page.locator("#testweaverButton").click()
        await expect(page.locator("#testweaverScoreValue")).to_have_text("8.3")
        state["fail_generation"] = True
        await page.locator("#generateTestweaver").click()
        await expect(page.locator("#testweaverStatus")).to_contain_text("Fixture service unavailable")
        await expect(page.locator("#tw-answer-0")).to_have_value("My reasoning 0.")
        state["fail_generation"] = False
        state["malformed"] = True
        await page.get_by_role("radio", name="Objective", exact=True).check()
        await page.locator("#generateTestweaver").click()
        await expect(page.locator("#testweaverStatus")).to_contain_text("unexpected question count")
        state["malformed"] = False

        await page.get_by_role("radio", name="Subjective", exact=True).check()
        await page.locator("#testweaverCount").fill("3")
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.locator("#generateTestweaver").click()
        await expect(page.locator("#testweaverStatus")).to_contain_text("Take your time")
        for index in range(3):
            await page.locator(f"#tw-answer-{index}").fill(f"My mobile reasoning {index}.")
        await page.locator("#submitTestweaver").click()
        await expect(page.locator("#testweaverScoreValue")).to_have_text("8.3")
        await expect(page.locator("#testweaverScore")).to_be_visible()
        await page.screenshot(path=str(screenshots / "mobile.png"))
        assert await page.locator("#testweaverModal").evaluate("element => element.scrollWidth <= element.clientWidth + 1"), "Mobile dialog must not overflow horizontally"
        assert await page.locator(".tw-main").evaluate("element => element.scrollWidth <= element.clientWidth + 1"), "Mobile questions must fit"
        await page.keyboard.press("Escape")
        await expect(page.locator("#testweaverModal")).to_be_hidden()
        await page.set_viewport_size({"width": 1440, "height": 1000})
        crawl_bounds = await page.locator("#crawlWebsite").bounding_box()
        scrape_bounds = await page.locator("#scrapeWebsite").bounding_box()
        assert crawl_bounds["y"] < scrape_bounds["y"], "Crawl belongs beside the URL; Scrape belongs below"
        for button_id, input_id in (("addYoutube", "youtubeInput"), ("crawlWebsite", "websiteInput"), ("scrapeWebsite", "websiteInput")):
            await page.locator(f"#{input_id}").fill("https://example.com/source")
            before = await page.locator(f"#{button_id}").bounding_box()
            await page.locator(f"#{button_id}").click()
            await expect(page.locator(f"#{button_id}.loading .loading-dots")).to_be_visible()
            dots = page.locator(f"#{button_id} .loading-dots i")
            await expect(dots).to_have_count(3)
            after = await page.locator(f"#{button_id}").bounding_box()
            assert abs(before["height"] - after["height"]) < 1, "Loading must not change the button height"
            for dot in await dots.all():
                bounds = await dot.bounding_box()
                assert bounds["width"] == bounds["height"] == 4, "Source dots must remain circular and retain their size"
                assert await dot.evaluate("element => getComputedStyle(element).animationName") == "sourceDotPulse"
            await page.screenshot(path=str(screenshots / f"{button_id}-loading.png"))
            await expect(page.locator(f"#{button_id}")).to_be_enabled()
            await expect(page.locator(f"#{button_id} .loading-dots")).to_be_hidden()
        await page.locator("#testweaverButton").click()
        await page.emulate_media(reduced_motion="reduce")
        await page.wait_for_function("document.getElementById('testweaverModal').getAnimations({subtree:true}).length === 0")
        assert await page.locator("#testweaverModal").evaluate("element => element.getAnimations({subtree:true}).length") == 0, "Reduced motion must stop animations"
        await page.evaluate("document.dispatchEvent(new CustomEvent('notebook-sources-updated', {detail: []}))")
        await expect(page.locator("#generateTestweaver")).to_be_disabled()
        await expect(page.locator("#testweaverSource")).to_be_disabled()
        assert not errors, errors
        await browser.close()
    print(f"Testweaver browser checks passed. Screenshots: {screenshots}")


if __name__ == "__main__":
    asyncio.run(main())
