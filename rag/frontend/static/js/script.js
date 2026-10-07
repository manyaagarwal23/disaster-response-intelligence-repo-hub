// Disaster Response Intelligence Repo Hub — frontend
// Talks to:  POST /api/ask   GET /api/search   GET /api/stats

const USHAHIDI_REPO = 'https://github.com/ushahidi/platform';
const THEME_KEY = 'drih-theme';
let appStats = null;

// ------------------------------------------------------------
// Helpers
// ------------------------------------------------------------
const $ = (id) => document.getElementById(id);

function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Render LLM markdown and strip anything dangerous (scripts, handlers)
function renderMarkdown(text) {
    const html = window.marked ? marked.parse(String(text ?? '')) : escapeHtml(text);
    return window.DOMPurify ? DOMPurify.sanitize(html) : escapeHtml(text);
}

// Syntax-highlight every <pre><code> inside `root`. highlight.js only adds
// <span> tags to already-escaped text, so it is safe on sanitized HTML.
function highlightCode(root) {
    if (!window.hljs) return;
    root.querySelectorAll('pre code').forEach(el => {
        try { hljs.highlightElement(el); } catch (e) { /* leave plain text */ }
    });
}

function fmtMs(ms) {
    if (ms == null) return '–';
    return ms >= 1000 ? (ms / 1000).toFixed(1) + ' s' : Math.round(ms) + ' ms';
}

function fmtNum(n) {
    return Number(n || 0).toLocaleString();
}

function githubUrl(file, start, end) {
    const ref = (appStats && appStats.ushahidi_commit) || 'develop';
    let url = `${USHAHIDI_REPO}/blob/${ref}/${file}`;
    if (start) url += `#L${start}` + (end && end !== start ? `-L${end}` : '');
    return url;
}

let toastTimer = null;
function showToast(message, icon = 'ph-check-circle') {
    const toast = $('toast');
    if (!toast) return;
    toast.innerHTML = `<i class="ph ${icon}"></i>${escapeHtml(message)}`;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2200);
}

// ------------------------------------------------------------
// Theme (dark by default, light on request; remembered per browser)
// ------------------------------------------------------------
function currentTheme() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

function applyTheme(theme) {
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* storage unavailable */ }
    const button = $('themeToggle');
    if (button) {
        button.innerHTML = theme === 'light'
            ? '<i class="ph ph-moon"></i><span>Dark</span>'
            : '<i class="ph ph-sun"></i><span>Light</span>';
    }
}

function toggleTheme() {
    applyTheme(currentTheme() === 'light' ? 'dark' : 'light');
}

// ------------------------------------------------------------
// Tabs
// ------------------------------------------------------------
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.toggle('active', tab.id === tabId));
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tabId));
    const focus = { home: 'searchInput', codesearch: 'codeSearchInput' }[tabId];
    if (focus) setTimeout(() => $(focus).focus(), 50);
}

// ------------------------------------------------------------
// System status (sidebar + hero numbers)
// ------------------------------------------------------------
// Right after a (re)start the server is still loading the embedding model,
// so keep retrying for a while before declaring the index unavailable.
async function loadStats(attempt = 1) {
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) throw new Error((await response.json()).error || 'stats unavailable');
        appStats = await response.json();
        const byType = appStats.by_type || {};
        $('statChunks').textContent = fmtNum(appStats.chunks) + ' chunks';
        $('statModel').textContent = (appStats.llm_model || '').split('/').pop() || '–';
        $('statCommit').textContent = (appStats.ushahidi_commit || '').slice(0, 8);
        $('heroChunks').textContent = fmtNum(appStats.chunks);
        $('heroMethods').textContent = fmtNum((byType.method || 0) + (byType.function || 0));
        $('heroDocs').textContent = fmtNum(byType.doc || 0);
        $('heroFiles').textContent = fmtNum(appStats.files);
        if (appStats.llm_configured) {
            setStatus('ok', 'Live · LLM + search');
        } else {
            setStatus('warn', 'Search-only (no LLM key)');
        }
    } catch (error) {
        if (attempt < 8) {
            setStatus('warn', 'Loading index…');
            setTimeout(() => loadStats(attempt + 1), 5000);
        } else {
            setStatus('bad', 'Index not ready');
            $('statChunks').textContent = '–';
        }
    }
}

