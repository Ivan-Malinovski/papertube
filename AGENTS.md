# AGENTS.md - Papertube Development Guide

This file provides guidance for AI agents working on the Papertube codebase.

## Project Overview

Papertube is a self-hosted YouTube video summarizer using:
- **Backend**: Python + FastAPI
- **Database**: SQLite (aiosqlite)
- **Frontend**: Vanilla HTML/CSS/JS with Jinja2 templates
- **AI**: OpenAI-compatible API
- **Extension**: Browser extension (Chrome/Firefox)

## Build & Run Commands

### Python Backend

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload)
uvicorn app.main:app --reload

# Run on custom host/port
uvicorn app.main:app --host 0.0.0.0 --port 8080

# Run with Docker
docker compose up -d --build
```

### Testing

**No formal test framework is currently set up.** To run a single test manually:

```bash
# Create and run a simple test script
python -c "
import asyncio
from app.database import init_db, save_summary, get_summaries

async def test():
    await init_db()
    print('DB initialized')
    # Add your test logic here

asyncio.run(test())
"
```

### Linting

No automatic linting is configured. Run manually:

```bash
# Python syntax check
python -m py_compile app/main.py

# Check imports
python -c "from app.main import app; print('Imports OK')"

# JavaScript - use browser console or eslint
# No automated JS linting configured
```

## Code Style Guidelines

### Python

**Imports:**
- Use relative imports within the app package: `from .module import ...`
- Group imports: stdlib -> third-party -> local
- Use `import typing` for type hints, or `from typing import ...`

**Types:**
- Use type hints for function parameters and return types
- Common: `str`, `int`, `bool`, `Optional[X]`, `List[X]`, `Dict[K, V]`, `Any`
- Use `| None` syntax for simple optional types (Python 3.10+)

**Naming:**
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private functions: prefix with `_`

**Formatting:**
- Maximum line length: ~120 characters (soft)
- Use f-strings for string formatting: `f"Value: {value}"`
- Add trailing commas in multi-line constructs

**Functions:**
- Keep functions focused and small
- Use docstrings for complex functions (Google style)
- Use async/await for all database and I/O operations

**Error Handling:**
- Use `try/except` for operations that may fail
- Return `JSONResponse(status_code=..., content={"error": ...})` for API errors
- Print errors to console: `print(f"Error: {e}")`
- Use custom exceptions for domain-specific errors

**Database:**
- Always use `async with aiosqlite.connect()` for context management
- Set `db.row_factory = aiosqlite.Row` when converting to dicts
- Use parameterized queries: `await db.execute("SELECT * FROM table WHERE id = ?", (id,))`

### JavaScript (Extension)

**General:**
- Vanilla JavaScript (no frameworks)
- Use `const` and `let`, avoid `var`
- Use arrow functions for callbacks
- Use template literals: `` `Value: ${value}` ``

**Naming:**
- Variables/functions: `camelCase`
- Constants: `UPPER_SNAKE_CASE`
- DOM element IDs: `kebab-case` (HTML), access via `getElementById`

**DOM Manipulation:**
- Wait for `DOMContentLoaded` before accessing elements
- Cache DOM references at load time
- Use event delegation for dynamic elements

**Extension-Specific:**
- Use `chrome.storage.local` for persistent storage
- Direct fetch from popup.js (not background.js) for reliability
- Handle CORS via extension permissions

### HTML/CSS

**HTML:**
- Use semantic elements: `<header>`, `<main>`, `<section>`, `<nav>`
- Keep templates in `app/templates/`

**CSS:**
- Classes: `kebab-case`
- Use CSS custom properties for theming: `var(--color-primary)`
- Prefer flexbox/grid over floats
- Keep styles in `app/static/` or inline in templates

## Important Patterns

### Streaming Response (Server)
```python
async def endpoint():
    async def generator():
        yield "data chunk\n"
    return StreamingResponse(generator(), media_type="text/plain")
```

### Streaming Response (Extension Client)
```javascript
const reader = response.body.getReader();
while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = new TextDecoder().decode(value);
    // Process chunks
}
```

### Rate Limiting Decorator
```python
@rate_limit(max_requests=10, window_seconds=60)
async def endpoint(user = Depends(require_user)):
    ...
```

### Auth Check
```python
async def endpoint(user = Depends(require_user)):
    # user is guaranteed non-null after this
```

### Video ID Extraction
```python
from app.transcription import extract_video_id
video_id = extract_video_id(youtube_url)
```

## Database Schema

- **users**: id, username, password_hash, full_name, is_admin, created_at
- **summaries**: id, user_id, video_id, video_title, video_url, channel_name, duration, thumbnail_url, transcript, summary, prompt_preset, model, api_endpoint, created_at, is_read
- **settings**: key, value
- **video_cache**: video_id, title, channel, duration, thumbnail_url, transcript, cached_at

## Key Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/summarize/stream` | Required | Stream summary generation |
| GET | `/history` | Required | List user summaries |
| GET | `/summary/{id}` | Required | View single summary |
| POST | `/api/login` | No | Extension API login |
| GET | `/api/ping` | No | Server connectivity test |
| POST | `/api/summarize` | Required | Background summarization |

## Common Tasks

### Adding a new API endpoint
1. Add route in `app/main.py`
2. Add `@rate_limit` decorator if needed
3. Add `user = Depends(require_user)` parameter
4. Return JSONResponse or StreamingResponse

### Adding a new database query
1. Add function in `app/database.py`
2. Use `async with aiosqlite.connect()` context
3. Set row_factory for dict conversion
4. Return typed results

### Modifying the extension
1. Edit files in `extension/` (Chrome) or `extension-firefox/` (Firefox)
2. Sync changes between both directories
3. Test by loading unpacked extension

## Known Issues & Tips

- Extension streaming: First chunk is JSON metadata + "\n", final chunk ends with "\n[ID:123]"
- Button animation bug: Set inline styles BEFORE removing `.hidden` class
- Extension-to-server: Use direct fetch from popup.js (not background.js)
- Server URL injection: Replace `__SERVER_URL__` placeholder in popup.js at download time
