document.addEventListener('DOMContentLoaded', async () => {
    const serverUrlInput = document.getElementById('serverUrl');
    const saveSettingsBtn = document.getElementById('save-settings');
    const status = document.getElementById('status');
    const toggleSettingsBtn = document.getElementById('toggle-settings');
    const settingsView = document.getElementById('settings-view');
    const openAppBtn = document.getElementById('open-app');
    const summarizeBtn = document.getElementById('summarize-now');
    const presetSelect = document.getElementById('preset-select');
    const summaryText = document.getElementById('summary-text');
    const videoTitle = document.getElementById('current-title');
    const videoChannel = document.getElementById('current-channel');
    const summaryView = document.getElementById('summary-view');
    const viewFullBtn = document.getElementById('view-full');

    // Login elements
    const loginView = document.getElementById('login-view');
    const loginBtn = document.getElementById('login-btn');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginStatus = document.getElementById('login-status');
    const mainActionView = document.getElementById('action-view');

    // Load current settings
    const settings = await chrome.storage.local.get(['serverUrl', 'lastPreset', 'auth_token']);
    const serverUrl = settings.serverUrl || 'http://localhost:8000';
    serverUrlInput.value = serverUrl;

    if (settings.lastPreset) {
        presetSelect.value = settings.lastPreset;
    }

    // Toggle settings logic
    toggleSettingsBtn.onclick = () => {
        settingsView.classList.toggle('hidden');
    };

    // Save settings
    saveSettingsBtn.onclick = () => {
        const url = serverUrlInput.value.trim();
        chrome.storage.local.set({ serverUrl: url }, () => {
            status.textContent = 'Settings saved!';
            status.className = 'status success';
            setTimeout(() => { status.textContent = ''; }, 2000);
            init();
        });
    };

    // Login logic
    loginBtn.onclick = async () => {
        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        loginBtn.disabled = true;
        loginStatus.textContent = "Logging in...";

        try {
            const resp = await fetch(`${serverUrl}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (resp.ok) {
                const data = await resp.json();
                await chrome.storage.local.set({ auth_token: data.access_token, username: data.username });
                loginStatus.textContent = "Success!";
                loginStatus.className = "status success";
                setTimeout(() => init(), 500);
            } else {
                loginStatus.textContent = "Invalid username or password.";
                loginStatus.className = "status error";
                loginBtn.disabled = false;
            }
        } catch (e) {
            loginStatus.textContent = "Server connection failed.";
            loginStatus.className = "status error";
            loginBtn.disabled = false;
        }
    };

    openAppBtn.onclick = (e) => {
        e.preventDefault();
        window.open(serverUrl, '_blank');
    };

    async function init() {
        const data = await chrome.storage.local.get(['auth_token']);
        if (!data.auth_token) {
            loginView.classList.remove('hidden');
            summaryView.classList.add('hidden');
            mainActionView.classList.add('hidden');
            return;
        }

        loginView.classList.add('hidden');
        mainActionView.classList.remove('hidden');

        // 1. Fetch presets
        try {
            const resp = await fetch(`${serverUrl}/api/presets`, {
                headers: { 'Authorization': `Bearer ${data.auth_token}` }
            });
            if (resp.ok) {
                const presets = await resp.json();
                presetSelect.innerHTML = '';
                for (const [key, label] of Object.entries(presets)) {
                    const opt = document.createElement('option');
                    opt.value = key;
                    opt.textContent = key.charAt(0).toUpperCase() + key.slice(1);
                    presetSelect.appendChild(opt);
                }
                const settings = await chrome.storage.local.get(['lastPreset']);
                if (settings.lastPreset) presetSelect.value = settings.lastPreset;
            } else if (resp.status === 401) {
                // Token expired
                chrome.storage.local.remove('auth_token');
                init();
                return;
            }
        } catch (e) { console.error('Failed to fetch presets', e); }

        // 2. Get current tab info
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        const currentTab = tabs[0];

        if (currentTab && (currentTab.url.includes('youtube.com/watch') || currentTab.url.includes('youtu.be/'))) {
            summaryView.classList.remove('hidden');
            checkSummary(currentTab.url, data.auth_token);
        } else {
            videoTitle.textContent = "Not a YouTube video page";
            summaryView.classList.remove('hidden');
            summarizeBtn.disabled = true;
        }
    }

    async function checkSummary(url, token) {
        try {
            const resp = await fetch(`${serverUrl}/api/summary/check?url=${encodeURIComponent(url)}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.exists) {
                    videoTitle.textContent = data.title;
                    videoChannel.textContent = data.channel;
                    // Render markdown if marked is available
                    if (typeof marked !== 'undefined') {
                        summaryText.innerHTML = marked.parse(data.summary);
                    } else {
                        summaryText.textContent = data.summary;
                    }
                    viewFullBtn.href = `${serverUrl}/summary/${data.id}`;
                    viewFullBtn.classList.remove('hidden');
                    summarizeBtn.textContent = "Summarize Again";
                } else {
                    videoTitle.textContent = "Ready to summarize";
                    summaryText.textContent = "Click the button below to generate a summary for this video.";
                }
            }
        } catch (e) {
            console.error('Check summary failed', e);
            summaryText.textContent = "Could not connect to Papertube server.";
        }
    }

    summarizeBtn.onclick = async () => {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        const currentTab = tabs[0];
        if (!currentTab) return;

        const data = await chrome.storage.local.get(['auth_token']);
        const preset = presetSelect.value;
        chrome.storage.local.set({ lastPreset: preset });

        summarizeBtn.disabled = true;
        summarizeBtn.textContent = "Processing...";
        status.textContent = "Sending to server...";
        status.className = "status";

        chrome.runtime.sendMessage({
            action: 'summarizeBackground',
            serverUrl,
            url: currentTab.url,
            preset: preset,
            token: data.auth_token
        }, (response) => {
            if (response && response.success) {
                status.textContent = "Summarized successfully!";
                status.className = "status success";
                summarizeBtn.textContent = "Summarize Again";
                summarizeBtn.disabled = false;
                checkSummary(currentTab.url, data.auth_token);
            } else {
                status.textContent = "Failed. Opening in tab...";
                status.className = "status error";
                window.open(`${serverUrl}/?url=${encodeURIComponent(currentTab.url)}&auto=1`, '_blank');
                summarizeBtn.disabled = false;
                summarizeBtn.textContent = "Summarize Now";
            }
        });
    };

    viewFullBtn.onclick = (e) => {
        e.preventDefault();
        window.open(viewFullBtn.href, '_blank');
    };

    init();
});