function setStatus(level, text) {
    $('statusDot').className = 'status-dot ' + level;
    $('statusText').textContent = text;
}

// ------------------------------------------------------------
// Ask (RAG answer)
// ------------------------------------------------------------
function fillSearch(text) {
    const input = $('searchInput');
    input.value = text;
    input.focus();
}

function askSuggestion(text) {
    fillSearch(text);
    askQuestion();
}

function newChat() {
    $('chatMessages').innerHTML = '';
    $('chatMessages').classList.add('hidden');
    $('home').classList.remove('chat-mode');
    $('chatHeader').classList.remove('minimized');
    $('suggestionsBox').classList.remove('hidden');
    $('searchInput').focus();
}

const PROGRESS_STEPS = [
    [0, 'Searching the index', 'ph-magnifying-glass'],
    [1200, 'Reranking the top 10 with the LLM', 'ph-sort-ascending'],
    [4500, 'Writing the answer and drawing the diagram', 'ph-brain'],
];

function pipelineHtml() {
    return `<div class="pipeline" role="status">${PROGRESS_STEPS.map(([, label, icon], i) => `
        <div class="step ${i === 0 ? 'active' : ''}" data-step="${i}">
            <span class="step-icon"><i class="ph ${icon}"></i></span>
            <span class="typing-status">${label}</span>
            ${i === 0 ? '<span class="typing-indicator"><span></span><span></span><span></span></span>' : ''}
        </div>`).join('')}</div>`;
}

function setPipelineStep(aiMsg, index) {
    aiMsg.querySelectorAll('.step').forEach((el, i) => {
        el.classList.toggle('done', i < index);
        el.classList.toggle('active', i === index);
    });
    const dots = aiMsg.querySelector('.typing-indicator');
    const active = aiMsg.querySelector('.step.active');
    if (dots && active && !active.contains(dots)) active.appendChild(dots);
}

async function askQuestion() {
    const input = $('searchInput');
    const question = input.value.trim();
    if (!question) return;
    input.value = '';

    // Switch the page into chat mode
    $('home').classList.add('chat-mode');
    $('chatHeader').classList.add('minimized');
    $('suggestionsBox').classList.add('hidden');
    const chatMessages = $('chatMessages');
    chatMessages.classList.remove('hidden');

    // User bubble
    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.innerHTML = `
        <div class="msg-avatar"><i class="ph ph-user"></i></div>
        <div class="msg-content">${escapeHtml(question)}</div>`;
    chatMessages.appendChild(userMsg);

    // AI bubble with pipeline progress
    const aiMsgId = 'ai-msg-' + Date.now();
    const aiMsg = document.createElement('div');
    aiMsg.className = 'message ai';
    aiMsg.id = aiMsgId;
    aiMsg.innerHTML = `
        <div class="msg-avatar"><i class="ph ph-robot"></i></div>
        <div class="msg-content">${pipelineHtml()}</div>`;
    chatMessages.appendChild(aiMsg);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    const timers = PROGRESS_STEPS.slice(1).map(([delay], i) => setTimeout(() => setPipelineStep(aiMsg, i + 1), delay));

    const content = aiMsg.querySelector('.msg-content');
    const started = performance.now();
    let data;
    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
        });
        data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || (data.detail && JSON.stringify(data.detail)) || `Server returned HTTP ${response.status}`);
        }
    } catch (error) {
        timers.forEach(clearTimeout);
        // Show the real problem - never a fake answer
        content.innerHTML = renderErrorCard(error.message || 'Could not reach the server.');
        addToHistory(question, `Error: ${error.message}`);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return;
    }
    timers.forEach(clearTimeout);

    data.clientMs = Math.round(performance.now() - started);
    renderRichAnswer(aiMsgId, data);
    $('statLatency').textContent = fmtMs((data.timings && data.timings.total_ms) || data.clientMs);

    addToHistory(question, (data.answer && data.answer.simple) || data.warning || 'Search results returned.');
    chatMessages.scrollTop = aiMsg.offsetTop - 12;
}

