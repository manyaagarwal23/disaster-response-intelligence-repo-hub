// Initialize Mermaid. "strict" stops LLM-generated diagrams from
// running scripts or adding click handlers.
if (window.mermaid) {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'strict' });
}

// ------------------------------------------------------------
// Safe HTML helpers
// ------------------------------------------------------------

// Escape plain text (user questions, file paths, code) before it goes into innerHTML
function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Render LLM markdown and strip anything dangerous (scripts, event handlers)
function renderMarkdown(text) {
    const html = window.marked ? marked.parse(String(text ?? '')) : escapeHtml(text);
    return window.DOMPurify ? DOMPurify.sanitize(html) : escapeHtml(text);
}

// Tab Switching Logic
function switchTab(tabId) {
    // Remove active class from all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Add active class to clicked tab
    document.getElementById(tabId).classList.add('active');

    // Find the corresponding button and make it active
    const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.getAttribute('onclick').includes(tabId));
    if (activeBtn) activeBtn.classList.add('active');
}

// Fill Search Bar from Suggestion Chips
function fillSearch(text) {
    const input = document.getElementById('searchInput');
    input.value = text;
    input.focus();
}

// Handle asking a question
async function askQuestion() {
    const input = document.getElementById('searchInput');
    const question = input.value.trim();

    if (!question) return;

    // Clear the input
    input.value = '';

    // Transform UI to Chat Mode (ChatGPT style)
    document.getElementById('home').classList.add('chat-mode');
    document.getElementById('chatHeader').classList.add('minimized');
    document.getElementById('suggestionsBox').classList.add('hidden');

    const chatMessages = document.getElementById('chatMessages');
    chatMessages.classList.remove('hidden');

    // 1. Append User Message Bubble
    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.innerHTML = `
        <div class="msg-avatar"><i class="ph ph-user"></i></div>
        <div class="msg-content">${escapeHtml(question)}</div>
    `;
    chatMessages.appendChild(userMsg);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // 2. Append AI Loading Bubble
    const aiMsgId = 'ai-msg-' + Date.now();
    const aiMsg = document.createElement('div');
    aiMsg.className = 'message ai';
    aiMsg.id = aiMsgId;
    aiMsg.innerHTML = `
        <div class="msg-avatar"><i class="ph ph-robot"></i></div>
        <div class="msg-content">
            <div class="typing-indicator"><span></span><span></span><span></span></div>
        </div>
    `;
    chatMessages.appendChild(aiMsg);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    const content = document.querySelector(`#${aiMsgId} .msg-content`);

    // 3. Fetch from backend
    let data;
    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: question })
        });

        data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(data.error || (data.detail && JSON.stringify(data.detail)) || `Server returned HTTP ${response.status}`);
        }
    } catch (error) {
        // Show the real problem - never a fake answer
        content.innerHTML = renderErrorCard(error.message || 'Could not reach the server.');
        addToHistory(question, `Error: ${error.message}`);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return;
    }

    renderRichAnswer(aiMsgId, data);

    addToHistory(
        question,
        (data.answer && data.answer.simple) || data.warning || 'Search results returned.'
    );

    // Scroll to bottom after answer loads
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderErrorCard(message) {
    return `
        <div class="info-card error-card">
            <div class="card-header error-header"><i class="ph ph-warning"></i> Something went wrong</div>
            <div class="card-body">${escapeHtml(message)}</div>
        </div>
    `;
}

// ------------------------------------------------------------
// Persistent history: saved in the browser (localStorage) so it
// survives a page refresh. Wrapped in try/catch because storage can
// be unavailable (private window, blocked site data).
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

// Add item to Chat History Tab and save it
function addToHistory(question, answer) {
    saveHistoryEntry(question, answer);
    renderHistoryItem(question, answer);
}

// Draw one history item (newest goes on top)
function renderHistoryItem(question, answer) {
    const historyList = document.getElementById('chatHistoryList');

    // Remove empty state if present
    const emptyState = historyList.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const historyItem = document.createElement('div');
    historyItem.className = 'history-item';
    historyItem.innerHTML = `
        <div class="history-item-q" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center;" onclick="this.nextElementSibling.classList.toggle('hidden')">
            <div style="display: flex; align-items: center; gap: 0.5rem;"><i class="ph ph-user"></i> ${escapeHtml(question)}</div>
            <i class="ph ph-caret-down"></i>
        </div>
        <div class="history-item-a hidden" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--glass-border);">
            <i class="ph ph-robot"></i>
            <div style="flex: 1;" class="mode-content">${renderMarkdown(answer)}</div>
        </div>
    `;

    // Add to top of list
    historyList.prepend(historyItem);
}

// Allow pressing Enter to submit
document.getElementById('searchInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        askQuestion();
    }
});

// Make Questions Tab items clickable
document.addEventListener('DOMContentLoaded', () => {
    // Restore saved history (oldest first, so the newest ends up on top)
    loadSavedHistory().forEach(entry => renderHistoryItem(entry.question, entry.answer));

    document.querySelectorAll('.dataset-list li').forEach(li => {
        li.style.cursor = 'pointer';
        li.addEventListener('click', () => {
            // Switch to home tab
            switchTab('home');

            // Set the search input and ask the question
            const input = document.getElementById('searchInput');
            input.value = li.innerText;
            askQuestion();
        });

        // Add a nice hover effect
        li.addEventListener('mouseover', () => li.style.color = 'var(--accent)');
        li.addEventListener('mouseout', () => li.style.color = '');
    });
});

