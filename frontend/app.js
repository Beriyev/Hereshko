const notebookId = new URLSearchParams(window.location.search).get("notebook_id");
const apiBaseUrl = window.HERESHKO_API_URL || "http://localhost:8000";
const sessionId = window.crypto?.randomUUID?.() || `session-${Date.now()}`;

const mindMapCache = new Map();
let mindMapSources = [];
let mindMapRoot = null;
let mindMapBusy = false;
let mapZoom = 1;
let mapZoomFrame = null;
let mapZoomTarget = 1;

const elements = {
  form: document.getElementById("chatForm"),
  input: document.getElementById("chatInput"),
  modeButton: document.getElementById("modeButton"),
  modeLabel: document.getElementById("modeLabel"),
  webSearchButton: document.getElementById("webSearchButton"),
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
let chatMode = "l1";

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

async function streamText(target, text, formatted = false) {
  target.replaceChildren();
  target.classList.add("stream-cursor", "streaming-reveal");

  if (formatted) {
    renderFormattedText(target, text);
    [...target.children].forEach((element) => element.classList.add("stream-block"));
  } else {
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
  }

  const duration = Math.min(3800, Math.max(1400, text.length * 6.5));
  target.style.setProperty("--stream-duration", `${duration}ms`);
  void target.offsetWidth;
  scrollToLatest();
  await wait(duration + 80);

  target.classList.remove("stream-cursor", "streaming-reveal");
  target.style.removeProperty("--stream-duration");
  [...target.children].forEach((element) => element.classList.remove("stream-block"));
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
    decorateTables(target);
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

function decorateTables(root) {
  root.querySelectorAll("table").forEach((table) => {
    const container = document.createElement("div");
    container.className = "table-scroll";
    container.tabIndex = 0;
    container.setAttribute("role", "region");
    container.setAttribute("aria-label", table.caption?.textContent.trim() || "Table; scroll horizontally to view all columns");
    table.parentNode.insertBefore(container, table);
    container.appendChild(table);
  });
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
  updateMindMapSources(sources);
  document.dispatchEvent(new CustomEvent("notebook-sources-updated", { detail: sources }));
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
    menu.setAttribute("aria-label", `Remove ${source.title}`);
    menu.title = `Remove ${source.title}`;
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
    menu.textContent = "\u2715";

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
      streamText(elements.summaryText, payload.summary, true),
      streamText(elements.summaryUpdated, `Updated ${new Date(payload.updated_at).toLocaleString()}`),
    ]);
    renderFormattedText(elements.summaryText, payload.summary);
    elements.summarySourceCount.textContent = payload.source_count;
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

function createL2Panel(row) {
  const panel = document.createElement("details");
  panel.className = "l2-research is-working";
  panel.open = true;
  const heading = document.createElement("summary");
  heading.textContent = "L2 · Planning questions…";
  heading.setAttribute("aria-live", "polite");
  const list = document.createElement("div");
  list.className = "l2-questions";
  panel.append(heading, list);
  row.prepend(panel);
  const questions = [];

  return {
    async update(event) {
      if (event.type === "planned") {
        heading.textContent = `L2 · Investigating ${event.questions.length} questions`;
        event.questions.forEach((question, index) => {
          const item = document.createElement("details");
          item.className = "l2-question";
          item.style.setProperty("--l2-order", index);
          const title = document.createElement("summary");
          const label = document.createElement("span");
          label.textContent = question;
          const status = document.createElement("small");
          status.textContent = "Waiting";
          title.append(label, status);
          const answer = document.createElement("div");
          answer.className = "l2-subanswer message-bubble";
          item.append(title, answer);
          list.appendChild(item);
          questions.push({ item, status, answer });
        });
      } else if (event.type === "answering") {
        questions[event.index].status.textContent = "Searching…";
        questions[event.index].item.classList.add("is-searching");
        questions[event.index].item.open = true;
      } else if (event.type === "answered") {
        const question = questions[event.index];
        question.item.classList.remove("is-searching");
        question.status.textContent = "Receiving answer…";
        if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
          await streamText(question.answer, event.answer, true);
        }
        renderFormattedText(question.answer, event.answer);
        addCitationCards(question.item, event.sources);
        question.status.textContent = "Answered";
      } else if (event.type === "synthesizing") {
        heading.textContent = "L2 · Preparing final answer…";
      } else if (event.type === "done") {
        heading.textContent = `L2 · ${questions.length} questions researched`;
        panel.classList.remove("is-working");
        panel.open = false;
      }
      scrollToLatest();
    },
    fail(message) {
      panel.classList.remove("is-working");
      questions.forEach((question) => question.item.classList.remove("is-searching"));
      heading.textContent = `L2 · ${message}`;
      questions.filter((question) => question.status.textContent !== "Answered")
        .forEach((question) => { question.status.textContent = "Not completed"; });
    },
  };
}

