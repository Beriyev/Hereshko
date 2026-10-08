const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("frontend/notebooks.js", "utf8");
const page = fs.readFileSync("frontend/notebooks.html", "utf8");

class Element {
  constructor() {
    this.children = [];
    this.handlers = {};
    this.attributes = {};
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.style = { setProperty() {} };
    const classes = new Set();
    this.classList = { add: (name) => classes.add(name), remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name) };
  }
  addEventListener(name, callback) { this.handlers[name] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.append(child); }
  replaceChildren(...children) { this.children = children; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  focus() {}
  select() {}
}

const tick = () => new Promise((resolve) => setImmediate(resolve));
const record = (id, title, count = 0, updated = "2026-10-08T00:00:00Z") => ({
  notebook_id: id, title, source_count: count, updated_at: updated, created_at: updated,
});

async function setup(items = [], reducedMotion = false, initialError = false) {
  const nodes = Object.fromEntries([...page.matchAll(/id="([^"]+)"/g)]
    .map((match) => [match[1], new Element()]));
  nodes.notebookSort.value = "recent";
  const body = new Element();
  const calls = [], navigation = [], timers = [], windowHandlers = {};
  let respond = () => ({ ok: !initialError, status: initialError ? 503 : 200,
    json: async () => initialError ? { detail: "Offline" } : { notebooks: items } });
  const context = vm.createContext({
    document: { body, querySelectorAll: () => [], getElementById: (id) => {
      assert.ok(nodes[id], `Missing HTML element: ${id}`);
      return nodes[id];
    }, createElement: () => new Element() },
    window: { location: { assign: (url) => navigation.push(url) },
      matchMedia: () => ({ matches: reducedMotion }),
      addEventListener: (name, handler) => { windowHandlers[name] = handler; } },
    URLSearchParams, setTimeout: (callback, delay) => timers.push({ callback, delay }),
    fetch: async (url, options) => { calls.push({ url, options }); return respond(); },
  });
  vm.runInContext(source, context);
  await tick();
  return { nodes, body, calls, navigation, timers, context, windowHandlers,
    respond: (callback) => { respond = callback; } };
}

