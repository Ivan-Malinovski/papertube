// Papertube Content Script
console.log('Papertube Extension: Content script starting...');

// Function to find the button container on YouTube
function findTargetContainer() {
    const selectors = [
        '#top-level-buttons-computed',
        '#actions-inner #top-level-buttons-computed',
        '#actions #top-level-buttons-computed',
        'ytd-menu-renderer #top-level-buttons-computed',
        'ytd-watch-metadata #actions'
    ];

    for (const selector of selectors) {
        const element = document.querySelector(selector);
        if (element) return element;
    }
    return null;
}

function injectButton() {
    if (document.getElementById('papertube-button')) return;

    const target = findTargetContainer();
    if (!target) return;

    const summarizeBtn = document.createElement('button');
    summarizeBtn.id = 'papertube-button';
    summarizeBtn.className = 'yt-spec-button-shape-next yt-spec-button-shape-next--outline yt-spec-button-shape-next--mono yt-spec-button-shape-next--size-m';
    summarizeBtn.style.margin = '0 8px';
    summarizeBtn.style.display = 'inline-flex';
    summarizeBtn.style.alignItems = 'center';
    summarizeBtn.style.gap = '6px';
    summarizeBtn.style.padding = '0 15px';
    summarizeBtn.style.borderRadius = '18px';
    summarizeBtn.style.border = '1px solid transparent';
    summarizeBtn.style.backgroundColor = '#f2f2f2'; /* Light grey like YouTube pills */
    summarizeBtn.style.color = '#0f0f0f'; /* Dark text */
    summarizeBtn.style.cursor = 'pointer';
    summarizeBtn.style.fontWeight = '500';
    summarizeBtn.style.height = '36px';
    summarizeBtn.title = "Send to Papertube";

    summarizeBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="18" height="18" fill="#ff0000" style="margin-right: 2px;"> <!-- Red check icon -->
            <path d="M21 7L9 19L3.5 13.5L4.91 12.09L9 16.17L19.59 5.59L21 7Z"/>
        </svg>
        <span style="color: #0f0f0f;">Summarize</span>
    `;

    summarizeBtn.onclick = async () => {
        const videoUrl = window.location.href;
        const result = await chrome.storage.local.get(['serverUrl', 'lastPreset', 'auth_token']);
        const serverUrl = result.serverUrl || 'http://localhost:8000';
        const preset = result.lastPreset || 'detailed';
        const token = result.auth_token;

        if (!token) {
            alert('Please login to Papertube extension first.');
            return;
        }

        const originalHtml = summarizeBtn.innerHTML;
        summarizeBtn.innerHTML = '<span>Sending...</span>';
        summarizeBtn.disabled = true;

        // Use background script to avoid CSP issues
        chrome.runtime.sendMessage({
            action: 'summarizeBackground',
            serverUrl,
            url: videoUrl,
            preset: preset,
            token: token
        }, (response) => {
            if (response && response.started) {
                summarizeBtn.innerHTML = '<span style="color: #10b981;">Sent!</span>';
                setTimeout(() => {
                    summarizeBtn.innerHTML = originalHtml;
                    summarizeBtn.disabled = false;
                }, 2000);
            } else {
                console.warn('Background send failed, falling back to tab:', response?.error);
                window.open(`${serverUrl}/?url=${encodeURIComponent(videoUrl)}&auto=1`, '_blank');
                summarizeBtn.innerHTML = originalHtml;
                summarizeBtn.disabled = false;
            }
        });
    };

    target.insertBefore(summarizeBtn, target.firstChild);
}

// Observe for page changes (YouTube navigation is dynamic)
let lastUrl = location.href;
const observer = new MutationObserver(() => {
    const url = location.href;
    if (url !== lastUrl) {
        lastUrl = url;
    }
    if (url.includes('watch?v=')) {
        injectButton();
    }
});

observer.observe(document.body, { childList: true, subtree: true });

// Initial check
if (location.href.includes('watch?v=')) {
    injectButton();
}
