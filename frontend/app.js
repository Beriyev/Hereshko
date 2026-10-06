const notebookId = "nb-1";
const apiBaseUrl = window.HERESHKO_API_URL || "http://localhost:8000";
const sessionId = window.crypto?.randomUUID?.() || `session-${Date.now()}`;

const mindMapData = {
  label: "Your notebook",
  description: "Mind map generation will use indexed notebook content when that feature is connected.",
  sources: 0,
  children: [],
};

const elements = {
  form: document.getElementById("chatForm"),
  input: document.getElementById("chatInput"),
  modeButton: document.getElementById("modeButton"),
  modeLabel: document.getElementById("modeLabel"),
  notebookTitle: document.getElementById("notebookTitle"),
  renameNotebook: document.getElementById("renameNotebook"),
  sourceCount: document.getElementById("sourceCount"),
  sourceList: document.getElementById("sourceList"),
  sourceEmpty: document.getElementById("sourceEmpty"),
  sourcePreview: document.getElementById("sourcePreview"),
  sourcePreviewTitle: document.getElementById("sourcePreviewTitle"),
  sourcePreviewText: document.getElementById("sourcePreviewText"),
  indexHealth: document.getElementById("indexHealth"),
  indexHealthBar: document.getElementById("indexHealthBar"),
  summaryText: document.getElementById("summaryText"),
  generatedTitle: document.getElementById("generatedTitle"),
  summarySourceCount: document.getElementById("summarySourceCount"),
  summaryUpdated: document.getElementById("summaryUpdated"),
  conversation: document.getElementById("conversation"),
  empty: document.getElementById("emptyConversation"),
  scroll: document.getElementById("centerScroll"),
  modal: document.getElementById("mindMapModal"),
  map: document.getElementById("map"),
  prompt: document.getElementById("mindMapPrompt"),
  selectedConcept: document.getElementById("selectedConcept"),
  conceptDescription: document.getElementById("conceptDescription"),
  conceptSources: document.getElementById("conceptSources"),
  toast: document.getElementById("toast"),
};

let isStreaming = false;
let toastTimer;
let savedNotebookTitle = "Untitled notebook";
let webSearchMode = false;

function showToast(message) {
  clearTimeout(toastTimer);
  elements.toast.querySelector("p").textContent = message;
  elements.toast.classList.add("show");
  toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 2300);
}

function showBottomPanel(title, text) {
  elements.sourcePreviewTitle.textContent = title;
  elements.sourcePreviewText.textContent = text;
  elements.sourcePreview.hidden = false;
  elements.sourcePreview.classList.remove("preview-enter");
  requestAnimationFrame(() => elements.sourcePreview.classList.add("preview-enter"));
}