async function requestL2(body, panel) {
  const response = await fetch(`${apiBaseUrl}/chat/l2`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`L2 request failed (${response.status})`);
  }
  if (!response.body) throw new Error("L2 progress stream is unavailable.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let payload;
  async function handleLine(line) {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === "error") throw new Error(event.message);
    await panel.update(event);
    if (event.type === "done") payload = event;
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) await handleLine(line);
      if (done) break;
    }
    await handleLine(buffer);
  } finally {
    reader.releaseLock();
  }
  if (!payload) throw new Error("L2 stream ended before the final answer.");
  return payload;
}

async function submitPrompt(prompt) {
  const cleanPrompt = prompt.trim();
  if (!cleanPrompt || isStreaming) return;

  isStreaming = true;
  elements.modeButton.disabled = true;
  elements.webSearchButton.disabled = true;
  elements.empty?.remove();
  createMessage("user", cleanPrompt);
  elements.input.value = "";
  autoResizeTextarea();
  scrollToLatest();
  const { row, bubble } = createMessage("assistant");
  const research = chatMode === "l2" ? createL2Panel(row) : null;
  try {
    const body = {
      notebook_id: notebookId,
      query: cleanPrompt,
      session_id: sessionId,
      web_search: webSearchMode,
      mode: chatMode,
    };
    const payload = research ? await requestL2(body, research) : await apiRequest("/chat/l1", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const answer = payload.answer || "The notebook returned an empty answer.";
    bubble.classList.remove("typing-bubble");
    bubble.textContent = "";
    await streamText(bubble, answer, true);
    renderFormattedText(bubble, answer);
    addCitationCards(row, payload.sources);
  } catch (error) {
    research?.fail(error.message);
    bubble.classList.remove("typing-bubble");
    bubble.textContent = `I couldn’t reach the Hereshko backend: ${error.message}`;
    showToast("Chat request failed");
  } finally {
    scrollToLatest();
    isStreaming = false;
    elements.modeButton.disabled = false;
    elements.webSearchButton.disabled = false;
  }
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitPrompt(elements.input.value);
});

elements.modeButton.addEventListener("click", () => {
  chatMode = chatMode === "l1" ? "l2" : "l1";
  elements.modeButton.classList.toggle("active", chatMode === "l2");
  elements.modeButton.setAttribute("aria-pressed", String(chatMode === "l2"));
  elements.modeLabel.textContent = chatMode.toUpperCase();
  showToast(`${chatMode.toUpperCase()} mode enabled`);
});

