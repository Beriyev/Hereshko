"""Browser checks for GraphWeaver, using fixture API responses (no Gemini calls).

Run: .venv/Scripts/python.exe -m tests.test_graphweaver_frontend
"""

import asyncio
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect


FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
SOURCES = [
    {"document_id": "doc-1", "title": "The water cycle.pdf", "source_type": "pdf", "metadata": {"pages_count": 4}},
    {"document_id": "doc-2", "title": "Field notes.txt", "source_type": "txt", "metadata": {}},
]
NODES = [
    {"id": "root", "parent_id": None, "title": "The Water Cycle", "summary": "How water moves between Earth and the atmosphere."},
    {"id": "air", "parent_id": "root", "title": "Entering the atmosphere", "summary": "Water becomes vapor through evaporation and transpiration."},
    {"id": "return", "parent_id": "root", "title": "Returning to Earth", "summary": "Water condenses into clouds and falls as precipitation."},
    {"id": "land", "parent_id": "root", "title": "Collection and movement", "summary": "Water gathers on the surface and moves underground."},
    {"id": "evaporation", "parent_id": "air", "title": "Evaporation", "summary": "Sunlight turns liquid water into vapor."},
    {"id": "transpiration", "parent_id": "air", "title": "Transpiration", "summary": "Plants release water vapor."},
    {"id": "condensation", "parent_id": "return", "title": "Condensation", "summary": "Vapor cools into cloud droplets."},
    {"id": "rain", "parent_id": "return", "title": "Precipitation", "summary": "Water returns as rain or snow."},
    {"id": "collection", "parent_id": "land", "title": "Surface collection", "summary": "Water gathers in rivers, lakes, and oceans."},
    {"id": "soil", "parent_id": "land", "title": "Infiltration", "summary": "Water enters soil and becomes groundwater."},
    {"id": "runoff", "parent_id": "land", "title": "Runoff", "summary": "Water flows across land into rivers."},
    {"id": "stomata", "parent_id": "transpiration", "title": "Stomata", "summary": "Leaf pores release water vapor."},
    {"id": "transport", "parent_id": "transpiration", "title": "Plant transport", "summary": "Water travels through the plant."},
    {"id": "roots", "parent_id": "transport", "title": "Root uptake", "summary": "Roots absorb water from soil."},
    {"id": "long-label", "parent_id": "transport", "title": "Movement of water and dissolved minerals from the roots through the stem to the leaves", "summary": "A long label exercises automatic wrapping and box sizing."},
    {"id": "unbroken-label", "parent_id": "land", "title": "GroundwaterRechargeAndLongTermSubsurfaceWaterStorage", "summary": "An unbroken label exercises wrapping without clipping."},
]