async function saveNotebookTitle() {
  const title = elements.notebookTitle.value.trim();
  if (!title) {
    elements.notebookTitle.value = savedNotebookTitle;
    showToast("Notebook name cannot be empty.");
    return;
  }
  if (title === savedNotebookTitle) return;

  const previousTitle = savedNotebookTitle;
  elements.renameNotebook.disabled = true;
  try {
    const notebook = await apiRequest(`/notebooks/${notebookId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    savedNotebookTitle = notebook.title;
    elements.notebookTitle.value = notebook.title;
    showToast("Notebook name saved.");
  } catch (error) {
    elements.notebookTitle.value = previousTitle;
    showToast(error.message);
  } finally {
    elements.renameNotebook.disabled = false;
  }
}

function autoResizeTextarea() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 130)}px`;
}

function createMessage(role, text = "") {
  const row = document.createElement("div");
  row.className = `chat-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  if (role === "assistant" && !text) {
    bubble.classList.add("typing-bubble");
    bubble.innerHTML = '<span class="chat-loading-dots" aria-label="Hereshko is thinking"><i></i><i></i><i></i></span>';
  } else {
    bubble.textContent = text;
  }
  row.appendChild(bubble);
  elements.conversation.appendChild(row);
  return { row, bubble };
}

function scrollToLatest() {
  requestAnimationFrame(() => {
    elements.scroll.scrollTo({ top: elements.scroll.scrollHeight, behavior: "smooth" });
  });
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function streamText(target, text) {
  target.replaceChildren();
  target.classList.add("stream-cursor", "streaming-reveal");

  const blocks = text.split(/\n{2,}/).filter((block) => block.trim());
  const revealBlocks = blocks.length ? blocks : [text];

  revealBlocks.forEach((block, index) => {
    const element = document.createElement("span");
    element.className = "stream-block";
    element.textContent = block;
    target.appendChild(element);

    if (index < revealBlocks.length - 1) {
      target.appendChild(document.createTextNode("\n\n"));
    }
  });

  const duration = Math.min(3800, Math.max(1400, text.length * 6.5));
  target.style.setProperty("--stream-duration", `${duration}ms`);
  void target.offsetWidth;
  scrollToLatest();
  await wait(duration + 80);

  target.classList.remove("stream-cursor", "streaming-reveal");
  target.style.removeProperty("--stream-duration");
}

function renderFormattedText(target, text) {
  target.replaceChildren();
  let usedMarkdownRenderer = false;

  if (window.marked && window.DOMPurify) {
    usedMarkdownRenderer = true;
    marked.setOptions({ breaks: true, gfm: true });
    // Hereshko supports bold with **double asterisks** only. Remove stray
    // single markers before Markdown parsing so they cannot leak into output.
    const normalizedMarkdown = text.replace(/(?<!\*)\*(?!\*)/g, "");
    target.innerHTML = DOMPurify.sanitize(marked.parse(normalizedMarkdown), {
      USE_PROFILES: { html: true },
    });
  } else {
    renderBasicFormatting(target, text);
  }

  if (usedMarkdownRenderer) {
    decorateCitationMarkers(target);
  }

  if (window.renderMathInElement) {
    renderMathInElement(target, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
      ],
      throwOnError: false,
    });
  }
}

function renderBasicFormatting(target, text) {
  const normalizedText = text.replace(/(?<!\*)\*(?!\*)/g, "");
  const tokens = normalizedText.split(/(\*\*[\s\S]*?\*\*|\[\d+\])/g);

  tokens.forEach((token) => {
    if (!token) return;

    if (token.startsWith("**") && token.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      target.appendChild(strong);
      return;
    }

    if (/^\[\d+\]$/.test(token)) {
      const strong = document.createElement("strong");
      const underline = document.createElement("u");
      underline.textContent = token;
      strong.appendChild(underline);
      target.appendChild(strong);
      return;
    }

    target.appendChild(document.createTextNode(token));
  });
}

function decorateCitationMarkers(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  let current;

  while ((current = walker.nextNode())) textNodes.push(current);

  textNodes.forEach((node) => {
    if (!/\[\d+\]/.test(node.nodeValue)) return;

    const fragment = document.createDocumentFragment();
    node.nodeValue.split(/(\[\d+\])/g).forEach((part) => {
      if (/^\[\d+\]$/.test(part)) {
        const marker = document.createElement("strong");
        const underline = document.createElement("u");
        underline.textContent = part;
        marker.appendChild(underline);
        fragment.appendChild(marker);
      } else if (part) {
        fragment.appendChild(document.createTextNode(part));
      }
    });

    node.parentNode.replaceChild(fragment, node);
  });
}

function addCitationCards(row, citations = []) {
  const sources = document.createElement("div");
  sources.className = "answer-sources";
  citations.forEach((citation, index) => {
    const number = citation.marker || index + 1;
    const source = document.createElement("button");
    source.textContent = number;
    source.title = citation.source_name || `Open source ${number}`;
    source.addEventListener("click", () => {
      showBottomPanel(
        citation.source_name || `Source ${number}`,
        citation.content || "No chunk text was returned for this citation."
      );
    });
    sources.appendChild(source);
  });
  if (citations.length) row.appendChild(sources);
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Keep the HTTP error when the server did not return JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

function sourceClass(sourceType) {
  if (sourceType === "pdf") return "pdf";
  if (sourceType === "website") return "web";
  if (sourceType === "youtube") return "video";
  return "note";
}

function sourceMeta(source) {
  const metadata = source.metadata || {};
  if (metadata.pages_count) return `${metadata.pages_count} pages · Indexed`;
  if (metadata.slides_count) return `${metadata.slides_count} slides · Indexed`;
  if (source.source_type === "website") return "Website · Indexed";
  if (source.source_type === "youtube") return "YouTube · Indexed";
  return `${source.source_type.toUpperCase()} · Indexed`;
}

function renderSources(sources) {
  elements.sourceList.innerHTML = "";

  if (!sources.length) {
    elements.sourceList.appendChild(elements.sourceEmpty);
    elements.sourceCount.textContent = "0";
    return;
  }

  sources.forEach((source, index) => {
    const card = document.createElement("article");
    card.className = `source-card${index === 0 ? " active" : ""}`;

    const icon = document.createElement("span");
    icon.className = `file-icon ${sourceClass(source.source_type)}`;
    icon.textContent = source.source_type.slice(0, 3).toUpperCase();

    const details = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = source.title;
    const meta = document.createElement("small");
    meta.textContent = sourceMeta(source);
    details.append(title, meta);

    const menu = document.createElement("button");
    menu.className = "source-menu";
    menu.type = "button";
    menu.setAttribute("aria-label", `Options for ${source.title}`);
    menu.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!window.confirm(`Remove ${source.title} from this notebook?`)) return;

      menu.disabled = true;
      try {
        await apiRequest(`/notebooks/${notebookId}/sources/${source.document_id}`, {
          method: "DELETE",
        });
        elements.sourcePreview.hidden = true;
        await loadNotebook();
        showToast("Source removed");
      } catch (error) {
        menu.disabled = false;
        showToast(`Source removal failed: ${error.message}`);
      }
    });
    menu.textContent = "•••";

    card.append(icon, details, menu);
    card.addEventListener("click", () => {
      document.querySelectorAll(".source-card").forEach((item) => item.classList.remove("active"));
      card.classList.add("active");
      showBottomPanel(source.title, source.metadata?.preview_text || "No text preview is available for this source.");
    });
    elements.sourceList.appendChild(card);
  });

  elements.sourceCount.textContent = sources.length;
  elements.indexHealth.textContent = "Ready";
  elements.indexHealthBar.style.width = "100%";
}

document.getElementById("closeSourcePreview").addEventListener("click", () => {
  elements.sourcePreview.hidden = true;
  document.querySelectorAll(".source-card").forEach((item) => item.classList.remove("active"));
});

document.getElementById("deleteAllSources").addEventListener("click", async (event) => {
  if (!Number(elements.sourceCount.textContent)) {
    showToast("There are no sources to delete");
    return;
  }
  if (!window.confirm("Remove every source from this notebook?")) return;

  const button = event.currentTarget;
  button.disabled = true;
  try {
    await apiRequest(`/notebooks/${notebookId}/sources`, { method: "DELETE" });
    elements.sourcePreview.hidden = true;
    await loadNotebook();
    showToast("All sources removed");
  } catch (error) {
    showToast(`Source removal failed: ${error.message}`);
  } finally {
    button.disabled = false;
  }
});

async function loadNotebook() {
  const [notebook, sourcePayload] = await Promise.all([
    apiRequest(`/notebooks/${notebookId}`),
    apiRequest(`/notebooks/${notebookId}/sources`),
  ]);

  savedNotebookTitle = notebook.title;
  elements.notebookTitle.value = notebook.title;
  elements.sourceCount.textContent = notebook.source_count;
  elements.summarySourceCount.textContent = notebook.source_count;
  if (notebook.source_count === 0) {
    elements.generatedTitle.textContent = "Notebook overview";
    elements.indexHealth.textContent = "Waiting";
    elements.indexHealthBar.style.width = "0%";
  }
  renderSources(sourcePayload.sources || []);

  if (notebook.source_count > 0) {
    refreshNotebookOverview(false).catch((error) => {
      console.warn(`Could not generate notebook overview: ${error.message}`);
    });
  }
}

async function refreshNotebookOverview(showSuccess = true) {
  elements.summaryText.classList.add("refreshing");

  try {
    const payload = await apiRequest(`/notebooks/${notebookId}/summary`, {
      method: "POST",
    });
    elements.generatedTitle.textContent = "";
    elements.summaryText.textContent = "";
    await Promise.all([
      streamText(elements.generatedTitle, payload.title),
      streamText(elements.summaryText, payload.summary),
    ]);
    renderFormattedText(elements.summaryText, payload.summary);
    elements.summarySourceCount.textContent = payload.source_count;
    elements.summaryUpdated.textContent = `Updated ${new Date(payload.updated_at).toLocaleString()}`;
    if (showSuccess) showToast("Notebook summary refreshed");
  } finally {
    elements.summaryText.classList.remove("refreshing");
  }
}

elements.notebookTitle.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    elements.notebookTitle.blur();
  }
});
elements.notebookTitle.addEventListener("blur", saveNotebookTitle);
elements.renameNotebook.addEventListener("click", () => {
  elements.notebookTitle.focus();
  elements.notebookTitle.select();
});

async function submitPrompt(prompt) {
  const cleanPrompt = prompt.trim();
  if (!cleanPrompt || isStreaming) return;

  isStreaming = true;
  elements.empty?.remove();
  createMessage("user", cleanPrompt);
  elements.input.value = "";
  autoResizeTextarea();
  scrollToLatest();
  const { row, bubble } = createMessage("assistant");
  try {
    const payload = await apiRequest("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        notebook_id: notebookId,
        query: cleanPrompt,
        session_id: sessionId,
        web_search: webSearchMode,
      }),
    });
    const answer = payload.answer || "The notebook returned an empty answer.";
    bubble.classList.remove("typing-bubble");
    bubble.textContent = "";
    await streamText(bubble, answer);
    renderFormattedText(bubble, answer);
    addCitationCards(row, payload.sources);
  } catch (error) {
    bubble.classList.remove("typing-bubble");
    bubble.textContent = `I couldn’t reach the Hereshko backend: ${error.message}`;
    showToast("Chat request failed");
  } finally {
    scrollToLatest();
    isStreaming = false;
  }
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitPrompt(elements.input.value);
});

elements.modeButton.addEventListener("click", () => {
  webSearchMode = !webSearchMode;
  elements.modeButton.classList.toggle("active", webSearchMode);
  elements.modeButton.setAttribute("aria-pressed", String(webSearchMode));
  elements.modeLabel.textContent = webSearchMode ? "Web Search" : "Grounded";
  showToast(webSearchMode ? "Web Search mode enabled" : "Grounded mode enabled");
});

elements.input.addEventListener("input", autoResizeTextarea);
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => {
    elements.input.value = button.dataset.question;
    autoResizeTextarea();
    elements.input.focus();
  });
});

document.querySelectorAll("[data-toast]").forEach((button) => {
  button.addEventListener("click", () => showToast(button.dataset.toast));
});

const fileInput = document.getElementById("fileInput");
const uploadZone = document.getElementById("uploadZone");

async function uploadFiles(files) {
  const pending = [];
  [...files].forEach((file) => {
    const card = document.createElement("article");
    card.className = "source-card";
    const extension = file.name.split(".").pop()?.toUpperCase() || "FILE";
    card.innerHTML = `
      <span class="file-icon note">${extension.slice(0, 3)}</span>
      <div><strong></strong><small>Queued · Preparing index</small></div>
      <button class="source-menu" aria-label="Source options">•••</button>
    `;
    card.querySelector("strong").textContent = file.name;
    document.getElementById("sourceList").prepend(card);
    pending.push({ file, card });
  });

  const sourceCards = document.querySelectorAll(".source-card").length;
  document.getElementById("sourceCount").textContent = sourceCards;
  await Promise.all(pending.map(async ({ file, card }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("notebook_id", notebookId);
    try {
      await apiRequest("/ingest/upload", { method: "POST", body: formData });
      card.querySelector("small").textContent = "Indexed";
    } catch (error) {
      card.querySelector("small").textContent = `Failed · ${error.message}`;
      showToast(`Could not index ${file.name}`);
    }
  }));
  await loadNotebook();
  showToast(`${files.length} source${files.length === 1 ? "" : "s"} processed`);
}

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFiles(fileInput.files);
});

["dragenter", "dragover"].forEach((eventName) => {
  uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadZone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadZone.classList.remove("dragging");
  });
});

uploadZone.addEventListener("drop", (event) => {
  if (event.dataTransfer.files.length) uploadFiles(event.dataTransfer.files);
});

document.getElementById("addYoutube").addEventListener("click", async () => {
  const input = document.getElementById("youtubeInput");
  if (!input.value.trim()) {
    showToast("Paste a YouTube URL first");
    input.focus();
    return;
  }

  const formData = new FormData();
  formData.append("url", input.value.trim());
  formData.append("notebook_id", notebookId);
  try {
    await apiRequest("/ingest/youtube", { method: "POST", body: formData });
    const card = document.createElement("article");
    card.className = "source-card";
    card.innerHTML = `
      <span class="file-icon video">YT</span>
      <div><strong>YouTube video</strong><small>Transcript indexed</small></div>
      <button class="source-menu" aria-label="Source options">•••</button>
    `;
    document.getElementById("sourceList").prepend(card);
    await loadNotebook();
    input.value = "";
    showToast("YouTube source added");
  } catch (error) {
    showToast(`YouTube ingestion failed: ${error.message}`);
  }
});

async function ingestWebsite(endpoint, triggerButton) {
  const input = document.getElementById("websiteInput");
  const box = document.getElementById("websiteBox");
  const scrapeButton = document.getElementById("scrapeWebsite");
  const crawlButton = document.getElementById("crawlWebsite");
  const url = input.value.trim();

  if (!url) {
    showToast("Paste a website URL first");
    input.focus();
    return;
  }

  const formData = new FormData();
  formData.append("url", url);
  formData.append("notebook_id", notebookId);
  box.classList.add("loading");
  input.disabled = true;
  scrapeButton.disabled = true;
  crawlButton.disabled = true;
  triggerButton.classList.add("loading");

  try {
    const payload = await apiRequest(endpoint, {
      method: "POST",
      body: formData,
    });
    await loadNotebook();
    input.value = "";
    const count = payload.document_ids?.length || 1;
    showToast(`${count} website source${count === 1 ? "" : "s"} indexed`);
  } catch (error) {
    showToast(`Website ingestion failed: ${error.message}`);
  } finally {
    box.classList.remove("loading");
    input.disabled = false;
    scrapeButton.disabled = false;
    crawlButton.disabled = false;
    triggerButton.classList.remove("loading");
  }
}

document.getElementById("scrapeWebsite").addEventListener("click", (event) => {
  ingestWebsite("/ingest/scrape", event.currentTarget);
});

document.getElementById("crawlWebsite").addEventListener("click", (event) => {
  ingestWebsite("/ingest/website", event.currentTarget);
});

document.getElementById("refreshSummary").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;

  try {
    await refreshNotebookOverview();
  } catch (error) {
    showToast(`Summary failed: ${error.message}`);
  } finally {
    button.disabled = false;
  }
});

function renderMindMap(root) {
  elements.map.innerHTML = "";
  const tree = document.createElement("ul");
  tree.appendChild(renderNode(root));
  elements.map.appendChild(tree);
}

function renderNode(node) {
  const li = document.createElement("li");
  const button = document.createElement("button");
  button.className = "map-node";
  button.textContent = node.label;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    document.querySelectorAll(".map-node").forEach((item) => item.classList.remove("selected"));
    button.classList.add("selected");

    elements.selectedConcept.textContent = node.label;
    elements.conceptDescription.textContent = node.description || "A concept discovered across your notebook sources.";
    elements.prompt.value = `Explain "${node.label}" using my notebook sources. Give a simple explanation, important details, and examples.`;

    elements.conceptSources.classList.remove("active");
    void elements.conceptSources.offsetWidth;
    elements.conceptSources.classList.add("active");
    const activeSources = node.sources || 1;
    elements.conceptSources.querySelectorAll("i").forEach((bar, index) => {
      bar.style.opacity = index < activeSources ? "1" : "0.18";
    });
    elements.conceptSources.querySelector("small").textContent = `${activeSources} notebook source${activeSources === 1 ? "" : "s"} cover this concept`;
  });

  li.appendChild(button);
  if (node.children?.length) {
    const children = document.createElement("ul");
    node.children.forEach((child) => children.appendChild(renderNode(child)));
    li.appendChild(children);
  }
  return li;
}

function openMindMap() {
  elements.modal.classList.add("open");
  elements.modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  renderMindMap(mindMapData);
}

function closeMindMap() {
  elements.modal.classList.remove("open");
  elements.modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

document.getElementById("closeMindMap").addEventListener("click", closeMindMap);
elements.modal.addEventListener("click", (event) => {
  if (event.target === elements.modal) closeMindMap();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && elements.modal.classList.contains("open")) closeMindMap();
});

document.getElementById("generateMap").addEventListener("click", () => {
  const topic = document.getElementById("mindMapTopic").value.trim() || "Your notebook";
  const map = structuredClone(mindMapData);
  map.label = topic;
  map.description = `A generated overview of ${topic} based on the current notebook.`;
  renderMindMap(map);
  showToast(`Generated a map for ${topic}`);
});

document.getElementById("regenerateMap").addEventListener("click", () => {
  renderMindMap(mindMapData);
  showToast("Mind map regenerated");
});

document.getElementById("askFromMap").addEventListener("click", () => {
  const prompt = elements.prompt.value.trim();
  if (!prompt) {
    showToast("Select a concept first");
    return;
  }
  closeMindMap();
  submitPrompt(prompt);
});

renderMindMap(mindMapData);
loadNotebook().catch((error) => {
  showToast(`Could not load notebook: ${error.message}`);
});
