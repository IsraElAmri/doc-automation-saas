/* ================================================================
   DocAI — Frontend JavaScript Application (Authenticated & Redesigned)
   ================================================================ */

const API = '';  // same origin
let isRegisterMode = false;
let documents = [];
let activeDocId = null;

// ── DOM Ready ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initUploadZone();
    initChat();
    checkAuthStatus();
});

// ── Auth & Global Interceptor ────────────────────────────────────────
function getToken() {
    return localStorage.getItem('token');
}

function getAuthHeaders() {
    const token = getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

async function apiFetch(url, options = {}) {
    const headers = { ...getAuthHeaders(), ...(options.headers || {}) };
    try {
        const response = await fetch(url, { ...options, headers });
        
        if (response.status === 401) {
            // Expired or invalid token
            logout(true);
            return response;
        }

        if (response.status === 429) {
            showBanner('warning', 'Slow down — you hit the request limit. Try again shortly.');
            return response;
        }

        if (response.status >= 500) {
            showBanner('error', 'Server error encountered. Please try again.');
        }

        return response;
    } catch (err) {
        showBanner('error', 'Network error. Please check your connection.');
        throw err;
    }
}

async function checkAuthStatus() {
    const token = getToken();
    const modal = document.getElementById('auth-modal');

    if (!token) {
        modal.classList.add('active');
        document.getElementById('user-profile').style.display = 'none';
        return;
    }

    try {
        const res = await apiFetch(`${API}/auth/me`);
        if (res.ok) {
            modal.classList.remove('active');
            document.getElementById('user-profile').style.display = 'flex';
            loadDocuments();
        } else {
            logout();
        }
    } catch {
        // Handled by apiFetch
    }
}

function toggleAuthMode() {
    isRegisterMode = !isRegisterMode;
    const title = document.getElementById('auth-modal-title');
    const submitBtn = document.getElementById('auth-submit-btn');
    const toggleText = document.getElementById('auth-toggle-text');
    const toggleBtn = toggleText.nextElementSibling;

    if (isRegisterMode) {
        title.textContent = 'Create Account';
        submitBtn.textContent = 'Register';
        toggleText.textContent = 'Already have an account?';
        toggleBtn.textContent = 'Sign In';
    } else {
        title.textContent = 'Sign In';
        submitBtn.textContent = 'Sign In';
        toggleText.textContent = "Don't have an account?";
        toggleBtn.textContent = 'Register';
    }
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    const email = document.getElementById('auth-email').value;
    const password = document.getElementById('auth-password').value;
    const endpoint = isRegisterMode ? '/auth/register' : '/auth/login';

    try {
        const res = await fetch(`${API}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();

        if (res.ok) {
            localStorage.setItem('token', data.access_token);
            checkAuthStatus();
        } else {
            showBanner('error', data.detail || 'Authentication failed');
        }
    } catch {
        showBanner('error', 'Network error during authentication');
    }
}

function logout(isSessionExpired = false) {
    localStorage.removeItem('token');
    documents = [];
    activeDocId = null;
    document.getElementById('user-profile').style.display = 'none';
    const modal = document.getElementById('auth-modal');
    modal.classList.add('active');
    renderDocuments();
    if (isSessionExpired) {
        showBanner('warning', 'Session expired. Please sign in again.');
    }
}

// ── Views ────────────────────────────────────────────────────────────
function switchView(view) {
    document.querySelectorAll('.view-section').forEach(v => v.classList.remove('active'));
    const activeView = document.getElementById(`view-${view}`);
    if (activeView) activeView.classList.add('active');
}

// ── Banners ──────────────────────────────────────────────────────────
function showBanner(type, text) {
    const banner = document.getElementById(`banner-${type}`);
    const bannerText = document.getElementById(`banner-${type}-text`);
    if (banner && bannerText) {
        bannerText.textContent = text;
        banner.style.display = 'flex';
        setTimeout(() => { banner.style.display = 'none'; }, 6000);
    }
}

// ── Document List (Paper Metaphor) ───────────────────────────────────
async function loadDocuments() {
    if (!getToken()) return;
    try {
        const res = await apiFetch(`${API}/documents`);
        if (!res.ok) return;
        const data = await res.json();
        documents = data.documents || [];
        renderDocuments();
    } catch {
        // Handled
    }
}

function renderDocuments() {
    const list = document.getElementById('documents-grid');
    
    if (documents.length === 0) {
        list.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 0.85rem;">No documents uploaded yet.</div>`;
        return;
    }

    list.innerHTML = documents.map(doc => {
        const isActive = doc.id === activeDocId;
        const date = new Date(doc.created_at).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric'
        });
        const sizeStr = doc.text_length > 1000
            ? `${(doc.text_length / 1000).toFixed(1)}k chars`
            : `${doc.text_length} chars`;

        const category = doc.category || 'General Document';

        return `
            <div class="doc-card ${isActive ? 'active' : ''}" onclick="selectDocument(${doc.id})">
                <div class="doc-card-title">${escapeHtml(doc.filename)}</div>
                <div class="doc-card-meta">
                    <span style="background: rgba(0, 68, 235, 0.08); color: var(--primary); padding: 2px 6px; border-radius: 4px; font-weight: 500;">${escapeHtml(category)}</span>
                    <span>•</span>
                    <span>${date}</span>
                </div>
                <div class="doc-card-actions">
                    <button class="view-summary-btn" onclick="event.stopPropagation(); extractDoc(${doc.id}, '${escapeHtml(doc.filename)}')">
                        ✨ Extract
                    </button>
                    <button class="doc-delete-btn" onclick="event.stopPropagation(); deleteDoc(${doc.id}, '${escapeHtml(doc.filename)}')" title="Delete">
                        ✕
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function selectDocument(docId) {
    activeDocId = docId;
    const doc = documents.find(d => d.id === docId);
    if (!doc) return;

    renderDocuments();
    switchView('chat');

    document.getElementById('chat-active-doc-title').textContent = doc.filename;
    document.getElementById('chat-input').disabled = false;
    document.getElementById('chat-send').disabled = false;
    
    loadChatHistory(docId);
}

// ── Upload Zone ──────────────────────────────────────────────────────
function initUploadZone() {
    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('file-input');

    zone.addEventListener('dragover', e => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
    });

    input.addEventListener('change', () => {
        if (input.files.length) handleUpload(input.files[0]);
        input.value = '';
    });
}

async function handleUpload(file) {
    const progressWrapper = document.getElementById('upload-progress-wrapper');
    const progressBar = document.getElementById('upload-progress-bar');
    const filenameEl = document.getElementById('upload-filename');

    filenameEl.textContent = file.name;
    progressWrapper.style.display = 'block';
    progressBar.style.width = '30%';

    const formData = new FormData();
    formData.append('file', file);

    try {
        progressBar.style.width = '70%';
        const res = await apiFetch(`${API}/upload`, {
            method: 'POST',
            body: formData,
        });

        if (res.ok) {
            progressBar.style.width = '100%';
            setTimeout(() => { progressWrapper.style.display = 'none'; }, 1000);
            await loadDocuments();
            const data = await res.json();
            if (data.document_id) selectDocument(data.document_id);
        } else {
            progressWrapper.style.display = 'none';
            const data = await res.json();
            showBanner('error', data.detail || 'Upload failed');
        }
    } catch {
        progressWrapper.style.display = 'none';
    }
}

// ── Extract (OCR) Modal ──────────────────────────────────────────────
async function extractDoc(docId, filename) {
    const modal = document.getElementById('extract-modal');
    modal.classList.add('active');

    try {
        const res = await apiFetch(`${API}/extract/${docId}`);
        const data = await res.json();
        modal.classList.remove('active');

        if (res.ok) {
            // Show extracted info cleanly in chat as AI message
            selectDocument(docId);
            appendMessage('ai', `**Extracted Information for ${filename}:**\n\n${data.extracted_info}`);
        } else {
            showBanner('error', data.detail || 'Extraction failed');
        }
    } catch {
        modal.classList.remove('active');
    }
}

// ── Delete Flow (with confirmation) ──────────────────────────────────
async function deleteDoc(docId, filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"? This cannot be undone.`)) return;

    try {
        const res = await apiFetch(`${API}/documents/${docId}`, {
            method: 'DELETE',
        });
        if (res.ok) {
            if (activeDocId === docId) {
                activeDocId = null;
                switchView('upload');
            }
            loadDocuments();
        } else {
            const data = await res.json();
            showBanner('error', data.detail || 'Delete failed');
        }
    } catch {
        // Handled
    }
}