async def main():
    requests = []
    state = {"fail": False, "empty": False}
    screenshots = Path(tempfile.mkdtemp(prefix="graphweaver-preview-"))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def respond(route):
            url = urlparse(route.request.url)
            if url.hostname == "graphweaver.test":
                path = FRONTEND / url.path.lstrip("/")
                if path.is_file():
                    await route.fulfill(path=str(path))
                else:
                    await route.fulfill(status=404, body="Not found")
                return
            if url.hostname != "localhost":
                await route.abort()
                return
            sources = [] if state["empty"] else SOURCES
            if url.path.endswith("/mindmap"):
                requests.append(route.request.post_data_json)
                await asyncio.sleep(0.6 if len(requests) == 1 else 0.3)
                if state["fail"]:
                    await route.fulfill(status=500, json={"detail": "Sample generation error"})
                    return
                payload = {"nodes": NODES}
            elif url.path.endswith("/sources"):
                payload = {"sources": sources}
            elif url.path.endswith("/summary"):
                payload = {"title": "The water cycle", "summary": "A notebook about water.", "source_count": len(sources), "updated_at": "2026-10-12T00:00:00Z"}
            else:
                payload = {"notebook_id": "nb-test", "title": "Water studies", "source_count": len(sources)}
            await route.fulfill(json=payload)

        await page.route("**/*", respond)
        await page.goto("http://graphweaver.test/index.html?notebook_id=nb-test")
        await expect(page.locator("#mindMapSource option")).to_have_count(2)
        await page.locator("#graphweaverButton").click()
        await expect(page.locator(".map-empty-state strong")).to_have_text("Follow the ideas")
        await page.locator("#generateMap").click()
        await expect(page.locator("#generateMap")).to_be_disabled()
        await expect(page.locator("#mindMapSource")).to_be_disabled()
        await expect(page.locator("#map")).to_have_attribute("aria-busy", "true")
        await expect(page.locator(".map-empty-state.loading .chat-loading-dots i")).to_have_count(3)
        await expect(page.locator(".map-empty-state.loading .chat-loading-dots")).to_be_visible()
        for dot in await page.locator(".map-empty-state.loading .chat-loading-dots i").all():
            await expect(dot).to_be_visible()
            dimensions = await dot.bounding_box()
            assert abs(dimensions["width"] - dimensions["height"]) < 0.1, "Loading dots must stay circular"
        await page.screenshot(path=str(screenshots / "loading.png"))
        await expect(page.locator(".map-empty-state.loading strong, .map-empty-state.loading p, .map-empty-state.loading .map-state-icon")).to_have_count(0)
        await expect(page.locator("#map .map-node")).to_have_count(len(NODES))
        await expect(page.locator("#generateMap")).to_be_enabled()
        assert requests == [{"document_id": "doc-1"}]
        root = await page.locator(".map-root-card").bounding_box()
        branch = await page.get_by_role("button", name="Entering the atmosphere", exact=True).bounding_box()
        assert branch["y"] > root["y"] + root["height"], "Map must run top to bottom"
        await expect(page.get_by_role("button", name="Evaporation", exact=True)).to_be_hidden()
        await page.get_by_role("button", name="Expand Entering the atmosphere", exact=True).click()
        await expect(page.get_by_role("button", name="Evaporation", exact=True)).to_be_visible()
        first = await page.get_by_role("button", name="Evaporation", exact=True).bounding_box()
        second = await page.get_by_role("button", name="Transpiration", exact=True).bounding_box()
        assert second["y"] > first["y"] + first["height"], "Subtopics must stack vertically"
        assert abs(first["x"] - second["x"]) < 1, "Subtopics must share a column"
        await page.get_by_role("button", name="Evaporation", exact=True).click()
        await expect(page.locator("#selectedConcept")).to_have_text("Evaporation")
        await expect(page.locator("#conceptDescription")).to_have_text("Sunlight turns liquid water into vapor.")
        assert "The water cycle.pdf" in await page.locator("#mindMapPrompt").input_value()
        await expect(page.locator("#conceptSources small")).to_have_text("The water cycle.pdf")
        await page.get_by_role("button", name="Expand Transpiration", exact=True).click()
        await page.get_by_role("button", name="Expand Plant transport", exact=True).click()
        await expect(page.get_by_role("button", name="Root uptake", exact=True)).to_be_visible()
        long_node = page.get_by_role("button", name="Movement of water and dissolved minerals from the roots through the stem to the leaves", exact=True)
        short_node = page.get_by_role("button", name="Root uptake", exact=True)
        assert (await long_node.bounding_box())["height"] > (await short_node.bounding_box())["height"], "Long labels must grow the box"
        labels = await page.locator(".map-node:visible").evaluate_all("items => items.map(item => { const box = item.getBoundingClientRect(); const label = item.querySelector('.map-node-label').getBoundingClientRect(); return {x: Math.abs(label.x + label.width / 2 - box.x - box.width / 2), y: Math.abs(label.y + label.height / 2 - box.y - box.height / 2), fits: item.scrollWidth <= item.clientWidth + 1 && item.scrollHeight <= item.clientHeight + 1}; })")
        assert all(item["x"] < 1 and item["y"] < 1 and item["fits"] for item in labels), "Labels must fit and be centered in their boxes"
        shades = []
        for title in ("The Water Cycle", "Entering the atmosphere", "Transpiration", "Plant transport", "Root uptake"):
            node = page.get_by_role("button", name=title, exact=True)
            colors = await node.evaluate("element => { const css = getComputedStyle(element); return {background: css.backgroundColor.match(/\\d+/g).slice(0, 3).map(Number), text: css.color.match(/\\d+/g).slice(0, 3).map(Number)}; }")
            shades.append(colors["background"][0])
            def luminance(rgb):
                channels = [value / 255 for value in rgb]
                linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
                return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
            background, text = luminance(colors["background"]), luminance(colors["text"])
            assert (max(background, text) + 0.05) / (min(background, text) + 0.05) >= 4.5, "Node text must remain readable"
        assert all(child > parent for parent, child in zip(shades, shades[1:])), "Deeper nodes must be lighter"
        await page.locator("#mapFit").click()
        await page.wait_for_function("document.getElementById('map').getBoundingClientRect().height <= document.getElementById('mapViewport').clientHeight")
        await page.screenshot(path=str(screenshots / "depth-shades.png"))
        toggles = await page.locator(".map-branch-toggle:visible").evaluate_all("items => items.map(item => { const button = item.getBoundingClientRect(); const card = item.parentElement.getBoundingClientRect(); return {x: Math.abs(button.x + button.width / 2 - card.x - card.width / 2), y: Math.abs(button.y + button.height / 2 - card.bottom)}; })")
        assert all(item["x"] < 1 and item["y"] < 1 for item in toggles), "Expansion buttons must sit at the bottom connector, centered on the note"
        connector_ends = await page.locator(".map-subtopics:not([hidden]) > li:last-child").evaluate_all("items => items.map(item => ({line: parseFloat(getComputedStyle(item, '::after').height), center: item.querySelector(':scope > .map-node-card').offsetHeight / 2, fullHeight: item.offsetHeight}))")
        assert any(item["fullHeight"] > 50 for item in connector_ends), "Fixture must include an expanded final node"
        assert all(abs(item["line"] - item["center"]) < 1 for item in connector_ends), "Connector must stop at the last note, not its descendants"
        await page.get_by_role("button", name="Collapse Transpiration", exact=True).click()
        for title in ("Returning to Earth", "Collection and movement"):
            await page.get_by_role("button", name=f"Expand {title}", exact=True).click()
        await page.locator("#mapFit").click()
        await page.wait_for_function("document.getElementById('map').getBoundingClientRect().width <= document.getElementById('mapViewport').clientWidth")
        tree_bounds = await page.locator("#map").bounding_box()
        viewport_bounds = await page.locator("#mapViewport").bounding_box()
        assert tree_bounds["width"] <= viewport_bounds["width"], "Fit must keep expanded tree in view"
        await expect(page.locator(".map-subtopic > .map-node-card").last).to_have_css("opacity", "1")
        await page.screenshot(path=str(screenshots / "desktop.png"))
        before = await page.locator("#mapScale").inner_text()
        await page.locator("#mapZoomIn").click()
        assert await page.locator("#mapScale").inner_text() != before
        for _ in range(6):
            await page.locator("#mapZoomIn").click()
        viewport = page.locator("#mapViewport")
        bounds = await viewport.bounding_box()
        x, y = bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] - 40
        await page.mouse.move(x, y)
        await page.mouse.down()
        await page.mouse.move(x - 100, y, steps=5)
        await page.mouse.up()
        assert await viewport.evaluate("element => element.scrollLeft") > 0, "Dragging must pan the map"
        await viewport.evaluate("element => { element.scrollLeft = 0; element.scrollTop = 0; }")
        await page.mouse.move(x, y)
        wheel_zoom = await page.locator("#mapScale").inner_text()
        await page.mouse.wheel(0, 160)
        await page.wait_for_function("document.getElementById('mapViewport').scrollLeft > 0 || document.getElementById('mapViewport').scrollTop > 0")
        assert await page.locator("#mapScale").inner_text() == wheel_zoom, "Plain wheel must scroll without zooming"
        previous_zoom = await page.evaluate("mapZoom")
        await page.keyboard.down("Control")
        await page.mouse.wheel(0, -120)
        await page.keyboard.up("Control")
        await page.wait_for_function("previous => mapZoom > previous", arg=previous_zoom)
        selected = await page.locator("#selectedConcept").inner_text()
        node = page.get_by_role("button", name="The Water Cycle", exact=True)
        await node.hover()
        node_bounds = await node.bounding_box()
        initial_scroll = await viewport.evaluate("element => element.scrollLeft")
        await page.mouse.move(node_bounds["x"] + node_bounds["width"] / 2, node_bounds["y"] + node_bounds["height"] / 2)
        await page.mouse.down()
        await page.mouse.move(node_bounds["x"] + node_bounds["width"] / 2 - 80, node_bounds["y"] + node_bounds["height"] / 2, steps=5)
        await page.mouse.up()
        assert await viewport.evaluate("element => element.scrollLeft") > initial_scroll, "Dragging a node must pan too"
        await expect(page.locator("#selectedConcept")).to_have_text(selected)
        await page.locator("#mapCollapse").click()
        await expect(page.get_by_role("button", name="Evaporation", exact=True)).to_be_hidden()
        await page.locator("#regenerateMap").click()
        await expect(page.locator("#generateMap")).to_be_enabled()
        assert len(requests) == 2
        await page.locator("#mindMapSource").select_option("doc-2")
        await expect(page.locator(".map-empty-state strong")).to_have_text("Follow the ideas")
        state["fail"] = True
        await page.locator("#generateMap").click()
        await expect(page.locator(".map-empty-state strong")).to_have_text("Couldn't generate this map")
        await expect(page.locator("#generateMap")).to_be_enabled()
        state["fail"] = False
        await page.locator("#generateMap").click()
        await expect(page.locator("#map .map-node")).to_have_count(len(NODES))
        assert requests[-1] == {"document_id": "doc-2"}
        await page.locator("#mindMapSource").select_option("doc-1")
        assert len(requests) == 4, "Cached maps must not make another request"
        await page.keyboard.press("Escape")
        await expect(page.locator("#mindMapModal")).to_have_attribute("aria-hidden", "true")
        await expect(page.locator("#graphweaverButton")).to_be_focused()
        await page.locator("#graphweaverButton").click()
        await expect(page.locator("#map .map-node")).to_have_count(len(NODES))
        await page.emulate_media(reduced_motion="no-preference")
        await page.locator("#mapCollapse").click()
        await expect(page.locator(".map-root-card")).to_have_css("animation-name", "mapCardReveal")
        await page.get_by_role("button", name="Expand Entering the atmosphere", exact=True).click()
        await page.get_by_role("button", name="Evaporation", exact=True).click()
        await expect(page.get_by_role("button", name="Evaporation", exact=True)).to_have_css("animation-name", "mapSelection")
        before_zoom = await page.evaluate("mapZoom")
        await page.locator("#mapZoomIn").click()
        await page.wait_for_function("previous => mapZoom > previous && mapZoomFrame === null", arg=before_zoom)
        await page.emulate_media(reduced_motion="reduce")
        await page.set_viewport_size({"width": 375, "height": 812})
        await page.locator("#mapFit").click()
        await page.wait_for_function("document.getElementById('map').getBoundingClientRect().width <= document.getElementById('mapViewport').clientWidth")
        await page.screenshot(path=str(screenshots / "mobile.png"))
        toolbar = await page.locator(".map-toolbar").bounding_box()
        assert toolbar["x"] >= 0 and toolbar["x"] + toolbar["width"] <= 375, "Mobile toolbar overflows"
        await expect(page.locator("#generateMap")).to_be_visible()
        await page.set_viewport_size({"width": 1440, "height": 1000})
        state["empty"] = True
        await page.reload()
        await page.locator("#graphweaverButton").click()
        await expect(page.locator(".map-empty-state strong")).to_have_text("Your map starts with a source")
        await expect(page.locator("#generateMap")).to_be_disabled()
        assert not errors, errors
        print("GraphWeaver browser checks passed: generation, top-down layout, branches, selection, animated zoom, wheel scroll/zoom, background/node drag, retries, cache, close, mobile, reduced motion, empty notebook")
        print("Screenshots: " + str(screenshots))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
