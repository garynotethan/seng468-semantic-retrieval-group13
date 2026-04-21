function resolveApiBase() {
    const override = localStorage.getItem('apiBaseOverride');
    if (override) return override;

    const { protocol, hostname } = window.location;
    const pageIsHttp = protocol === 'http:' || protocol === 'https:';

    if (pageIsHttp && hostname && hostname !== 'localhost' && hostname !== '127.0.0.1') {
        return `http://${hostname}:8080`;
    }

    return 'http://localhost:8080';
}

const API_BASE = resolveApiBase();
let currentToken = localStorage.getItem('token') || null;
let currentUsername = localStorage.getItem('username') || null;
let authMode = 'login'; // 'login' or 'signup'

// DOM Elements
const authView = document.getElementById('auth-view');
const dashboardView = document.getElementById('dashboard-view');
const authForm = document.getElementById('auth-form');
const authSubmitBtn = document.getElementById('auth-submit');
const authError = document.getElementById('auth-error');
const welcomeMsg = document.getElementById('welcome-msg');
const docsList = document.getElementById('docs-list');
const fileUpload = document.getElementById('file-upload');
const fileNameDisplay = document.getElementById('file-name');
const uploadBtn = document.getElementById('upload-btn');
const uploadStatus = document.getElementById('upload-status');
const searchForm = document.getElementById('search-form');
const searchResults = document.getElementById('search-results');
const systemBanner = document.getElementById('system-banner');
let documentPollId = null;

// Initialization
function init() {
    checkApiConnection();

    if (currentToken) {
        showDashboard();
    } else {
        showAuth();
    }
}

// UI Navigation
function showAuth() {
    authView.classList.add('active');
    dashboardView.classList.remove('active');
}

function showDashboard() {
    authView.classList.remove('active');
    dashboardView.classList.add('active');
    welcomeMsg.textContent = `Welcome, ${currentUsername}`;
    fetchDocuments();
    
    // Poll for document status updates every 5 seconds
    if (!documentPollId) {
        documentPollId = setInterval(fetchDocuments, 5000);
    }
}

function switchAuthTab(mode) {
    authMode = mode;
    document.getElementById('tab-login').classList.toggle('active', mode === 'login');
    document.getElementById('tab-signup').classList.toggle('active', mode === 'signup');
    authSubmitBtn.textContent = mode === 'login' ? 'Login' : 'Sign Up';
    authError.textContent = '';
}

// Authentication
async function handleAuth(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    const endpoint = authMode === 'login' ? '/auth/login' : '/auth/signup';
    authError.textContent = '';
    authSubmitBtn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.error || 'Authentication failed');
        }

        if (authMode === 'signup') {
            // After signup, automatically login
            authMode = 'login';
            handleAuth(e);
        } else {
            currentToken = data.token;
            currentUsername = username;
            localStorage.setItem('token', currentToken);
            localStorage.setItem('username', currentUsername);
            showDashboard();
        }
    } catch (err) {
        authError.textContent = err.message;
    } finally {
        authSubmitBtn.disabled = false;
    }
}

function logout() {
    currentToken = null;
    currentUsername = null;
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    showAuth();
}

async function checkApiConnection() {
    systemBanner.textContent = `Checking backend at ${API_BASE}...`;
    systemBanner.className = 'system-banner';

    try {
        const res = await fetch(`${API_BASE}/documents`);
        if (res.status === 401) {
            systemBanner.textContent = `Backend reachable at ${API_BASE}. Log in, choose a PDF, then upload.`;
            systemBanner.className = 'system-banner ok';
            return;
        }

        systemBanner.textContent = `Backend responded with status ${res.status}. Open DevTools for details if the UI still looks stuck.`;
        systemBanner.className = 'system-banner warn';
    } catch (err) {
        systemBanner.textContent = `Cannot reach backend at ${API_BASE}. Start Docker and check "docker compose logs -f api worker".`;
        systemBanner.className = 'system-banner error';
        console.error('Backend connection check failed:', err);
    }
}

// Document Management
function updateFileName() {
    if (fileUpload.files.length > 0) {
        fileNameDisplay.textContent = fileUpload.files[0].name;
        uploadBtn.disabled = false;
    } else {
        fileNameDisplay.textContent = '';
        uploadBtn.disabled = true;
    }
}