// Rich Answer Rendering
// data = { answer: {simple, technical, diagram_type, diagram_code} | null,
//          sources: [{file, start_line, end_line, class, method, type, content}],
//          llm_used, warning }
function renderRichAnswer(aiMsgId, data) {
    const container = document.querySelector(`#${aiMsgId} .msg-content`);
    const answer = data.answer || {};
    const sources = data.sources || [];

    let html = `<div class="answer-stack">`;

    // Warning (e.g. no API key / rate limit -> search results only)
    if (data.warning) {
        html += `
            <div class="info-card warning-card">
                <div class="card-header warning-header"><i class="ph ph-warning-circle"></i> ${data.llm_used ? 'Note' : 'Search results only'}</div>
                <div class="card-body">${escapeHtml(data.warning)}</div>
            </div>`;
    }

    // Simple Summary Box (Blue)
    if (answer.simple) {
        html += `
            <div class="info-card simple-card">
                <div class="card-header blue-header">
                    <i class="ph ph-info"></i> AI Summary
                </div>
                <div class="card-body markdown-body">${renderMarkdown(answer.simple)}</div>
            </div>`;
    }

    // Technical Details Box (Violet)
    if (answer.technical) {
        html += `
            <div class="info-card technical-card">
                <div class="card-header violet-header">
                    <i class="ph ph-code"></i> Technical Details
                </div>
                <div class="card-body markdown-body">${renderMarkdown(answer.technical)}</div>
            </div>`;
    }

    // Mermaid Diagram placeholder (Teal) - code is inserted as text below
    const hasDiagram = Boolean(answer.diagram_code || answer.fallback_diagram_code);
    if (hasDiagram) {
        html += `
            <div class="info-card diagram-container teal-card" style="display: none;">
                <div class="card-header teal-header"><i class="ph ph-projector-screen-chart"></i> Architecture Visualization</div>
                <div class="card-body mermaid"></div>
            </div>`;
    }

    // Sources (Green): the chunks that were ACTUALLY retrieved and given to the LLM
    if (sources.length > 0) {
        html += `
            <div class="info-card sources-container green-card">
                <div class="card-header green-header" onclick="toggleSources(this)" style="cursor: pointer; display: flex; justify-content: space-between;">
                    <div><i class="ph ph-file-code"></i> <span>Repository Evidence (${sources.length} retrieved chunks)</span></div>
                    <i class="ph ph-caret-down caret"></i>
                </div>
                <div class="sources-list ${answer.simple ? 'hidden' : ''}">`;

        sources.forEach(s => {
            const location = s.start_line ? `${s.file}:${s.start_line}-${s.end_line}` : s.file;
            const context = [s.class, s.method].filter(Boolean).join('::') || s.type;
            html += `
                <details class="source-item">
                    <summary>
                        <span class="source-file"><i class="ph ph-file-php"></i> ${escapeHtml(location)}</span>
                        <span class="source-context">${escapeHtml(context)}</span>
                    </summary>
                    <pre class="source-code"><code>${escapeHtml(s.content)}</code></pre>
                </details>`;
        });
        html += `</div></div>`;
    }

    html += `</div>`; // Close answer-stack

    container.innerHTML = html;

    // Render mermaid diagram if present
    if (hasDiagram) {
        // LLM diagram first; the backup built from retrieved code if it fails
        renderDiagram(container, [answer.diagram_code, answer.fallback_diagram_code]);
    }
}

// Mermaid must measure text while drawing, which fails inside a hidden
// (display: none) element - Firefox throws, Chrome measures everything
// as 0. So draw with mermaid.render() (it uses its own temporary,
// visible element), then insert the finished SVG and show the card.
let diagramCounter = 0;

async function renderDiagram(container, candidates) {
    const containerEl = container.querySelector('.diagram-container');
    const mermaidEl = container.querySelector('.mermaid');

    if (!window.mermaid) {
        console.warn('Mermaid library did not load - diagram not shown');
        containerEl.remove();
        return;
    }

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
            // securityLevel 'strict' already sanitizes the SVG
            mermaidEl.innerHTML = svg;
            containerEl.style.display = 'block';
            return;
        } catch (e) {
            console.warn('Mermaid diagram could not be rendered, trying backup', e);
            // mermaid.render leaves an error element in <body> on failure
            document.getElementById('d' + id)?.remove();
            document.getElementById(id)?.remove();
        }
    }

    // Neither the LLM diagram nor the backup could be drawn
    containerEl.remove();
}

window.toggleSources = function(header) {
    const list = header.nextElementSibling;
    const caret = header.querySelector('.caret');
    if (list.classList.contains('hidden')) {
        list.classList.remove('hidden');
        caret.style.transform = 'rotate(180deg)';
    } else {
        list.classList.add('hidden');
        caret.style.transform = 'rotate(0deg)';
    }
};