function renderErrorCard(message) {
    return `
        <div class="info-card error-card">
            <div class="card-header error-header"><i class="ph ph-warning"></i> Something went wrong</div>
            <div class="card-body">${escapeHtml(message)}</div>
        </div>`;
}

// data = { answer: {simple, technical, diagram_type, diagram_code, fallback_diagram_code} | null,
//          sources: [{file, start_line, end_line, class, method, type, score, content}],
//          llm_used, warning, timings }
function renderRichAnswer(aiMsgId, data) {
    const container = document.querySelector(`#${aiMsgId} .msg-content`);
    const answer = data.answer || {};
    const sources = data.sources || [];
    const t = data.timings || {};

    let html = `<div class="answer-meta">`;
    html += `<span class="meta-chip strong"><i class="ph ph-timer"></i> ${fmtMs(t.total_ms ?? data.clientMs)}</span>`;
    if (t.retrieval_ms != null) html += `<span class="meta-chip" title="vector + hybrid search"><i class="ph ph-magnifying-glass"></i> search ${fmtMs(t.retrieval_ms)}</span>`;
    if (data.llm_used) {
        html += `<span class="meta-chip" title="LLM reranking of the top 10"><i class="ph ph-sort-ascending"></i> rerank ${fmtMs(t.rerank_ms)}</span>`;
        html += `<span class="meta-chip" title="LLM answer generation"><i class="ph ph-brain"></i> answer ${fmtMs(t.generation_ms)}</span>`;
    }
    html += `<span class="meta-chip"><i class="ph ph-files"></i> ${sources.length} sources</span>`;
    if (answer.simple) html += `<button class="icon-btn" onclick="copyAnswer(this)" title="Copy the answer as text"><i class="ph ph-copy"></i> Copy</button>`;
    html += `</div><div class="answer-stack">`;

    if (data.warning) {
        html += `
            <div class="info-card warning-card">
                <div class="card-header warning-header"><i class="ph ph-warning-circle"></i> ${data.llm_used ? 'Note' : 'Search results only'}</div>
                <div class="card-body">${escapeHtml(data.warning)}</div>
            </div>`;
    }

    if (answer.simple) {
        html += `
            <div class="info-card simple-card">
                <div class="card-header blue-header"><i class="ph ph-info"></i> AI Summary</div>
                <div class="card-body markdown-body" data-copy>${renderMarkdown(answer.simple)}</div>
            </div>`;
    }

    if (answer.technical) {
        html += `
            <div class="info-card technical-card">
                <div class="card-header violet-header"><i class="ph ph-code"></i> Technical Details</div>
                <div class="card-body markdown-body" data-copy>${renderMarkdown(answer.technical)}</div>
            </div>`;
    }

    const hasDiagram = Boolean(answer.diagram_code || answer.fallback_diagram_code);
    if (hasDiagram) {
        html += `
            <div class="info-card diagram-container teal-card" style="display: none;">
                <div class="card-header teal-header">
                    <i class="ph ph-tree-structure"></i> Architecture Visualization
                    <div class="card-actions"><button class="card-action" onclick="openDiagramModal(this)"><i class="ph ph-arrows-out"></i> Expand</button></div>
                </div>
                <div class="card-body mermaid"></div>
            </div>`;
    }

    if (sources.length > 0) {
        html += `
            <div class="info-card sources-container green-card">
                <div class="card-header green-header" onclick="toggleSources(this)">
                    <i class="ph ph-file-code"></i> Repository Evidence
                    <span class="pill">${sources.length} retrieved chunks</span>
                    <i class="ph ph-caret-down caret"></i>
                </div>
                <div class="sources-list ${answer.simple ? 'hidden' : ''}">
                    ${sources.map((s, i) => sourceItemHtml(s, i + 1)).join('')}
                </div>
            </div>`;
    }

    html += `</div>`;
    container.innerHTML = html;
    highlightCode(container);

    if (hasDiagram) {
        // LLM diagram first; the backup built from retrieved code if it fails
        renderDiagram(container, [answer.diagram_code, answer.fallback_diagram_code]);
    }
}

