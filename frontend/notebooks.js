function streamNotebookIntro() {
  let delay = 650;
  document.querySelectorAll(".library-intro [data-stream]").forEach((element) => {
    const walker = document.createTreeWalker(element, 4); // Text nodes only.
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    textNodes.forEach((node) => {
      const fragment = document.createDocumentFragment();
      for (const character of node.textContent) {
        const letter = document.createElement("span");
        letter.className = "intro-letter";
        letter.textContent = character;
        setTimeout(() => letter.classList.add("is-visible"), delay);
        fragment.appendChild(letter);
        delay += 28;
      }
      node.replaceWith(fragment);
    });
  });
}

const libraryApi = window.HERESHKO_API_URL || "http://localhost:8000";
const library = {
  grid: document.getElementById("notebookGrid"),
  count: document.getElementById("notebookCount"),
  status: document.getElementById("libraryStatus"),
  empty: document.getElementById("libraryEmpty"),
  search: document.getElementById("notebookSearch"),
  sort: document.getElementById("notebookSort"),
  refresh: document.getElementById("refreshNotebooks"),
  dialog: document.getElementById("notebookDialog"),
  form: document.getElementById("notebookForm"),
  title: document.getElementById("newNotebookTitle"),
  save: document.getElementById("saveNotebook"),
  cancel: document.getElementById("cancelNotebook"),
  error: document.getElementById("dialogError"),
};
let notebooks = [];
let editingId = null;
let isLeaving = false;

async function libraryRequest(path, options = {}) {
  const response = await fetch(`${libraryApi}${path}`, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status})`);
  }
  return payload;
}

function workspaceLink(id) {
  return `index.html?${new URLSearchParams({ notebook_id: id })}`;
}

function openNotebook(id) {
  if (isLeaving) return;
  isLeaving = true;
  document.body.classList.add("library-leaving");
  const delay = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 180;
  setTimeout(() => window.location.assign(workspaceLink(id)), delay);
}

function openNotebookDialog(notebook = null) {
  editingId = notebook?.notebook_id || null;
  document.getElementById("dialogTitle").textContent = notebook ? "Rename notebook" : "New notebook";
  document.getElementById("dialogDescription").textContent = notebook
    ? "A new name, the same ideas and sources." : "Give this collection a name. You can change it later.";
  library.title.value = notebook?.title || "";
  library.save.textContent = notebook ? "Save name" : "Create notebook";
  library.error.hidden = true;
  library.dialog.showModal();
  library.title.focus();
  library.title.select();
}

function renderNotebooks() {
  const search = library.search.value.trim().toLocaleLowerCase();
  const visible = notebooks.filter((notebook) => notebook.title.toLocaleLowerCase().includes(search));
  visible.sort(library.sort.value === "name"
    ? (a, b) => a.title.localeCompare(b.title)
    : (a, b) => new Date(b.updated_at) - new Date(a.updated_at));
  library.grid.replaceChildren();
  library.count.textContent = notebooks.length;
  library.empty.hidden = visible.length > 0;
  document.getElementById("emptyTitle").textContent = search ? "No matching notebooks." : "Your first notebook starts here.";
  document.getElementById("emptyText").textContent = search
    ? "Try another name or clear your search." : "Create a notebook, add your sources, and make room for discovery.";
  document.getElementById("emptyCreate").hidden = Boolean(search);

  visible.forEach((notebook, index) => {
    const card = document.createElement("article");
    card.className = "notebook-card";
    card.style.setProperty("--card-order", Math.min(index, 8));
    const link = document.createElement("a");
    link.className = "notebook-link";
    link.href = workspaceLink(notebook.notebook_id);
    const emblem = document.createElement("span");
    emblem.className = "notebook-emblem";
    emblem.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h12a2 2 0 0 1 2 2v16H7a2 2 0 0 1-2-2V3ZM5 17h14M9 7h6M9 10h4" /></svg>';
    const title = document.createElement("h3");
    title.textContent = notebook.title;
    const sources = document.createElement("p");
    sources.textContent = `${notebook.source_count} source${notebook.source_count === 1 ? "" : "s"}`;
    const bottom = document.createElement("div");
    bottom.className = "notebook-bottom";
    const date = document.createElement("time");
    date.dateTime = notebook.updated_at;
    date.textContent = `Updated ${new Date(notebook.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
    const arrow = document.createElement("span");
    arrow.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" /></svg>';
    bottom.append(date, arrow);
    link.append(emblem, title, sources, bottom);
    link.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      openNotebook(notebook.notebook_id);
    });
    const rename = document.createElement("button");
    rename.className = "notebook-rename";
    rename.type = "button";
    rename.setAttribute("aria-label", `Rename ${notebook.title}`);
    rename.title = "Rename notebook";
    rename.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 5.5 4 4M5 19l3.6-.7L19 7.9a1.4 1.4 0 0 0 0-2l-.9-.9a1.4 1.4 0 0 0-2 0L5.7 15.4 5 19Z" /></svg>';
    rename.addEventListener("click", () => openNotebookDialog(notebook));
    card.append(link, rename);
    library.grid.appendChild(card);
  });
}

async function loadNotebooks() {
  if (library.refresh.disabled) return;
  library.refresh.disabled = true;
  library.grid.setAttribute("aria-busy", "true");
  library.status.hidden = false;
  library.status.textContent = "Loading your notebooks…";
  library.empty.hidden = true;
  try {
    const payload = await libraryRequest("/notebooks");
    notebooks = payload.notebooks;
    renderNotebooks();
    library.status.hidden = true;
  } catch (error) {
    library.status.textContent = `Could not load notebooks: ${error.message}. Use Refresh to try again.`;
  } finally {
    library.grid.setAttribute("aria-busy", "false");
    library.refresh.disabled = false;
  }
}

library.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (library.save.disabled) return;
  const title = library.title.value.trim();
  if (!title || title.length > 120) {
    library.error.textContent = "Enter a notebook name between 1 and 120 characters.";
    library.error.hidden = false;
    return;
  }
  library.save.disabled = true;
  library.cancel.disabled = true;
  library.title.disabled = true;
  library.save.textContent = editingId ? "Saving…" : "Creating…";
  library.error.hidden = true;
  try {
    const notebook = await libraryRequest(editingId ? `/notebooks/${encodeURIComponent(editingId)}` : "/notebooks", {
      method: editingId ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    library.dialog.close();
    if (editingId) {
      notebooks = notebooks.map((item) => item.notebook_id === notebook.notebook_id ? notebook : item);
      renderNotebooks();
    } else {
      openNotebook(notebook.notebook_id);
    }
  } catch (error) {
    library.error.textContent = error.message;
    library.error.hidden = false;
  } finally {
    library.save.disabled = false;
    library.cancel.disabled = false;
    library.title.disabled = false;
    library.save.textContent = editingId ? "Save name" : "Create notebook";
  }
});
document.getElementById("newNotebook").addEventListener("click", () => openNotebookDialog());
document.getElementById("emptyCreate").addEventListener("click", () => openNotebookDialog());
library.cancel.addEventListener("click", () => library.dialog.close());
library.dialog.addEventListener("cancel", (event) => { if (library.save.disabled) event.preventDefault(); });
library.refresh.addEventListener("click", loadNotebooks);
library.search.addEventListener("input", renderNotebooks);
library.sort.addEventListener("change", renderNotebooks);
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    isLeaving = false;
    document.body.classList.remove("library-leaving");
    loadNotebooks();
  }
});
streamNotebookIntro();
loadNotebooks();