elements.webSearchButton.addEventListener("click", () => {
  webSearchMode = !webSearchMode;
  elements.webSearchButton.classList.toggle("active", webSearchMode);
  elements.webSearchButton.setAttribute("aria-pressed", String(webSearchMode));
  const label = webSearchMode ? "Web Search on" : "Web Search off";
  elements.webSearchButton.setAttribute("aria-label", label);
  elements.webSearchButton.title = label;
  showToast(webSearchMode ? "Web Search enabled" : "Web Search disabled");
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
      <button class="source-menu" type="button" aria-label="Uploading source" disabled>&#10005;</button>
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

document.getElementById("addYoutube").addEventListener("click", async (event) => {
  const input = document.getElementById("youtubeInput");
  const button = event.currentTarget;
  const box = document.getElementById("youtubeBox");
  if (button.disabled) return;
  if (!input.value.trim()) {
    showToast("Paste a YouTube URL first");
    input.focus();
    return;
  }

  const formData = new FormData();
  formData.append("url", input.value.trim());
  formData.append("notebook_id", notebookId);
  box.classList.add("loading");
  box.setAttribute("aria-busy", "true");
  button.classList.add("loading");
  button.disabled = true;
  input.disabled = true;
  try {
    await apiRequest("/ingest/youtube", { method: "POST", body: formData });
    const card = document.createElement("article");
    card.className = "source-card";
    card.innerHTML = `
      <span class="file-icon video">YT</span>
      <div><strong>YouTube video</strong><small>Transcript indexed</small></div>
      <button class="source-menu" type="button" aria-label="Loading source" disabled>&#10005;</button>
    `;
    document.getElementById("sourceList").prepend(card);
    await loadNotebook();
    input.value = "";
    showToast("YouTube source added");
  } catch (error) {
    showToast(`YouTube ingestion failed: ${error.message}`);
  } finally {
    box.classList.remove("loading");
    box.setAttribute("aria-busy", "false");
    button.classList.remove("loading");
    button.disabled = false;
    input.disabled = false;
  }
});

async function ingestWebsite(endpoint, triggerButton) {
  const input = document.getElementById("websiteInput");
  if (input.disabled) return;
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
  box.setAttribute("aria-busy", "true");
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
    box.setAttribute("aria-busy", "false");
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

function updateMindMapSources(sources) {
  const select = document.getElementById("mindMapSource");
  const previous = select.value;
  mindMapSources = sources;
  select.replaceChildren();
  sources.forEach((source) => {
    const option = document.createElement("option");
    option.value = source.document_id;
    option.textContent = source.title;
    select.appendChild(option);
  });
  if (sources.some((source) => source.document_id === previous)) select.value = previous;
  if (!sources.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No sources yet";
    select.appendChild(option);
  }
  for (const id of mindMapCache.keys()) {
    if (!sources.some((source) => source.document_id === id)) mindMapCache.delete(id);
  }
  setMindMapBusy(mindMapBusy);
  if (select.value !== previous || !sources.length) showSelectedMindMap();
}

function resetMapConcept() {
  elements.selectedConcept.textContent = "Choose a node";
  elements.conceptDescription.textContent = "Select a concept to read its summary and ask a question.";
  elements.prompt.value = "";
  elements.conceptSources.querySelector("small").textContent = "No node selected";
}

function showMapMessage(title, description, loading = false) {
  stopMapZoom();
  mindMapRoot = null;
  resetMapConcept();
  const state = document.createElement("div");
  state.className = `map-empty-state${loading ? " loading" : ""}`;
  if (loading) {
    const dots = document.createElement("span");
    dots.className = "chat-loading-dots";
    dots.setAttribute("role", "status");
    dots.setAttribute("aria-label", "Generating mind map");
    for (let index = 0; index < 3; index++) dots.appendChild(document.createElement("i"));
    state.appendChild(dots);
  } else {
    const heading = document.createElement("strong");
    heading.textContent = title;
    const text = document.createElement("p");
    text.textContent = description;
    state.append(heading, text);
  }
  elements.map.replaceChildren(state);
  mapZoom = 1;
  requestAnimationFrame(() => updateMapScale());
}

function mindMapTree(nodes) {
  const byId = new Map(nodes.map((node) => [node.id, { ...node, children: [] }]));
  const roots = [...byId.values()].filter((node) => node.parent_id === null);
  if (roots.length !== 1 || byId.size !== nodes.length) throw new Error("The generated map has an invalid structure. Try regenerating it.");
  for (const node of byId.values()) {
    if (node.parent_id === null) continue;
    const parent = byId.get(node.parent_id);
    if (!parent) throw new Error("The generated map has a missing branch. Try regenerating it.");
    parent.children.push(node);
  }
  const visited = new Set();
  function visit(node) {
    if (visited.has(node.id)) throw new Error("The generated map has a circular branch. Try regenerating it.");
    visited.add(node.id);
    node.children.forEach(visit);
  }
  visit(roots[0]);
  if (visited.size !== nodes.length) throw new Error("The generated map has disconnected branches. Try regenerating it.");
  return roots[0];
}

function selectMapNode(node, button) {
  elements.map.querySelectorAll(".map-node").forEach((item) => {
    item.classList.remove("selected");
    item.setAttribute("aria-pressed", "false");
  });
  button.classList.add("selected");
  button.setAttribute("aria-pressed", "true");
  elements.selectedConcept.textContent = node.title;
  elements.conceptDescription.textContent = node.summary;
  const source = mindMapSources.find((item) => item.document_id === document.getElementById("mindMapSource").value);
  elements.prompt.value = `Explain "${node.title}" using ${source?.title || "my notebook sources"}. Give a simple explanation, important details, and examples.`;
  elements.conceptSources.querySelector("small").textContent = source?.title || "Selected notebook source";
}

function renderMindMap(root) {
  stopMapZoom();
  mindMapRoot = root;
  resetMapConcept();
  const tree = document.createElement("ul");
  tree.appendChild(renderNode(root));
  elements.map.replaceChildren(tree);
  requestAnimationFrame(fitMindMap);
}

function renderNode(node, depth = 0, order = 0) {
  const li = document.createElement("li");
  li.className = depth === 0 ? "map-root" : depth === 1 ? "map-theme" : "map-subtopic";
  const card = document.createElement("div");
  card.className = `map-node-card${depth === 0 ? " map-root-card" : ""}`;
  const shade = Math.min(218, 18 + depth * 28);
  card.style.setProperty("--map-node-background", `rgb(${shade}, ${shade}, ${shade})`);
  card.style.setProperty("--map-node-text", shade >= 125 ? "#111" : "#f2f2f2");
  card.style.setProperty("--map-node-border", shade >= 125 ? "rgba(0, 0, 0, 0.2)" : "rgba(255, 255, 255, 0.2)");
  card.style.setProperty("--map-highlight", shade >= 125 ? "rgba(0, 0, 0, 0.65)" : "rgba(255, 255, 255, 0.65)");
  card.style.setProperty("--map-delay", `${Math.min(depth * 75 + order * 45, 360)}ms`);
  const button = document.createElement("button");
  button.className = "map-node";
  const label = document.createElement("span");
  label.className = "map-node-label";
  label.textContent = node.title;
  button.appendChild(label);
  button.title = node.title;
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", () => selectMapNode(node, button));
  card.appendChild(button);
  li.appendChild(card);
  if (node.children.length) {
    const children = document.createElement("ul");
    children.className = depth === 0 ? "map-themes" : "map-subtopics";
    children.hidden = depth > 0;
    const toggle = document.createElement("button");
    toggle.className = "map-branch-toggle";
    const updateToggle = () => {
      toggle.textContent = children.hidden ? `+${node.children.length}` : "−";
      toggle.setAttribute("aria-expanded", String(!children.hidden));
      toggle.setAttribute("aria-label", `${children.hidden ? "Expand" : "Collapse"} ${node.title}`);
    };
    updateToggle();
    toggle.addEventListener("click", () => {
      stopMapZoom();
      const before = new Map([...elements.map.querySelectorAll(".map-node-card")]
        .filter((item) => item.offsetParent !== null)
        .map((item) => [item, item.getBoundingClientRect()]));
      children.hidden = !children.hidden;
      updateToggle();
      requestAnimationFrame(() => {
        updateMapScale();
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        for (const [item, previous] of before) {
          if (item.offsetParent === null) continue;
          const current = item.getBoundingClientRect();
          const x = (previous.left - current.left) / mapZoom;
          const y = (previous.top - current.top) / mapZoom;
          if (Math.abs(x) + Math.abs(y) > 1) {
            item.animate([
              { transform: `translate(${x}px, ${y}px)` },
              { transform: "translate(0, 0)" },
            ], { duration: 360, easing: "cubic-bezier(.2,.8,.2,1)" });
          }
        }
      });
    });
    card.appendChild(toggle);
    node.children.forEach((child, index) => children.appendChild(renderNode(child, depth + 1, index)));
    li.appendChild(children);
  }
  return li;
}

function updateMapConnectors() {
  const positions = [...elements.map.querySelectorAll(".map-node-card")]
    .filter((card) => card.offsetParent !== null)
    .map((card) => {
      const branch = card.parentElement.querySelector(":scope > ul.map-subtopics");
      return {
        node: card.parentElement,
        middle: card.offsetHeight / 2,
        branch,
        parentCenter: branch && !branch.hidden ? card.offsetLeft + card.offsetWidth / 2 - branch.offsetLeft - 8 : null,
      };
    });
  for (const position of positions) {
    position.node.style.setProperty("--map-node-middle", `${position.middle}px`);
    if (position.parentCenter !== null) position.branch.style.setProperty("--map-parent-center", `${position.parentCenter}px`);
  }
}

function updateMapScale(zoom = mapZoom) {
  updateMapConnectors();
  mapZoom = Math.max(0.2, Math.min(2.5, zoom));
  const viewport = document.getElementById("mapViewport");
  const surface = document.getElementById("mapSurface");
  const width = Math.max(elements.map.offsetWidth * mapZoom, viewport.clientWidth);
  surface.style.width = `${width}px`;
  surface.style.height = `${Math.max(elements.map.offsetHeight * mapZoom, viewport.clientHeight)}px`;
  elements.map.style.transform = `scale(${mapZoom})`;
  elements.map.style.left = `${Math.max(0, (width - elements.map.offsetWidth * mapZoom) / 2)}px`;
  document.getElementById("mapScale").textContent = `${Math.round(mapZoom * 100)}%`;
}

function stopMapZoom() {
  if (mapZoomFrame !== null) cancelAnimationFrame(mapZoomFrame);
  mapZoomFrame = null;
  mapZoomTarget = mapZoom;
}

function zoomMapAt(zoom, point) {
  const viewport = document.getElementById("mapViewport");
  const x = (viewport.scrollLeft + point.x - (parseFloat(elements.map.style.left) || 0)) / mapZoom;
  const y = (viewport.scrollTop + point.y) / mapZoom;
  updateMapScale(zoom);
  viewport.scrollLeft = x * mapZoom + (parseFloat(elements.map.style.left) || 0) - point.x;
  viewport.scrollTop = y * mapZoom - point.y;
}

function animateMapZoom(zoom, point) {
  stopMapZoom();
  mapZoomTarget = Math.max(0.2, Math.min(2.5, zoom));
  const viewport = document.getElementById("mapViewport");
  const anchor = point || { x: viewport.clientWidth / 2, y: viewport.clientHeight / 2 };
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    zoomMapAt(mapZoomTarget, anchor);
    return;
  }
  const startZoom = mapZoom;
  let startTime;
  function frame(time) {
    startTime ??= time;
    const progress = Math.min(1, (time - startTime) / 180);
    const eased = 1 - (1 - progress) ** 3;
    zoomMapAt(startZoom + (mapZoomTarget - startZoom) * eased, anchor);
    mapZoomFrame = progress < 1 ? requestAnimationFrame(frame) : null;
  }
  mapZoomFrame = requestAnimationFrame(frame);
}

function fitMindMap() {
  stopMapZoom();
  const viewport = document.getElementById("mapViewport");
  if (!viewport.clientWidth) return;
  updateMapScale(Math.min(1, (viewport.clientWidth - 32) / elements.map.offsetWidth,
    (viewport.clientHeight - 24) / elements.map.offsetHeight));
  viewport.scrollLeft = 0;
  viewport.scrollTop = 0;
}

function setMindMapBusy(busy) {
  mindMapBusy = busy;
  const select = document.getElementById("mindMapSource");
  select.disabled = busy || !mindMapSources.length;
  document.getElementById("generateMap").disabled = busy || !mindMapSources.length;
  document.getElementById("generateMap").textContent = busy ? "Generating…" : "Generate map";
  document.getElementById("regenerateMap").disabled = busy || !mindMapSources.length;
  elements.map.setAttribute("aria-busy", String(busy));
}

function showSelectedMindMap() {
  const sourceId = document.getElementById("mindMapSource").value;
  const cached = mindMapCache.get(sourceId);
  document.getElementById("mapHint").textContent = "Expand with + · Drag to pan · Scroll to move · Ctrl/⌘ + wheel to zoom";
  if (cached) renderMindMap(cached);
  else showMapMessage(mindMapSources.length ? "Break your sources down." : "Your map starts with a source",
    mindMapSources.length ? "Choose a source above, then generate its mind map." : "Add a document, website, or video to this notebook first.");
}

async function generateSelectedMindMap() {
  const sourceId = document.getElementById("mindMapSource").value;
  if (mindMapBusy || !sourceId) return;
  setMindMapBusy(true);
  showMapMessage("Connecting the ideas", "Building a mind map from your selected source…", true);
  document.getElementById("mapHint").textContent = "";
  try {
    const payload = await apiRequest(`/notebooks/${notebookId}/mindmap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: sourceId }),
    });
    const root = mindMapTree(payload.nodes);
    if (!mindMapSources.some((source) => source.document_id === sourceId)) return;
    mindMapCache.set(sourceId, root);
    if (document.getElementById("mindMapSource").value === sourceId) {
      renderMindMap(root);
      document.getElementById("mapHint").textContent = `${payload.nodes.length} concepts · Expand with + · Drag to pan · Ctrl/⌘ + wheel to zoom`;
    }
  } catch (error) {
    showMapMessage("Couldn't generate this map", `${error.message} Try Generate map again.`);
    document.getElementById("mapHint").textContent = "Choose a source and try again.";
    showToast(`Mind map failed: ${error.message}`);
  } finally {
    setMindMapBusy(false);
  }
}

function openMindMap() {
  elements.modal.classList.add("open");
  elements.modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  if (!mindMapBusy) showSelectedMindMap();
  requestAnimationFrame(fitMindMap);
  document.getElementById("closeMindMap").focus();
}

function closeMindMap() {
  stopMapZoom();
  elements.modal.classList.remove("open");
  elements.modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  document.getElementById("graphweaverButton").focus();
}

document.getElementById("closeMindMap").addEventListener("click", closeMindMap);
elements.modal.addEventListener("click", (event) => {
  if (event.target === elements.modal) closeMindMap();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && elements.modal.classList.contains("open")) closeMindMap();
});

document.getElementById("graphweaverButton").addEventListener("click", openMindMap);
document.getElementById("generateMap").addEventListener("click", generateSelectedMindMap);
document.getElementById("regenerateMap").addEventListener("click", generateSelectedMindMap);
document.getElementById("mindMapSource").addEventListener("change", showSelectedMindMap);
document.getElementById("mapZoomOut").addEventListener("click", () => animateMapZoom((mapZoomFrame === null ? mapZoom : mapZoomTarget) - 0.1));
document.getElementById("mapZoomIn").addEventListener("click", () => animateMapZoom((mapZoomFrame === null ? mapZoom : mapZoomTarget) + 0.1));
document.getElementById("mapFit").addEventListener("click", fitMindMap);
document.getElementById("mapCollapse").addEventListener("click", () => {
  if (mindMapRoot) renderMindMap(mindMapRoot);
});
window.addEventListener("resize", () => {
  if (elements.modal.classList.contains("open")) updateMapScale();
});

const mapViewport = document.getElementById("mapViewport");
let mapDrag = null;
let suppressMapClick = false;
mapViewport.addEventListener("wheel", (event) => {
  if (!mindMapRoot) return;
  if (event.ctrlKey || event.metaKey) {
    event.preventDefault();
    const bounds = mapViewport.getBoundingClientRect();
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? mapViewport.clientHeight : 1;
    const delta = Math.max(-120, Math.min(120, event.deltaY * unit));
    animateMapZoom((mapZoomFrame === null ? mapZoom : mapZoomTarget) * Math.exp(-delta * 0.0025),
      { x: event.clientX - bounds.left, y: event.clientY - bounds.top });
  } else if (event.shiftKey || (mapViewport.scrollHeight <= mapViewport.clientHeight && mapViewport.scrollWidth > mapViewport.clientWidth)) {
    event.preventDefault();
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? mapViewport.clientWidth : 1;
    mapViewport.scrollLeft += (event.deltaY || event.deltaX) * unit;
  }
}, { passive: false });
mapViewport.addEventListener("click", (event) => {
  if (!suppressMapClick) return;
  event.preventDefault();
  event.stopPropagation();
}, true);
mapViewport.addEventListener("pointerdown", (event) => {
  if (event.pointerType !== "mouse" || event.button !== 0 || event.target.closest(".map-branch-toggle")) return;
  stopMapZoom();
  suppressMapClick = false;
  mapDrag = { x: event.clientX, y: event.clientY, left: mapViewport.scrollLeft, top: mapViewport.scrollTop, moved: false };
});
mapViewport.addEventListener("pointermove", (event) => {
  if (!mapDrag) return;
  if (!mapDrag.moved && Math.hypot(event.clientX - mapDrag.x, event.clientY - mapDrag.y) < 5) return;
  if (!mapDrag.moved) {
    mapDrag.moved = true;
    suppressMapClick = true;
    mapViewport.setPointerCapture(event.pointerId);
    mapViewport.classList.add("dragging");
  }
  event.preventDefault();
  mapViewport.scrollLeft = mapDrag.left - event.clientX + mapDrag.x;
  mapViewport.scrollTop = mapDrag.top - event.clientY + mapDrag.y;
});
mapViewport.addEventListener("lostpointercapture", () => {
  mapDrag = null;
  mapViewport.classList.remove("dragging");
});
mapViewport.addEventListener("pointerup", (event) => {
  if (mapViewport.hasPointerCapture(event.pointerId)) mapViewport.releasePointerCapture(event.pointerId);
  mapDrag = null;
  mapViewport.classList.remove("dragging");
  setTimeout(() => { suppressMapClick = false; }, 0);
});
mapViewport.addEventListener("pointercancel", () => {
  mapDrag = null;
  suppressMapClick = false;
  mapViewport.classList.remove("dragging");
});
mapViewport.addEventListener("pointerleave", () => {
  if (mapDrag && !mapDrag.moved) mapDrag = null;
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

showSelectedMindMap();
setMindMapBusy(false);
if (notebookId) {
  loadNotebook().catch((error) => {
    showToast(`Could not load notebook: ${error.message}`);
  });
} else {
  window.location.replace("notebooks.html");
}