// One retrieved chunk / search hit, shared by evidence lists and Code Search
function sourceItemHtml(s, rank, withExplain = false) {
    const lines = s.start_line ? `L${s.start_line}${s.end_line && s.end_line !== s.start_line ? '–' + s.end_line : ''}` : '';
    const context = [s.class, s.method].filter(Boolean).join('::');
    const pct = Math.max(4, Math.min(100, Math.round((s.score || 0) * 100)));
    const file = String(s.file || '');
    const slash = file.lastIndexOf('/');
    const dir = slash >= 0 ? file.slice(0, slash + 1) : '';
    const name = slash >= 0 ? file.slice(slash + 1) : file;
    const type = String(s.type || '').toLowerCase();
    const language = type === 'doc' ? 'markdown' : 'php';
    const explain = withExplain
        ? `<div class="source-actions"><button onclick="explainResult(${JSON.stringify(file)}, ${JSON.stringify(context)})"><i class="ph ph-sparkle"></i> Explain with AI</button></div>`
        : '';
    return `
        <details class="source-item">
            <summary>
                <div class="source-top">
                    <span class="source-rank">${rank}</span>
                    <span class="source-file"><i class="ph ${type === 'doc' ? 'ph-file-text' : 'ph-file-php'}"></i><span class="dir">${escapeHtml(dir)}</span><span class="name">${escapeHtml(name)}</span></span>
                    ${lines ? `<span class="source-lines">${lines}</span>` : ''}
                    <a class="source-link" href="${githubUrl(file, s.start_line, s.end_line)}" target="_blank" rel="noopener" onclick="event.stopPropagation()"><i class="ph ph-github-logo"></i> GitHub</a>
                </div>
                <div class="source-bottom">
                    ${context ? `<span class="source-context">${escapeHtml(context)}</span>` : ''}
                    ${type ? `<span class="source-type ${escapeHtml(type)}">${escapeHtml(type)}</span>` : ''}
                    ${s.score != null ? `<span class="score"><span class="score-bar"><span style="width:${pct}%"></span></span>${Number(s.score).toFixed(2)}</span>` : ''}
                </div>
            </summary>
            <pre class="source-code"><code class="language-${language}">${escapeHtml(s.content)}</code></pre>
            ${explain}
        </details>`;
}

function copyAnswer(button) {
    const card = button.closest('.msg-content');
    const text = Array.from(card.querySelectorAll('[data-copy]')).map(el => el.innerText).join('\n\n');
    navigator.clipboard.writeText(text).then(() => {
        button.innerHTML = '<i class="ph ph-check"></i> Copied';
        showToast('Answer copied to the clipboard');
        setTimeout(() => { button.innerHTML = '<i class="ph ph-copy"></i> Copy'; }, 1500);
    }).catch(() => showToast('Could not access the clipboard', 'ph-warning'));
}

// ------------------------------------------------------------
// Diagrams
// ------------------------------------------------------------
// Mermaid must measure text while drawing, which fails inside a hidden
// element. So draw with mermaid.render() (its own temporary element),
// then insert the finished SVG and show the card.
let diagramCounter = 0;

