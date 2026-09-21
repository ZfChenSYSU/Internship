const shell = document.querySelector("#shell");
const form = document.querySelector("#chatForm");
const input = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const reasoningToggle = document.querySelector("#reasoningToggle");
const conversation = document.querySelector("#conversation");
const questionText = document.querySelector("#questionText");
const status = document.querySelector("#status");
const statusText = document.querySelector("#statusText");
const answerText = document.querySelector("#answerText");
const reasoningPanel = document.querySelector("#reasoningPanel");
const reasoningText = document.querySelector("#reasoningText");
const metrics = document.querySelector("#metrics");
const sources = document.querySelector("#sources");
const sourcesToggle = document.querySelector("#sourcesToggle");
const sourceCount = document.querySelector("#sourceCount");
const sourceList = document.querySelector("#sourceList");

let busy = false;
let reasoningEnabled = false;
let answerBuffer = "";
let reasoningBuffer = "";

const escapeHtml = (value) => value
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function inlineFormat(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(S\d+)\]/g, '<span class="citation">$1</span>');
}

function renderAnswer(value) {
  const lines = value.split("\n");
  const output = [];
  let listType = null;
  const closeList = () => {
    if (listType) output.push(`</${listType}>`);
    listType = null;
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      closeList();
      continue;
    }
    if (line.startsWith("### ")) {
      closeList();
      output.push(`<h3>${inlineFormat(line.slice(4))}</h3>`);
    } else if (line.startsWith("## ")) {
      closeList();
      output.push(`<h2>${inlineFormat(line.slice(3))}</h2>`);
    } else if (/^[-*]\s+/.test(line)) {
      if (listType !== "ul") { closeList(); output.push("<ul>"); listType = "ul"; }
      output.push(`<li>${inlineFormat(line.replace(/^[-*]\s+/, ""))}</li>`);
    } else if (/^\d+[.)]\s+/.test(line)) {
      if (listType !== "ol") { closeList(); output.push("<ol>"); listType = "ol"; }
      output.push(`<li>${inlineFormat(line.replace(/^\d+[.)]\s+/, ""))}</li>`);
    } else {
      closeList();
      output.push(`<p>${inlineFormat(line)}</p>`);
    }
  }
  closeList();
  answerText.innerHTML = output.join("");
}

function resizeInput() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 220)}px`;
  sendButton.disabled = busy || !input.value.trim();
}

function setBusy(value) {
  busy = value;
  input.disabled = value;
  reasoningToggle.disabled = value;
  sendButton.disabled = value || !input.value.trim();
}

function resetResponse(question) {
  shell.classList.add("has-result");
  conversation.hidden = false;
  questionText.textContent = question;
  answerBuffer = "";
  reasoningBuffer = "";
  answerText.innerHTML = "";
  reasoningText.textContent = "";
  reasoningPanel.hidden = !reasoningEnabled;
  reasoningPanel.open = reasoningEnabled;
  status.hidden = false;
  statusText.textContent = "正在检索医学证据…";
  metrics.hidden = true;
  sources.hidden = true;
  sourceList.hidden = true;
  sourcesToggle.setAttribute("aria-expanded", "false");
  sourceList.innerHTML = "";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderSources(items) {
  sourceList.innerHTML = "";
  for (const item of items) {
    const article = document.createElement("article");
    article.className = "source-item";
    const path = (item.title_path || []).join(" › ");
    article.innerHTML = `
      <div class="source-topline">
        <span class="tier">${escapeHtml(item.authority_tier)}级</span>
        <div>
          <div class="source-title">${escapeHtml(item.id)} · ${escapeHtml(item.title || "未命名来源")}</div>
          <div class="source-path">${escapeHtml(path || item.source_path || "")}</div>
        </div>
      </div>
      <div class="source-text">${escapeHtml(item.text || "")}</div>
    `;
    sourceList.append(article);
  }
  sourceCount.textContent = `${items.length} 条`;
  sources.hidden = items.length === 0;
}

async function submitQuestion(question) {
  setBusy(true);
  resetResponse(question);
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: question, reasoning: reasoningEnabled }),
    });
    if (!response.ok || !response.body) {
      throw new Error(`请求失败（HTTP ${response.status}）`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "";
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = pending.split("\n");
      pending = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === "status") {
          status.hidden = false;
          statusText.textContent = event.message;
        } else if (event.type === "evidence") {
          renderSources(event.items || []);
        } else if (event.type === "reasoning") {
          reasoningBuffer += event.delta;
          reasoningText.textContent = reasoningBuffer;
        } else if (event.type === "answer") {
          status.hidden = true;
          answerBuffer += event.delta;
          renderAnswer(answerBuffer);
        } else if (event.type === "done") {
          status.hidden = true;
          metrics.textContent = `检索与生成共 ${event.total_seconds.toFixed(1)} 秒`;
          metrics.hidden = false;
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
      if (done) break;
    }
    if (!answerBuffer) throw new Error("模型没有返回可显示的回答");
  } catch (error) {
    status.hidden = true;
    answerText.innerHTML = `<p><strong>请求未完成</strong></p><p>${escapeHtml(error.message || String(error))}</p>`;
  } finally {
    setBusy(false);
    input.value = "";
    resizeInput();
    input.focus();
  }
}

reasoningToggle.addEventListener("click", () => {
  reasoningEnabled = !reasoningEnabled;
  reasoningToggle.setAttribute("aria-pressed", String(reasoningEnabled));
});

sourcesToggle.addEventListener("click", () => {
  const expanded = sourcesToggle.getAttribute("aria-expanded") === "true";
  sourcesToggle.setAttribute("aria-expanded", String(!expanded));
  sourceList.hidden = expanded;
});

input.addEventListener("input", resizeInput);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question || busy) return;
  submitQuestion(question);
});

resizeInput();