async function handleUpload(e) {
    e.preventDefault();
    if (fileUpload.files.length === 0) return;

    const file = fileUpload.files[0];
    const formData = new FormData();
    formData.append('file', file);

    uploadBtn.disabled = true;
    uploadStatus.textContent = 'Uploading...';

    try {
        const res = await fetch(`${API_BASE}/documents`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${currentToken}`
            },
            body: formData
        });

        if (!res.ok) {
            if (res.status === 401) logout();
            throw new Error('Upload failed');
        }

        uploadStatus.textContent = 'Upload started!';
        uploadStatus.style.color = '';
        fileUpload.value = '';
        updateFileName();
        fetchDocuments();
        
        setTimeout(() => { uploadStatus.textContent = ''; }, 3000);
    } catch (err) {
        uploadStatus.textContent = err.message;
        uploadStatus.style.color = 'var(--danger-color)';
    } finally {
        uploadBtn.disabled = false;
    }
}

async function fetchDocuments() {
    if (!currentToken) return;

    try {
        const res = await fetch(`${API_BASE}/documents`, {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });

        if (res.status === 401) {
            logout();
            return;
        }

        const docs = await res.json();
        renderDocuments(docs);
        systemBanner.textContent = `Backend reachable at ${API_BASE}.`;
        systemBanner.className = 'system-banner ok';
    } catch (err) {
        console.error('Failed to fetch documents:', err);
        systemBanner.textContent = `Failed to load documents from ${API_BASE}. Check the browser console and Docker logs.`;
        systemBanner.className = 'system-banner error';
    }
}

async function deleteDocument(id) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        const res = await fetch(`${API_BASE}/documents/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });

        if (!res.ok) throw new Error('Delete failed');
        fetchDocuments();
    } catch (err) {
        alert(err.message);
    }
}

function renderDocuments(docs) {
    docsList.innerHTML = '';
    
    if (docs.length === 0) {
        docsList.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 20px 0; font-size: 0.875rem;">No documents uploaded yet.</div>';
        return;
    }

    docs.forEach(doc => {
        const isReady = doc.status === 'ready';
        const docEl = document.createElement('div');
        docEl.className = 'doc-item glass-panel';
        docEl.innerHTML = `
            <div class="doc-info">
                <span class="doc-name" title="${doc.filename}">${doc.filename}</span>
                <span class="doc-status">
                    <span class="status-badge ${isReady ? 'status-ready' : 'status-processing'}"></span>
                    ${isReady ? 'Ready' : 'Processing...'}
                </span>
            </div>
            <button class="btn-icon" onclick="deleteDocument('${doc.document_id}')" title="Delete">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            </button>
        `;
        docsList.appendChild(docEl);
    });
}

// Search
async function handleSearch(e) {
    e.preventDefault();
    const query = document.getElementById('search-query').value.trim();
    if (!query) return;

    const searchBtn = document.getElementById('search-btn');
    searchBtn.disabled = true;
    searchBtn.textContent = 'Searching...';

    try {
        const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`, {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });

        if (res.status === 401) {
            logout();
            return;
        }

        const payload = await res.json();
        renderResults(payload.results || []);
    } catch (err) {
        searchResults.innerHTML = `<div class="error-message">Search failed: ${err.message}</div>`;
    } finally {
        searchBtn.disabled = false;
        searchBtn.textContent = 'Search';
    }
}

function renderResults(results) {
    if (!results || results.length === 0) {
        searchResults.innerHTML = `
            <div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                    <circle cx="11" cy="11" r="8"></circle>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                <p>No results found for your query.</p>
            </div>
        `;
        return;
    }

    searchResults.innerHTML = results.map(r => `
        <div class="result-card glass-panel">
            <div class="result-meta">
                <span class="result-filename">
                    <svg style="vertical-align: middle; margin-right: 4px;" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                    ${r.filename}
                </span>
                <span class="result-score">Score: ${r.score.toFixed(3)}</span>
            </div>
            <p class="result-text">${r.chunk_text}</p>
        </div>
    `).join('');
}

// Start app
init();
