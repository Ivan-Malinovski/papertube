# Papertube - Project Plan

## Overview
A self-hosted web application that summarizes YouTube videos using AI (Nano-GPT API). Users can input a YouTube URL via a web form or bookmarklet, and the app extracts the transcript, sends it to an LLM, and displays the summary. All history is saved to a local SQLite database.

## Tech Stack
- **Backend**: Python + FastAPI
- **Database**: SQLite (aiosqlite for async)
- **Frontend**: Vanilla HTML/CSS/JS (Jinja2 templates)
- **Transcription**: youtube-transcript-api
- **HTTP Client**: httpx (async)
- **Container**: Docker + Docker Compose

## File Structure
```
Papertube/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, routes
│   ├── database.py          # SQLite operations, settings
│   ├── transcription.py     # YouTube transcript extraction
│   ├── llm.py               # Nano-GPT API client
│   ├── templates/
│   │   ├── base.html        # Base template with dark mode
│   │   ├── index.html       # Main page (form + results)
│   │   ├── history.html     # Searchable history list
│   │   ├── summary.html     # Single summary view
│   │   └── settings.html    # Configuration page
│   └── static/
│       ├── style.css        # Styles with dark mode support
│       └── bookmarklet.js   # Bookmarklet code
├── data/                    # SQLite database (persistent)
├── extension/               # Browser extension
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── plan.md                  # This file
```

## Features

### Core Functionality
1. **Transcript Extraction**: Extract YouTube transcripts using youtube-transcript-api
   - Try English first (en, en-US, en-GB)
   - Fall back to any available language
   - Show clear error if no captions available

2. **AI Summarization**: Send transcript to Nano-GPT API
   - Endpoint: https://nano-gpt.com/api/v1
   - Default model: meta-llama/llama-4-maverick
   - Support for custom API token and endpoint

3. **Prompt Presets**:
   - Brief: 2-3 sentence summary
   - Detailed: Comprehensive summary with main points
   - Key Points: Bullet list of key points
   - Chapters: Breakdown with logical sections

### History & Persistence
- SQLite database stores all summaries
- Searchable history (by title or summary content)
- View individual summaries with full details
- Delete summaries from history

### Settings
- API endpoint URL
- API token
- Default model
- Dark mode toggle
- Custom prompt presets (editable)

### Bookmarklet
- JavaScript snippet to open summarizer with pre-filled URL
- Instructions for installation

## Database Schema

### summaries table
- id (PRIMARY KEY)
- video_id (TEXT)
- video_title (TEXT)
- video_url (TEXT)
- transcript (TEXT)
- summary (TEXT)
- prompt_preset (TEXT)
- model (TEXT)
- api_endpoint (TEXT)
- created_at (TIMESTAMP)

### settings table
- key (TEXT PRIMARY KEY)
- value (TEXT)

## API Endpoints

- `GET /` - Main page (form + latest summaries)
- `POST /summarize` - Create new summary
- `GET /history` - History page
- `GET /api/history` - List summaries (JSON, with search)
- `GET /summary/{id}` - View single summary
- `DELETE /api/summary/{id}` - Delete summary
- `GET /settings` - Settings page
- `POST /api/settings` - Update settings
- `GET /api/settings` - Get settings (JSON)
- `GET /bookmarklet` - Bookmarklet instructions

## Environment/Configuration
- Database path: `data/summaries.db`
- Default settings loaded on first run
- All settings configurable via web UI

## Docker Setup
- Python 3.11 slim image
- Port 8000 exposed
- Volume mounted for data persistence
- Uvicorn with auto-reload for development

## Error Handling
- Invalid YouTube URLs
- Videos with no captions/transcripts disabled
- API errors (connection, authentication, rate limits)
- Clear user-facing error messages
