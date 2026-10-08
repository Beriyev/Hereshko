const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("frontend/app.js", "utf8");
const handlers = source.slice(source.indexOf('document.getElementById("addYoutube").addEventListener'),
  source.indexOf('document.getElementById("refreshSummary").addEventListener'));

function setup() {
  const nodes = {};
  for (const id of ["addYoutube", "youtubeInput", "youtubeBox", "websiteInput", "websiteBox",
                    "scrapeWebsite", "crawlWebsite", "sourceList"]) {
    const classes = new Set();
    nodes[id] = {
      value: "https://example.com/test", disabled: false, attributes: {},
      classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name),
                   contains: (name) => classes.has(name) },
      addEventListener(name, callback) { this[name] = callback; },
      setAttribute(name, value) { this.attributes[name] = value; },
      focus() {}, prepend() {},
    };
  }
  let resolve, reject, calls = 0;
  const pending = new Promise((success, failure) => { resolve = success; reject = failure; });
  const context = vm.createContext({
    document: { getElementById: (id) => nodes[id], createElement: () => ({}) },
    FormData, notebookId: "test", showToast() {}, loadNotebook: async () => {},
    apiRequest: () => { calls++; return pending; },
  });
  vm.runInContext(handlers, context);
  return { nodes, context, resolve, reject, calls: () => calls };
}

(async () => {
  for (const kind of ["youtube", "scrape", "crawl"]) {
    for (const fail of [false, true]) {
      const fixture = setup();
      const { nodes, context } = fixture;
      const youtube = kind === "youtube";
      const button = nodes[youtube ? "addYoutube" : kind === "scrape" ? "scrapeWebsite" : "crawlWebsite"];
      const box = nodes[youtube ? "youtubeBox" : "websiteBox"];
      const input = nodes[youtube ? "youtubeInput" : "websiteInput"];
      const run = () => youtube ? button.click({ currentTarget: button })
        : context.ingestWebsite(kind === "scrape" ? "/ingest/scrape" : "/ingest/website", button);
      const task = run();
      assert.equal(box.classList.contains("loading"), true);
      assert.equal(button.classList.contains("loading"), true);
      assert.equal(box.attributes["aria-busy"], "true");
      assert.equal(button.disabled, true);
      assert.equal(input.disabled, true);
      await run();
      assert.equal(fixture.calls(), 1, "Duplicate ingestion must not start");
      if (fail) fixture.reject(new Error("Test failure"));
      else fixture.resolve({ document_ids: ["test"] });
      await task;
      assert.equal(box.classList.contains("loading"), false);
      assert.equal(button.classList.contains("loading"), false);
      assert.equal(box.attributes["aria-busy"], "false");
      assert.equal(button.disabled, false);
      assert.equal(input.disabled, false);
      if (!youtube) {
        assert.equal(nodes.scrapeWebsite.disabled, false);
        assert.equal(nodes.crawlWebsite.disabled, false);
      }
    }
  }
  console.log("YouTube, scrape, and crawl loading states pass for success, failure, and duplicate clicks");
})().catch((error) => { console.error(error); process.exitCode = 1; });
