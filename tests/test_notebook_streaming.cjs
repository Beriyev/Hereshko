const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("frontend/notebooks.js", "utf8");
const animation = source.slice(0, source.indexOf("const libraryApi"));

for (const reducedMotion of [false, true]) {
  const groups = [["beriyev's noteweaver"], ["Hail the", " sources."],
    ["Bring your sources together. Pick up a thread, or start a new one."]];
  const elements = groups.map((texts) => texts.map((textContent) => ({
    textContent, replacement: null,
    replaceWith(fragment) { this.replacement = fragment.children; },
  })));
  const timers = [];
  const context = vm.createContext({
    setTimeout: (callback, delay) => timers.push({ callback, delay }),
    window: { matchMedia: () => ({ matches: reducedMotion }) },
    document: {
      querySelectorAll: () => elements,
      createTreeWalker(nodes, filter) {
        assert.equal(filter, 4);
        let index = -1;
        return { currentNode: null, nextNode() {
          this.currentNode = nodes[++index];
          return this.currentNode || null;
        } };
      },
      createDocumentFragment: () => ({ children: [], appendChild(node) { this.children.push(node); } }),
      createElement: () => {
        const classes = new Set();
        return { style: {}, classList: { add: (name) => classes.add(name), contains: (name) => classes.has(name) } };
      },
    },
  });
  vm.runInContext(animation, context);
  context.streamNotebookIntro();
  const nodes = elements.flat();
  const letters = nodes.flatMap((node) => node.replacement);
  assert.equal(letters.map((letter) => letter.textContent).join(""), groups.flat().join(""));
  assert.ok(letters.every((letter) => letter.className === "intro-letter"));
  assert.ok(letters.every((letter) => !letter.classList.contains("is-visible")));
  assert.deepEqual(timers.map((timer) => timer.delay), letters.map((_, index) => 650 + index * 28));
  timers[0].callback();
  assert.equal(letters[0].classList.contains("is-visible"), true);
  assert.equal(letters[1].classList.contains("is-visible"), false);
  timers.forEach((timer) => timer.callback());
  assert.ok(letters.every((letter) => letter.classList.contains("is-visible")));
  assert.equal(elements[1][0].replacement.map((letter) => letter.textContent).join(""), "Hail the",
    "Highlighted text must remain inside its original span");
}
assert.match(fs.readFileSync("frontend/notebooks.css", "utf8"), /prefers-reduced-motion: reduce/);
console.log("Notebook text reveals sequentially, preserves highlighting, and does not rely on CSS motion being enabled");