// ── Chat ─────────────────────────────────────────────────────────────
function initChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');

    sendBtn.addEventListener('click', sendChatMessage);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
}

async function loadChatHistory(docId) {
    const messagesEl = document.getElementById('chat-messages');
    messagesEl.innerHTML = '';

    try {
        const res = await apiFetch(`${API}/chat-history/${docId}`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.chats && data.chats.length > 0) {
            data.chats.forEach(chat => {
                appendMessage('user', chat.question);
                appendMessage('ai', chat.answer);
            });
        } else {
            messagesEl.innerHTML = `
                <div class="chat-welcome">
                    <span class="chat-welcome-icon">💬</span>
                    <p>Ask anything about this document.</p>
                </div>
            `;
        }
    } catch {
        // Handled
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question || !activeDocId) return;

    const welcome = document.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    appendMessage('user', question);
    input.value = '';
    input.disabled = true;

    try {
        const res = await apiFetch(`${API}/ask/${activeDocId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
        });

        if (res.ok) {
            const data = await res.json();
            appendMessage('ai', data.answer);
        } else {
            const data = await res.json();
            appendMessage('ai', `Error: ${data.detail || 'Failed to get answer'}`);
        }
    } catch {
        appendMessage('ai', 'Error sending message.');
    }

    input.disabled = false;
    input.focus();
}

function appendMessage(role, text) {
    const messagesEl = document.getElementById('chat-messages');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;

    if (role === 'ai') {
        bubble.innerHTML = formatMarkdown(text);
    } else {
        bubble.textContent = text;
    }

    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Utilities ────────────────────────────────────────────────────────
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}
