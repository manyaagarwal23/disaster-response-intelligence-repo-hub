// Initialize Mermaid
if (window.mermaid) {
    mermaid.initialize({ startOnLoad: false, theme: 'dark' });
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
    // Optional: automatically ask the question when chip is clicked
    // askQuestion();
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
        <div class="msg-content">${question}</div>
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

    // 3. Fetch from backend
    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: question })
        });

        if (!response.ok) throw new Error('Network error');
        
        const data = await response.json();
        
        try {
            // Attempt to parse the LLM's JSON string from data.answer
            let jsonString = data.answer;
            // The LLM might output text before or after the JSON, let's extract the JSON block
            const jsonMatch = jsonString.match(/\{[\s\S]*\}/);
            if (jsonMatch) jsonString = jsonMatch[0];
            
            const parsed = JSON.parse(jsonString);
            renderRichAnswer(aiMsgId, parsed);
            
            // Add to History Tab secretly in the background
            addToHistory(question, parsed.simple || "Answer generated successfully.");
        } catch (e) {
            console.error("Failed to parse JSON response, falling back to markdown", e);
            let text = data.answer;
            if (window.marked) text = marked.parse(text);
            document.querySelector(`#${aiMsgId} .msg-content`).innerHTML = text;
            
            // Add to History Tab (fallback)
            addToHistory(question, data.answer || "Answer generated successfully.");
        }

    } catch (error) {
        // Fallback for demo if backend errors
        const fallbackText = "This is a simulated AI response to your question. Once we integrate the backend fully, this will pull real source code references from ChromaDB and answer using the Groq LLM!";
        document.querySelector(`#${aiMsgId} .msg-content`).innerHTML = `<p>${fallbackText}</p>`;
        addToHistory(question, fallbackText);
    }

    // Scroll to bottom after answer loads
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add item to Chat History Tab (in the background)
function addToHistory(question, answer) {
    const historyList = document.getElementById('chatHistoryList');
    
    // Remove empty state if present
    const emptyState = historyList.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    let displayAnswer = answer;
    if (window.marked && answer) {
        displayAnswer = marked.parse(answer);
    }

    const historyItem = document.createElement('div');
    historyItem.className = 'history-item';
    historyItem.innerHTML = `
        <div class="history-item-q" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center;" onclick="this.nextElementSibling.classList.toggle('hidden')">
            <div style="display: flex; align-items: center; gap: 0.5rem;"><i class="ph ph-user"></i> ${question}</div>
            <i class="ph ph-caret-down"></i>
        </div>
        <div class="history-item-a hidden" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--glass-border);">
            <i class="ph ph-robot"></i> 
            <div style="flex: 1;" class="mode-content">${displayAnswer}</div>
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
function renderRichAnswer(aiMsgId, data) {
    const container = document.querySelector(`#${aiMsgId} .msg-content`);
    
    let html = `
        <div class="answer-stack">
            <!-- Simple Summary Box (Blue) -->
            ${data.simple ? `
            <div class="info-card simple-card">
                <div class="card-header blue-header">
                    <i class="ph ph-info"></i> AI Summary
                </div>
                <div class="card-body markdown-body">
                    ${window.marked ? marked.parse(data.simple) : data.simple}
                </div>
            </div>` : ''}
            
            <!-- Technical Details Box (Violet) -->
            ${data.technical ? `
            <div class="info-card technical-card">
                <div class="card-header violet-header">
                    <i class="ph ph-code"></i> Technical Details
                </div>
                <div class="card-body markdown-body">
                    ${window.marked ? marked.parse(data.technical) : data.technical}
                </div>
            </div>` : ''}
    `;

    // Add Mermaid Diagram if exists (Teal)
    if (data.diagram_type === 'mermaid' && data.diagram_code) {
        const diagramId = 'mermaid-' + Date.now();
        html += `
            <div class="info-card diagram-container teal-card" id="container-${diagramId}" style="display: none;">
                <div class="card-header teal-header"><i class="ph ph-projector-screen-chart"></i> Architecture Visualization</div>
                <div class="card-body mermaid" id="${diagramId}">
                    ${data.diagram_code}
                </div>
            </div>
        `;
    }
    
    // Add Sources (Green)
    if (data.sources && data.sources.length > 0) {
        html += `
            <div class="info-card sources-container green-card">
                <div class="card-header green-header" onclick="toggleSources(this)" style="cursor: pointer; display: flex; justify-content: space-between;">
                    <div><i class="ph ph-file-code"></i> <span>Repository Evidence (${data.sources.length} files)</span></div>
                    <i class="ph ph-caret-down caret"></i>
                </div>
                <div class="sources-list hidden">
        `;
        data.sources.forEach(s => {
            html += `
                <div class="source-item">
                    <span class="source-file"><i class="ph ph-file-php"></i> ${s.file}</span>
                    <span class="source-context">${s.context}</span>
                </div>
            `;
        });
        html += `</div></div>`;
    }

    html += `</div>`; // Close answer-stack

    container.innerHTML = html;

    // Initialize mermaid if present
    if (data.diagram_type === 'mermaid' && window.mermaid) {
        setTimeout(() => {
            const mermaidEl = document.querySelector(`#${aiMsgId} .mermaid`);
            const containerEl = document.querySelector(`#${aiMsgId} .diagram-container`);
            if (!mermaidEl || !containerEl) return;
            
            try {
                // Initialize mermaid on this specific element
                mermaid.init(undefined, mermaidEl);
                
                // Check if Mermaid injected its ugly red error SVG anyway
                if (mermaidEl.innerHTML.includes('Syntax error') || mermaidEl.innerHTML.includes('Parse error')) {
                    console.warn("Mermaid generated an error graphic due to LLM hallucination. Hiding container.");
                    containerEl.remove(); // Silently destroy it
                } else {
                    // Success! Show the beautiful diagram
                    containerEl.style.display = 'block';
                }
            } catch (e) {
                console.error("Mermaid parsing failed", e);
                containerEl.remove();
            }
        }, 100);
    }
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
