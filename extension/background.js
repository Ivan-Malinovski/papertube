// Papertube Background Service Worker
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'summarizeBackground') {
        const { serverUrl, url, preset, token } = request;

        // Send immediate response to acknowledge request started
        sendResponse({ started: true });

        // Use streaming endpoint
        const formData = new URLSearchParams();
        formData.append('url', url);
        formData.append('preset', preset);

        fetch(`${serverUrl}/summarize/stream`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
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
                        // Send completion message
                        chrome.runtime.sendMessage({
                            action: 'streamingComplete',
                            summaryId: summaryId
                        }).catch(() => {}); // Ignore errors if popup closed
                        return;
                    }

                    const chunk = decoder.decode(value, { stream: true });

                    if (isFirstChunk) {
                        // First chunk contains metadata JSON + summary text
                        const newlineIndex = chunk.indexOf('\n');
                        if (newlineIndex > 0) {
                            try {
                                const metadataJson = chunk.substring(0, newlineIndex);
                                const metadata = JSON.parse(metadataJson);
                                if (metadata.type === 'metadata') {
                                    chrome.runtime.sendMessage({
                                        action: 'streamingMetadata',
                                        metadata: {
                                            title: metadata.video_title,
                                            channel: metadata.channel_name,
                                            duration: metadata.duration,
                                            thumbnail: metadata.thumbnail_url
                                        }
                                    }).catch(() => {});

                                    // Send remaining text after metadata
                                    const remainingText = chunk.substring(newlineIndex + 1);
                                    if (remainingText) {
                                        chrome.runtime.sendMessage({
                                            action: 'streamingChunk',
                                            text: remainingText
                                        }).catch(() => {});
                                    }
                                }
                            } catch (e) {
                                // Not JSON, treat as regular text
                                chrome.runtime.sendMessage({
                                    action: 'streamingChunk',
                                    text: chunk
                                }).catch(() => {});
                            }
                        }
                        isFirstChunk = false;
                    } else {
                        // Check for final ID marker
                        const idMatch = chunk.match(/\n\[ID:(\d+)\]$/);
                        if (idMatch) {
                            summaryId = idMatch[1];
                            const textBeforeId = chunk.substring(0, idMatch.index);
                            if (textBeforeId) {
                                chrome.runtime.sendMessage({
                                    action: 'streamingChunk',
                                    text: textBeforeId
                                }).catch(() => {});
                            }
                        } else {
                            chrome.runtime.sendMessage({
                                action: 'streamingChunk',
                                text: chunk
                            }).catch(() => {});
                        }
                    }

                    return readChunk();
                });
            }

            return readChunk();
        })
        .catch(err => {
            chrome.runtime.sendMessage({
                action: 'streamingError',
                error: err.message
            }).catch(() => {});
        });

        return true; // Keep message channel open for async response
    }
});