async function renderDiagram(container, candidates) {
    const containerEl = container.querySelector('.diagram-container');
    const mermaidEl = container.querySelector('.mermaid');

    if (!window.mermaid) {
        console.warn('Mermaid library did not load - diagram not shown');
        containerEl.remove();
        return;
    }

    // "strict" stops LLM-generated diagrams from running scripts
    mermaid.initialize({ startOnLoad: false, theme: currentTheme() === 'light' ? 'neutral' : 'dark', securityLevel: 'strict' });

    for (const candidate of candidates) {
        if (!candidate) continue;

        // The LLM sometimes wraps the code in ```mermaid fences anyway
        const code = String(candidate)
            .replace(/^\s*```(?:mermaid)?\s*/i, '')
            .replace(/\s*```\s*$/, '')
            .trim();

        const id = 'diagram-svg-' + (++diagramCounter);
        try {
            const { svg } = await mermaid.render(id, code);
            mermaidEl.innerHTML = svg;   // securityLevel 'strict' already sanitized it
            containerEl.style.display = 'block';
            return;
        } catch (e) {
            console.warn('Mermaid diagram could not be rendered, trying backup', e);
            document.getElementById('d' + id)?.remove();
            document.getElementById(id)?.remove();
        }
    }

    // Neither the LLM diagram nor the backup could be drawn
    containerEl.remove();
}

function openDiagramModal(button) {
    const svg = button.closest('.diagram-container').querySelector('.mermaid').innerHTML;
    const modal = $('diagramModal');
    modal.querySelector('.modal-body').innerHTML = svg;
    modal.classList.remove('hidden');
}

function closeDiagramModal() {
    const modal = $('diagramModal');
    modal.classList.add('hidden');
    modal.querySelector('.modal-body').innerHTML = '';
}

window.toggleSources = function (header) {
    const list = header.nextElementSibling;
    const caret = header.querySelector('.caret');
    list.classList.toggle('hidden');
    caret.style.transform = list.classList.contains('hidden') ? 'rotate(0deg)' : 'rotate(180deg)';
};

// ------------------------------------------------------------
// Code Search (instant, no LLM)
// ------------------------------------------------------------
async function runCodeSearch() {
    const query = $('codeSearchInput').value.trim();
    const k = $('codeSearchK').value;
    const meta = $('codeSearchMeta');
    const list = $('codeSearchResults');
    if (!query) return;

    meta.innerHTML = `<span class="typing-indicator"><span></span><span></span><span></span></span> Searching…`;
    const started = performance.now();
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&k=${encodeURIComponent(k)}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `Server returned HTTP ${response.status}`);

        const ms = Math.round(performance.now() - started);
        meta.innerHTML = `<span class="meta-chip strong"><i class="ph ph-lightning"></i> ${data.results.length} results in ${fmtMs(ms)}</span>
                          <span class="meta-chip"><i class="ph ph-magnifying-glass"></i> retrieval ${fmtMs(data.timings && data.timings.retrieval_ms)}</span>
                          <span>for “${escapeHtml(query)}”</span>`;
        list.innerHTML = data.results.length
            ? data.results.map((s, i) => sourceItemHtml(s, i + 1, true)).join('')
            : `<div class="empty-state"><i class="ph ph-binoculars"></i>Nothing matched. Try describing what the code does.</div>`;
        highlightCode(list);
    } catch (error) {
        meta.innerHTML = '';
        list.innerHTML = renderErrorCard(error.message);
    }
}

function explainResult(file, context) {
    switchTab('home');
    askSuggestion(context ? `Explain ${context} in ${file}` : `Explain the file ${file}`);
}

// ------------------------------------------------------------
// History: saved in localStorage so it survives a page refresh.
// Wrapped in try/catch because storage can be unavailable.
// ------------------------------------------------------------
const HISTORY_KEY = 'drih-chat-history-v1';
const HISTORY_LIMIT = 100;

function loadSavedHistory() {
    try {
        const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
        return Array.isArray(saved) ? saved : [];
    } catch (e) {
        return [];
    }
}

