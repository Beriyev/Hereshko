const notebookId = "nb-1";
const apiBaseUrl = window.HERESHKO_API_URL || "http://localhost:8000";
const sessionId = window.crypto?.randomUUID?.() || `session-${Date.now()}`;

const mindMapData = {
  label: "Machine Learning",
  description: "Systems that learn patterns from data to make predictions or decisions.",
  sources: 4,
  children: [
    {
      label: "Neural Networks",
      description: "Layered function approximators inspired by connected biological neurons.",
      sources: 3,
      children: [
        { label: "Backpropagation", description: "Computes gradients through the chain rule.", sources: 2 },
        { label: "Optimization", description: "Updates model parameters to minimize a loss function.", sources: 3 },
        { label: "Generalization", description: "The model's ability to perform well on unseen data.", sources: 2 },
      ],
    },
    {
      label: "Transformers",
      description: "Sequence models built around attention rather than recurrence.",
      sources: 4,
      children: [
        { label: "Self-attention", description: "Relates each token to every other relevant token.", sources: 4 },
        { label: "Positional encoding", description: "Injects token order into a non-recurrent architecture.", sources: 2 },
        {
          label: "Representations",
          description: "Learned numerical descriptions of concepts and relationships.",
          sources: 3,
          children: [
            { label: "Embeddings", description: "Dense vectors that encode semantic properties.", sources: 3 },
            { label: "Context", description: "Information surrounding a token that shapes its meaning.", sources: 2 },
          ],
        },
      ],
    },
    {
      label: "Evaluation",
      description: "Methods for measuring model quality, reliability, and failure modes.",
      sources: 2,
      children: [
        { label: "Metrics", description: "Quantitative measures aligned with the task objective.", sources: 2 },
        { label: "Bias & variance", description: "A framework for understanding underfitting and overfitting.", sources: 2 },
      ],
    },
  ],
};

const randomResponses = [
  "Hi! I’m ready to help you explore this notebook. Your current sources cover neural networks, transformers, attention, and model evaluation. Ask for an explanation, comparison, revision plan, or a source-grounded quiz and I’ll trace the answer back to the exact material.",
  "Hello! This notebook has been indexed and its main concepts are connected. We could begin with self-attention, compare transformers with recurrent networks, or turn the uploaded material into a focused study session.",
  "Hey there. I’ve mapped the ideas across your sources and can help you move from a broad overview to the exact supporting passage. Try asking what the most important concept is, where the sources agree, or what you should revise first.",
];

const elements = {
  form: document.getElementById("chatForm"),
  input: document.getElementById("chatInput"),
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

function showToast(message) {
  clearTimeout(toastTimer);
  elements.toast.querySelector("p").textContent = message;
  elements.toast.classList.add("show");
  toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 2300);
}

function autoResizeTextarea() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 130)}px`;
}

function createMessage(role, text = "") {
  const row = document.createElement("div");
  row.className = `chat-row ${role}`;

  if (role === "assistant") {
    const label = document.createElement("div");
    label.className = "message-label";
    label.innerHTML = "<i>H</i> Hereshko";
    row.appendChild(label);
  }

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;
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
  target.classList.add("stream-cursor");
  const words = text.split(/(\s+)/);

  for (const word of words) {
    if (/^\s+$/.test(word)) {
      target.textContent += word;
      continue;
    }

    for (const character of word) {
      target.textContent += character;
      const punctuationPause = /[.,!?]/.test(character) ? 46 : 0;
      await wait(10 + Math.random() * 15 + punctuationPause);
    }
    scrollToLatest();
  }

  target.classList.remove("stream-cursor");
}

function addCitationCards(row, citations = []) {
  const sources = document.createElement("div");
  sources.className = "answer-sources";
  citations.forEach((citation, index) => {
    const number = citation.marker || index + 1;
    const source = document.createElement("button");
    source.textContent = number;
    source.title = citation.source_name || `Open source ${number}`;
    source.addEventListener("click", () => showToast(citation.content || `Source ${number}`));
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
      body: JSON.stringify({ notebook_id: notebookId, query: cleanPrompt, session_id: sessionId }),
    });
    await streamText(bubble, payload.answer || "The notebook returned an empty answer.");
    addCitationCards(row, payload.sources);
  } catch (error) {
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
    document.getElementById("sourceCount").textContent = document.querySelectorAll(".source-card").length;
    input.value = "";
    showToast("YouTube source added");
  } catch (error) {
    showToast(`YouTube ingestion failed: ${error.message}`);
  }
});

document.getElementById("refreshSummary").addEventListener("click", () => {
  const summary = document.getElementById("summaryText");
  summary.classList.remove("refreshing");
  void summary.offsetWidth;
  summary.classList.add("refreshing");
  setTimeout(() => {
    summary.textContent = "Your notebook connects neural-network training with transformer design, emphasizing attention, learned representations, and evaluation. The material moves from foundational mechanisms to practical questions about reliability and generalization.";
    showToast("Notebook summary refreshed");
  }, 360);
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

document.getElementById("openMindMap").addEventListener("click", openMindMap);
document.getElementById("closeMindMap").addEventListener("click", closeMindMap);
elements.modal.addEventListener("click", (event) => {
  if (event.target === elements.modal) closeMindMap();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && elements.modal.classList.contains("open")) closeMindMap();
  if ((event.metaKey || event.ctrlKey) && event.key === "3") {
    event.preventDefault();
    openMindMap();
  }
});

document.getElementById("generateMap").addEventListener("click", () => {
  const topic = document.getElementById("mindMapTopic").value.trim() || "Machine Learning";
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
