import re
import html
import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/watch\?.*v=)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'  # Direct video ID
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def get_video_metadata(video_id: str) -> dict:
    """Fetch video title, channel name, and duration from YouTube page metadata."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    data = {
        "title": video_id,
        "channel": "Unknown Channel",
        "duration": "Unknown",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                # Find <title> tag
                title_match = re.search(r'<title>(.*?)</title>', response.text)
                if title_match:
                    title = title_match.group(1)
                    # Unescape HTML entities
                    title = html.unescape(title)
                    data["title"] = title.replace(" - YouTube", "").strip()
                
                # Find Channel name
                channel_match = re.search(r'"ownerChannelName":"(.*?)"', response.text)
                if channel_match:
                    data["channel"] = html.unescape(channel_match.group(1))
                else:
                    meta_match = re.search(r'<link itemprop="name" content="(.*?)">', response.text)
                    if meta_match:
                        data["channel"] = meta_match.group(1)
                
                # Find duration (in ISO 8601 format like PT10M30S)
                duration_match = re.search(r'"lengthSeconds":"(\d+)"', response.text)
                if duration_match:
                    seconds = int(duration_match.group(1))
                    h = seconds // 3600
                    m = (seconds % 3600) // 60
                    s = seconds % 60
                    if h > 0:
                        data["duration"] = f"{h}:{m:02d}:{s:02d}"
                    else:
                        data["duration"] = f"{m}:{s:02d}"
    except Exception:
        pass
    
    return data


async def get_transcript(video_id: str) -> str:
    """
    Fetch transcript text for a YouTube video.
    Works with youtube-transcript-api 1.x where segments are objects, not dicts.

    Returns:
        Transcript text string

    Raises:
        ValueError: If no transcript available
    """
    try:
        # Create instance
        api = YouTubeTranscriptApi()
        
        # 1. List transcripts
        transcript_list = api.list(video_id)

        # 2. Try to get English transcript first
        try:
            transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        except NoTranscriptFound:
            # Fall back to any available transcript
            transcripts = list(transcript_list)
            if not transcripts:
                raise ValueError("No transcript found for this video")
            transcript = transcripts[0]

        # 3. Fetch the data
        transcript_data = transcript.fetch()

        # 4. Join all text segments
        # Library v1.x returns 'FetchedTranscriptSnippet' objects with .text attribute
        segments = []
        for entry in transcript_data:
            if hasattr(entry, 'text'):
                segments.append(entry.text)
            elif isinstance(entry, dict) and 'text' in entry:
                segments.append(entry['text'])
            else:
                # Defensive fallback
                segments.append(str(entry))

        full_text = " ".join(segments)
        return full_text

    except TranscriptsDisabled:
        raise ValueError("Transcripts are disabled for this video")
    except NoTranscriptFound:
        raise ValueError("No transcript found for this video")
    except Exception as e:
        error_msg = str(e)
        if "No transcript found" in error_msg:
             raise ValueError("No transcript found for this video")
        raise ValueError(f"Failed to fetch transcript: {error_msg}")