function saveHistoryEntry(question, answer) {
    try {
        const saved = loadSavedHistory();
        saved.push({ question, answer, time: new Date().toISOString() });
        localStorage.setItem(HISTORY_KEY, JSON.stringify(saved.slice(-HISTORY_LIMIT)));
    } catch (e) {
        console.warn('Could not save chat history', e);
    }
}

function addToHistory(question, answer) {
    saveHistoryEntry(question, answer);
    renderHistoryItem(question, answer, new Date().toISOString());
}

function renderHistoryItem(question, answer, time) {
    const historyList = $('chatHistoryList');
    const emptyState = historyList.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const when = time ? new Date(time).toLocaleString() : '';
    const item = document.createElement('div');
    item.className = 'history-item';
    item.innerHTML = `
        <div class="history-item-q" style="cursor: pointer;" onclick="this.nextElementSibling.classList.toggle('hidden')">
            <i class="ph ph-user"></i> ${escapeHtml(question)}
            <span class="history-time">${escapeHtml(when)}</span>
            <i class="ph ph-caret-down"></i>
        </div>
        <div class="history-item-a hidden" style="margin-top: 0.8rem; padding-top: 0.8rem; border-top: 1px solid var(--border);">
            <i class="ph ph-robot"></i>
            <div style="flex: 1;" class="markdown-body">${renderMarkdown(answer)}</div>
        </div>`;
    historyList.prepend(item);
    updateHistoryCount();
}

function updateHistoryCount() {
    const n = document.querySelectorAll('#chatHistoryList .history-item').length;
    $('historyCount').textContent = `${n} saved`;
    const nav = $('navHistoryCount');
    if (nav) nav.textContent = String(n);
}

function clearHistory() {
    try { localStorage.removeItem(HISTORY_KEY); } catch (e) { /* ignore */ }
    $('chatHistoryList').innerHTML = '<div class="empty-state"><i class="ph ph-clock-counter-clockwise"></i>No questions asked yet. Start on the Ask tab.</div>';
    updateHistoryCount();
    showToast('History cleared', 'ph-trash');
}

// ------------------------------------------------------------
// Init
// ------------------------------------------------------------
const PLACEHOLDERS = [
    'Ask anything about the Ushahidi codebase…',
    'Where is an incoming SMS report parsed?',
    'How does the V5 posts API check permissions?',
    'What does the UpdateUsecase do?',
    'Which data source plugins exist?',
];

document.addEventListener('DOMContentLoaded', () => {
    applyTheme(currentTheme());
    loadStats();

    // Restore saved history (oldest first, so the newest ends up on top)
    loadSavedHistory().forEach(entry => renderHistoryItem(entry.question, entry.answer, entry.time));
    updateHistoryCount();

    $('searchInput').addEventListener('keypress', (e) => { if (e.key === 'Enter') askQuestion(); });
    $('codeSearchInput').addEventListener('keypress', (e) => { if (e.key === 'Enter') runCodeSearch(); });

    // Rotate example questions in the empty, unfocused search box
    let placeholderIndex = 0;
    setInterval(() => {
        const input = $('searchInput');
        if (document.activeElement === input || input.value) return;
        placeholderIndex = (placeholderIndex + 1) % PLACEHOLDERS.length;
        input.placeholder = PLACEHOLDERS[placeholderIndex];
    }, 3500);

    // Test Dataset questions are clickable
    document.querySelectorAll('.dataset-list li').forEach(li => {
        li.addEventListener('click', () => {
            switchTab('home');
            fillSearch(li.innerText.trim());
            askQuestion();
        });
    });

    // Keyboard: "/" or Ctrl/Cmd+K focuses the active search box, Esc closes the diagram
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDiagramModal();
        const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
        const wantsFocus = (e.key === '/' && !typing) || (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey));
        if (wantsFocus) {
            e.preventDefault();
            const active = document.querySelector('.tab-content.active');
            (active && active.id === 'codesearch' ? $('codeSearchInput') : $('searchInput')).focus();
        }
    });
});
