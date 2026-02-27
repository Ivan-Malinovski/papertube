document.addEventListener('DOMContentLoaded', async () => {
    const serverUrlInput = document.getElementById('serverUrl');
    const status = document.getElementById('status');
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
    const mainView = document.getElementById('main-view');
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginStatus = document.getElementById('login-status');
    const loggedInAs = document.getElementById('logged-in-as');
    const mainActionView = document.getElementById('action-view');

    // Load saved settings
    const settings = await chrome.storage.local.get(['serverUrl', 'lastPreset', 'auth_token', 'username']);
    const defaultServerUrl = '__SERVER_URL__';
    serverUrlInput.value = settings.serverUrl || defaultServerUrl;

    if (settings.lastPreset) {
        presetSelect.value = settings.lastPreset;
    }

    // Get current server URL from input
    function getServerUrl() {
        return serverUrlInput.value.trim() || defaultServerUrl;
    }

    // Login function
    async function doLogin() {
        const url = getServerUrl();
        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        if (!username || !password) {
            loginStatus.textContent = "Please enter username and password";
            loginStatus.className = "status error";
            return;
        }

        loginBtn.disabled = true;
        loginBtn.textContent = "Signing in...";
        loginStatus.textContent = "Connecting...";
        loginStatus.className = "status";

        try {
            const resp = await fetch(`${url}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (resp.ok) {
                const data = await resp.json();
                await chrome.storage.local.set({ 
                    auth_token: data.access_token, 
                    username: data.username,
                    serverUrl: url 
                });
                loginStatus.textContent = "Success!";
                loginStatus.className = "status success";
                setTimeout(() => showMainView(data.username), 500);
            } else {
                loginStatus.textContent = "Invalid credentials";
                loginStatus.className = "status error";
                loginBtn.disabled = false;
                loginBtn.textContent = "Sign In";
            }
        } catch (e) {
            loginStatus.textContent = "Cannot connect to server";
            loginStatus.className = "status error";
            loginBtn.disabled = false;
            loginBtn.textContent = "Sign In";
        }
    }

    // Login button click
    loginBtn.addEventListener('click', doLogin);

    // Enter key to login - on any of the 3 fields
    [serverUrlInput, usernameInput, passwordInput].forEach((input, index) => {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (index < 2) {
                    // Move to next field
                    [serverUrlInput, usernameInput, passwordInput][index + 1].focus();
                } else {
                    // Last field - submit login
                    doLogin();
                }
            }
        });
    });

    // Logout function
    logoutBtn.addEventListener('click', async () => {
        await chrome.storage.local.remove(['auth_token', 'username']);
        loginView.classList.remove('hidden');
        mainView.classList.add('hidden');
        usernameInput.value = '';
        passwordInput.value = '';
        loginStatus.textContent = '';
    });

    openAppBtn.onclick = (e) => {
        e.preventDefault();
        window.open(getServerUrl(), '_blank');
    };

    function showMainView(username) {
        loginView.classList.add('hidden');
        mainView.classList.remove('hidden');
        loggedInAs.textContent = `Logged in as ${username}`;
        initMainView();
    }

    async function initMainView() {
        const data = await chrome.storage.local.get(['auth_token']);
        if (!data.auth_token) {
            loginView.classList.remove('hidden');
            mainView.classList.add('hidden');
            return;
        }

        const url = getServerUrl();

        // 1. Fetch presets
        try {
            const resp = await fetch(`${url}/api/presets`, {
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
                await chrome.storage.local.remove(['auth_token', 'username']);
                loginView.classList.remove('hidden');
                mainView.classList.add('hidden');
                return;
            }
        } catch (e) { 
            console.error('Failed to fetch presets', e); 
            loginStatus.textContent = "Connection lost";
            loginView.classList.remove('hidden');
            mainView.classList.add('hidden');
            return;
        }

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

    async function checkSummary(urlToCheck, token) {
        const url = getServerUrl();
        try {
            const resp = await fetch(`${url}/api/summary/check?url=${encodeURIComponent(url)}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.exists) {
                    videoTitle.textContent = data.title;
                    videoChannel.textContent = data.channel;
                    if (typeof marked !== 'undefined') {
                        summaryText.innerHTML = marked.parse(data.summary);
                    } else {
                        summaryText.textContent = data.summary;
                    }
                    viewFullBtn.href = `${url}/summary/${data.id}`;
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
        const url = getServerUrl();
        
        chrome.storage.local.set({ lastPreset: preset });

        const defaultContent = document.getElementById('btn-default-content');
        const loadingContent = document.getElementById('btn-loading-content');
        const statusContainer = document.getElementById('status-container');

        summarizeBtn.disabled = true;
        defaultContent.style.display = 'none';
        loadingContent.style.display = 'flex';
        loadingContent.classList.remove('hidden');

        const steps = [
            "Loading video metadata...",
            "Extracting transcript...",
            "Summarizing..."
        ];
        let currentStep = 0;
        let stageInterval = null;
        let typingInterval = null;

        const updateStage = () => {
            if (currentStep < steps.length) {
                statusContainer.innerHTML = `<span class="status-anim-text active">${steps[currentStep]}</span>`;
                currentStep++;
            }
        };

        updateStage();
        stageInterval = setInterval(() => {
            if (currentStep < steps.length) {
                updateStage();
            } else {
                clearInterval(stageInterval);
            }
        }, 2500);

        const textBuffer = { current: "" };
        const displayBuffer = { current: "" };
        let isStreamingDone = false;
        let currentSummaryId = null;

        videoTitle.textContent = "Processing video...";
        videoChannel.textContent = "";
        summaryText.innerHTML = '<div class="streaming-status"><div class="dot"></div> Generating summary...</div><div class="summary-placeholder"></div><span class="typing-line"></span>';
        const summaryPlaceholder = summaryText.querySelector('.summary-placeholder');
        viewFullBtn.classList.add('hidden');

        const updateTyping = () => {
            if (textBuffer.current.length > 0) {
                let charsToTake;
                if (textBuffer.current.length > 50) charsToTake = 20;
                else if (textBuffer.current.length > 20) charsToTake = 10;
                else charsToTake = 3;

                const chunk = textBuffer.current.substring(0, charsToTake);
                textBuffer.current = textBuffer.current.substring(charsToTake);
                displayBuffer.current += chunk;

                if (typeof marked !== 'undefined') {
                    summaryPlaceholder.innerHTML = marked.parse(displayBuffer.current);
                } else {
                    summaryPlaceholder.textContent = displayBuffer.current;
                }
            } else if (isStreamingDone) {
                clearInterval(typingInterval);
                onStreamingComplete(currentSummaryId);
            }
        };

        function onStreamingComplete(summaryId) {
            if (summaryId) {
                currentSummaryId = summaryId;
                viewFullBtn.href = `${url}/summary/${summaryId}`;
                viewFullBtn.classList.remove('hidden');
            }

            const typingLine = summaryText.querySelector('.typing-line');
            if (typingLine) typingLine.remove();

            const streamHeader = summaryText.querySelector('.streaming-status');
            if (streamHeader) {
                streamHeader.innerHTML = '<span style="color: #10b981;">✓ Summary Complete</span>';
            }

            clearInterval(stageInterval);
            statusContainer.innerHTML = '<span class="status-anim-text active">Done!</span>';
            setTimeout(() => {
                summarizeBtn.disabled = false;
                defaultContent.textContent = "Summarize Again";
                defaultContent.style.display = 'inline';
                loadingContent.style.display = 'none';
                loadingContent.classList.add('hidden');
            }, 1500);
        }

        typingInterval = setInterval(updateTyping, 50);

        const formData = new URLSearchParams();
        formData.append('url', currentTab.url);
        formData.append('preset', preset);

        fetch(`${url}/summarize/stream`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${data.auth_token}`
            },
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || `Server returned ${response.status}`); });
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let isFirstChunk = true;
            let summaryId = null;

            function readChunk() {
                return reader.read().then(({ done, value }) => {
                    if (done) {
                        isStreamingDone = true;
                        currentSummaryId = summaryId;
                        return;
                    }

                    const chunk = decoder.decode(value, { stream: true });

                    if (isFirstChunk) {
                        const newlineIndex = chunk.indexOf('\n');
                        if (newlineIndex > 0) {
                            try {
                                const metadataJson = chunk.substring(0, newlineIndex);
                                const metadata = JSON.parse(metadataJson);
                                if (metadata.type === 'metadata') {
                                    clearInterval(stageInterval);
                                    statusContainer.innerHTML = '<span class="status-anim-text active">Summarizing...</span>';

                                    videoTitle.textContent = metadata.video_title || "Loading...";
                                    videoChannel.textContent = metadata.channel_name || "";

                                    const remainingText = chunk.substring(newlineIndex + 1);
                                    if (remainingText) {
                                        textBuffer.current += remainingText;
                                    }
                                }
                            } catch (e) {
                                textBuffer.current += chunk;
                            }
                        }
                        isFirstChunk = false;
                    } else {
                        const idMatch = chunk.match(/\n\[ID:(\d+)\]$/);
                        if (idMatch) {
                            summaryId = idMatch[1];
                            const textBeforeId = chunk.substring(0, idMatch.index);
                            if (textBeforeId) {
                                textBuffer.current += textBeforeId;
                            }
                        } else {
                            textBuffer.current += chunk;
                        }
                    }

                    return readChunk();
                });
            }

            return readChunk();
        })
        .catch(err => {
            clearInterval(stageInterval);
            clearInterval(typingInterval);
            status.textContent = err.message;
            status.className = "status error";
            summarizeBtn.disabled = false;
            defaultContent.textContent = "Summarize Now";
            defaultContent.style.display = 'inline';
            loadingContent.style.display = 'none';
            loadingContent.classList.add('hidden');
        });
    };

    viewFullBtn.onclick = (e) => {
        e.preventDefault();
        window.open(viewFullBtn.href, '_blank');
    };

    // Check if already logged in
    if (settings.auth_token) {
        showMainView(settings.username);
    }
});
