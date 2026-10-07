const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

class Element {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.textContent = "";
    this.style = { setProperty() {} };
    this.classList = { add() {}, remove() {} };
  }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); }
  prepend(child) { this.children.unshift(child); }
  setAttribute() {}
}

const source = fs.readFileSync("frontend/app.js", "utf8");
const functions = source.slice(source.indexOf("function createL2Panel("), source.indexOf("async function submitPrompt("));
const context = vm.createContext({
  document: { createElement: (tag) => new Element(tag) },
  renderFormattedText: (element, text) => { element.textContent = text; },
  addCitationCards: (element, sources) => { element.sources = sources; },
  scrollToLatest() {},
  window: { matchMedia: () => ({ matches: false }) },
  streamText: async (element, text) => { element.textContent = text; },
  TextDecoder,
  apiBaseUrl: "http://test",
});
vm.runInContext(functions, context);

async function panelTest() {
const row = new Element("div");
const panel = context.createL2Panel(row);
await panel.update({ type: "planned", questions: ["Question one?", "Question two?"] });
await panel.update({ type: "answering", index: 0 });
await panel.update({ type: "answered", index: 0, answer: "Answer [1]", sources: [{ marker: 1 }] });
const research = row.children[0];
const first = research.children[1].children[0];
assert.equal(first.children[0].children[1].textContent, "Answered");
assert.equal(first.children[1].textContent, "Answer [1]");
assert.equal(first.sources[0].marker, 1);
await panel.update({ type: "done" });
assert.equal(research.open, false);
}

async function streamTest(events) {
  const bytes = new TextEncoder().encode(events.map((event) => JSON.stringify(event)).join("\n") + "\n");
  let offset = 0;
  context.fetch = async () => ({
    ok: true,
    body: { getReader: () => ({
      async read() {
        if (offset >= bytes.length) return { done: true };
        const value = bytes.slice(offset, offset + 7);
        offset += 7;
        return { value, done: false };
      },
      releaseLock() {},
    }) },
  });
  const received = [];
  const result = await context.requestL2({ mode: "l2" }, { update: (event) => received.push(event) });
  return { result, received };
}

(async () => {
  await panelTest();
  const { result, received } = await streamTest([
    { type: "planned", questions: ["Unicode café?"] },
    { type: "done", answer: "Final café answer [1]", sources: [{ marker: 1 }] },
  ]);
  assert.equal(result.answer, "Final café answer [1]");
  assert.equal(received.length, 2);
  await assert.rejects(streamTest([{ type: "error", message: "Test failure" }]), /Test failure/);
  await assert.rejects(streamTest([{ type: "planning" }]), /ended before the final answer/);
  console.log("L2 panel, citations, fragmented UTF-8 stream, and error handling passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
