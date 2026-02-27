// Papertube Background Service Worker
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'summarizeBackground') {
        const { serverUrl, url, preset, token } = request;

        fetch(`${serverUrl}/api/summarize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ url, preset })
        })
            .then(response => {
                if (response.ok) return response.json();
                throw new Error(`Server returned ${response.status}`);
            })
            .then(data => sendResponse({ success: true, data }))
            .catch(err => sendResponse({ success: false, error: err.message }));

        return true; // Keep message channel open for async response
    }
});