(async () => {
  const older = record("old", "Zebra", 2, "2020-01-01T00:00:00Z");
  const newer = record("new", "Alpha", 1);
  const fixture = await setup([older, newer]);
  const { nodes, context } = fixture;
  const titles = () => nodes.notebookGrid.children.map((card) => card.children[0].children[1].textContent);
  assert.deepEqual(titles(), ["Alpha", "Zebra"]);
  assert.equal(nodes.notebookGrid.children[0].children[0].children[2].textContent, "1 source");
  assert.equal(nodes.notebookGrid.children[1].children[0].children[2].textContent, "2 sources");
  assert.equal(nodes.notebookGrid.attributes["aria-busy"], "false");
  assert.equal(nodes.libraryStatus.hidden, true);
  assert.equal(nodes.refreshNotebooks.disabled, false);
  nodes.notebookSearch.value = " zeb ";
  nodes.notebookSearch.handlers.input();
  assert.deepEqual(titles(), ["Zebra"]);
  nodes.notebookSearch.value = "missing";
  nodes.notebookSearch.handlers.input();
  assert.equal(nodes.libraryEmpty.hidden, false);
  assert.equal(nodes.emptyCreate.hidden, true);
  nodes.notebookSearch.value = "";
  nodes.notebookSort.value = "name";
  nodes.notebookSort.handlers.change();
  assert.deepEqual(titles(), ["Alpha", "Zebra"]);

  // Renaming uses PATCH, preserves the ID, and updates the visible card.
  nodes.notebookGrid.children[0].children[1].handlers.click();
  assert.equal(nodes.newNotebookTitle.value, "Alpha");
  assert.equal(nodes.notebookDialog.open, true);
  nodes.newNotebookTitle.value = "  Renamed  ";
  fixture.respond(() => ({ ok: true, json: async () => record("new", "Renamed", 1) }));
  await nodes.notebookForm.handlers.submit({ preventDefault() {} });
  assert.equal(fixture.calls.at(-1).options.method, "PATCH");
  assert.equal(fixture.calls.at(-1).url, "http://localhost:8000/notebooks/new");
  assert.equal(fixture.calls.at(-1).options.body, JSON.stringify({ title: "Renamed" }));
  assert.deepEqual(titles(), ["Renamed", "Zebra"]);
  assert.equal(nodes.notebookDialog.open, false);

  // Invalid input sends no request; failed saves keep the dialog usable.
  nodes.newNotebook.handlers.click();
  nodes.newNotebookTitle.value = "   ";
  const previousCalls = fixture.calls.length;
  await nodes.notebookForm.handlers.submit({ preventDefault() {} });
  assert.equal(fixture.calls.length, previousCalls);
  assert.equal(nodes.dialogError.hidden, false);
  nodes.newNotebookTitle.value = "New notebook";
  fixture.respond(() => ({ ok: false, status: 400, json: async () => ({ detail: "Test error" }) }));
  await nodes.notebookForm.handlers.submit({ preventDefault() {} });
  assert.equal(nodes.dialogError.textContent, "Test error");
  assert.equal(nodes.notebookDialog.open, true);
  assert.equal(nodes.saveNotebook.disabled, false);
  assert.equal(nodes.cancelNotebook.disabled, false);
  assert.equal(nodes.newNotebookTitle.disabled, false);

  // While saving, block duplicate submits and Escape cancellation.
  let resolve;
  fixture.respond(() => new Promise((done) => { resolve = done; }));
  const saving = nodes.notebookForm.handlers.submit({ preventDefault() {} });
  assert.equal(nodes.saveNotebook.disabled, true);
  await nodes.notebookForm.handlers.submit({ preventDefault() {} });
  assert.equal(fixture.calls.length, previousCalls + 2);
  let prevented = false;
  nodes.notebookDialog.handlers.cancel({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  resolve({ ok: true, json: async () => record("a/b ?", "New notebook") });
  await saving;
  assert.equal(fixture.calls.at(-1).options.method, "POST");
  assert.equal(fixture.timers[0].delay, 180);
  fixture.timers[0].callback();
  assert.equal(fixture.navigation[0], "index.html?notebook_id=a%2Fb+%3F");

  const empty = await setup();
  assert.equal(empty.nodes.libraryEmpty.hidden, false);
  assert.equal(empty.nodes.emptyCreate.hidden, false);
  const failed = await setup([], false, true);
  assert.match(failed.nodes.libraryStatus.textContent, /Offline/);
  assert.equal(failed.nodes.refreshNotebooks.disabled, false);
  failed.respond(() => ({ ok: true, json: async () => ({ notebooks: [newer] }) }));
  await failed.nodes.refreshNotebooks.handlers.click();
  assert.equal(failed.nodes.libraryStatus.hidden, true);
  assert.equal(failed.nodes.notebookGrid.children.length, 1);

  const reduced = await setup([newer], true);
  const link = reduced.nodes.notebookGrid.children[0].children[0];
  link.handlers.click({ button: 0, ctrlKey: true, preventDefault() { throw Error("Modifier click intercepted"); } });
  assert.equal(reduced.timers.length, 0);
  link.handlers.click({ button: 0, preventDefault() {} });
  assert.equal(reduced.timers[0].delay, 0);
  reduced.context.openNotebook("another");
  assert.equal(reduced.timers.length, 1, "Duplicate navigation should be blocked");
  reduced.windowHandlers.pageshow({ persisted: true });
  await tick();
  assert.equal(reduced.body.classList.contains("library-leaving"), false);

  assert.match(fs.readFileSync("frontend/index.html", "utf8"), /class="brand" href="notebooks.html"/);
  assert.match(fs.readFileSync("frontend/app.js", "utf8"), /window.location.replace\("notebooks.html"\)/);
  console.log("Notebook frontend: loading, search, sorting, rename, create, errors, duplicate guards, navigation, and reduced motion pass");
})().catch((error) => { console.error(error); process.exitCode = 1; });
