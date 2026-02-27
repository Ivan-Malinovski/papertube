import httpx
from typing import List, Dict, Any, Optional

DEFAULT_API_ENDPOINT = "https://nano-gpt.com/api/v1"
DEFAULT_MODEL = "meta-llama/llama-4-maverick"


async def summarize_transcript(
    transcript: str,
    prompt: str,
    api_token: str,
    model: str = DEFAULT_MODEL,
    api_endpoint: str = DEFAULT_API_ENDPOINT
) -> str:
    """
    Send transcript to LLM for summarization.

    Args:
        transcript: The video transcript text
        prompt: The prompt/instruction for summarization
        api_token: API authentication token
        model: Model identifier to use
        api_endpoint: API endpoint URL

    Returns:
        The generated summary text

    Raises:
        ValueError: If API call fails
    """
    # Truncate very long transcripts to fit within context limits
    # Assuming ~4 chars per token, 100k tokens ~ 400k chars
    max_chars = 350000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n\n[Transcript truncated due to length]"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Transcript text: {transcript}"}
    ]

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{api_endpoint.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0].get("message", {}).get("content")
                if content:
                    return content
                else:
                    raise ValueError("API returned an empty message content")
            else:
                raise ValueError(f"Invalid response format from API: {str(data)}")

    except Exception as e:
        raise ValueError(f"Failed to generate summary: {str(e)}")


async def stream_summarize_transcript(
    transcript: str,
    prompt: str,
    api_token: str,
    model: str = DEFAULT_MODEL,
    api_endpoint: str = DEFAULT_API_ENDPOINT
):
    """
    Stream transcript to LLM for summarization.
    """
    max_chars = 350000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n\n[Transcript truncated due to length]"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Transcript text: {transcript}"}
    ]

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
        "stream": True
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{api_endpoint.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise ValueError(f"API error: {response.status_code} - {error_text.decode()}")

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            import json
                            chunk = json.loads(data)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                content = chunk["choices"][0].get("delta", {}).get("content")
                                if content:
                                    yield content
                        except Exception as e:
                            print(f"Error parsing sync chunk: {e}")
                            continue

    except httpx.RequestError as e:
        raise ValueError(f"Connection error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Streaming failed: {str(e)}")


def truncate_transcript_for_display(transcript: str, max_length: int = 500) -> str:
    """Truncate transcript for display purposes."""
    if len(transcript) <= max_length:
        return transcript
    return transcript[:max_length].rstrip() + "..."
