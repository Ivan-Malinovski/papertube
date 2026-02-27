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

The project uses pytest with pytest-asyncio and pytest-xdist for parallel execution.

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Run in parallel (requires pytest-xdist)
pytest tests/ -n auto

# Run specific test file
pytest tests/test_auth.py -v

# Run specific test
pytest tests/test_auth.py::TestPasswordHashing::test_hash_password -v
```

**Test Structure:**
- `tests/conftest.py` - Fixtures for test isolation, temp DB, state reset
- `tests/test_auth.py` - Authentication (JWT, password hashing, login rate limiting)
- `tests/test_database.py` - Database operations
- `tests/test_validation.py` - Input validation (Pydantic schemas, validators)
- `tests/test_config.py` - Configuration tests
- `tests/test_api_token.py` - API token validation
- `tests/test_ratelimit.py` - Rate limiting
- `tests/test_transcription.py` - YouTube URL validation, video ID extraction
- `tests/test_llm.py` - LLM integration
- `tests/test_api_endpoints.py` - API endpoint tests

**Test Isolation:**
- Each test gets a unique temporary database via `temp_db_path` fixture
- Global state (rate limits, login attempts) is reset via `reset_app_state` autouse fixture
- Tests can run in parallel with pytest-xdist

**Adding Tests:**
1. Add test class to appropriate file in `tests/`
2. Use existing fixtures: `app_client`, `initialized_db`, `db_with_user`, `temp_db_path`
3. Use `@pytest.mark.asyncio` for async tests
4. Use `@pytest.mark.parametrize` for parameterized tests

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
- Use the connection pool in `app/db_manager.py` for all database operations
- Get pool connection: `pool = await get_db_pool(str(DB_PATH))`
- Use context manager: `async with pool.get_connection() as db:`
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

The rate limiter is in `app/ratelimit.py`:
- Uses in-memory storage (`_request_log`)
- Cleans up old entries automatically every 100 requests
- Returns 429 with `Retry-After` header when exceeded
- Call `cleanup_rate_limits()` manually for forced cleanup

### Login Rate Limiting
Login rate limiting is in `app/main.py`:
- IP-based limiting before authentication
- Uses `LOGIN_ATTEMPTS` dict with automatic cleanup every 50 attempts
- Functions: `check_login_rate_limit()`, `record_failed_login()`

### Auth Check
```python
async def endpoint(user = Depends(require_user)):
    # user is guaranteed non-null after this
```

### Input Validation
Validation uses Pydantic models in `app/schemas.py`. Due to Pydantic v2 compatibility with FastAPI Form data, validation is done **manually inside endpoints**:

```python
from pydantic import ValidationError

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Manual validation
    try:
        form_data = LoginRequest(username=username, password=password)
    except ValidationError as e:
        errors = e.errors()
        error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]
        return JSONResponse(
            status_code=422,
            content={"error": "Validation failed", "details": error_messages}
        )
    
    # Continue with normal logic using form_data.username, form_data.password
```

Available schemas in `app/schemas.py`:
- `LoginRequest` - username (alphanumeric + underscore/hyphen, max 50), password
- `RegisterRequest` - username (3-32 chars), password (8-128 chars), full_name (max 100)
- `SummaryRequest` - url (YouTube URL validation), preset (brief/detailed/key_points/chapters)
- `ChatRequest` - id (positive int), message (1-10000 chars)
- `AdminUserCreate` - username, password, full_name, is_admin
- `SettingsUpdate` - key, value (with allowed keys validation)

Utility validators in `app/validators.py`:
- `sanitize_input(text, max_length)` - strips whitespace, removes null bytes
- `validate_youtube_url(url)` - validates YouTube URL format
- `validate_username(username)` - returns (bool, error_msg)
- `validate_password(password)` - returns (bool, error_msg)

### Video ID Extraction
```python
from app.transcription import extract_video_id
video_id = extract_video_id(youtube_url)
```

### API Token Validation
API token validation uses timing-safe comparison to prevent timing attacks. Import from `app/main.py`:

```python
from app.main import check_api_token_configured, validate_api_token_format

# Simple boolean check
if not check_api_token_configured(api_token):
    raise ValueError("API Token not configured")

# Detailed validation with error message
is_valid, error_msg = validate_api_token_format(api_token or "")
if not is_valid:
    return JSONResponse(status_code=400, content={"error": f"API Token not configured. {error_msg}"})
```

Validation includes:
- Timing-safe comparison using `secrets.compare_digest`
- Length check (10-500 characters)
- Rejects common placeholder patterns
- Character set validation (alphanumeric + `_-/.+=`)

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
2. Use `get_db_pool()` to get a connection from the pool
3. Use context manager: `async with pool.get_connection() as db:`
4. Set row_factory for dict conversion
5. Return typed results

### Modifying the extension
1. Edit files in `extension/` (Chrome) or `extension-firefox/` (Firefox)
2. Sync changes between both directories
3. Test by loading unpacked extension

## Configuration Management

Configuration is centralized in `app/config.py` using Pydantic Settings. All settings can be overridden via environment variables with the `PAPERTUBE_` prefix.

### Configuration Options

| Setting | Env Variable | Default | Description |
|---------|--------------|---------|-------------|
| host | PAPERTUBE_HOST | 0.0.0.0 | Server host |
| port | PAPERTUBE_PORT | 8080 | Server port |
| secret_key | PAPERTUBE_SECRET_KEY | (random) | JWT secret |
| algorithm | PAPERTUBE_ALGORITHM | HS256 | JWT algorithm |
| access_token_expire_minutes | PAPERTUBE_ACCESS_TOKEN_EXPIRE_MINUTES | 525600 | Token expiry (1 year) |
| login_max_attempts | PAPERTUBE_LOGIN_MAX_ATTEMPTS | 5 | Max login tries |
| login_lockout_window | PAPERTUBE_LOGIN_LOCKOUT_WINDOW | 900 | Lockout seconds (15 min) |
| api_rate_limit_max_requests | PAPERTUBE_API_RATE_LIMIT_MAX_REQUESTS | 10 | API rate limit |
| api_rate_limit_window_seconds | PAPERTUBE_API_RATE_LIMIT_WINDOW_SECONDS | 60 | Rate limit window |
| default_api_endpoint | PAPERTUBE_DEFAULT_API_ENDPOINT | (Google AI) | LLM endpoint |
| default_model | PAPERTUBE_DEFAULT_MODEL | gemini-2.0-flash | LLM model |
| database_path | PAPERTUBE_DATABASE_PATH | data/summaries.db | DB path |

### Using Config in Code

Import from `app/config.py`:

```python
# Get individual settings
from app.config import get_secret_key, get_login_max_attempts, get_default_model

# Access full settings object
from app.config import get_settings

settings = get_settings()
model = settings.default_model
```

### Adding New Settings

1. Add field to `Settings` class in `app/config.py`
2. Add helper function if needed
3. Update `.env.example` with the new variable
4. Update this documentation

## Known Issues & Tips

- Extension streaming: First chunk is JSON metadata + "\n", final chunk ends with "\n[ID:123]"
- Button animation bug: Set inline styles BEFORE removing `.hidden` class
- Extension-to-server: Use direct fetch from popup.js (not background.js)
- Server URL injection: Replace `__SERVER_URL__` placeholder in popup.js at download time
- Test client: `request.client` may be None in test environment - use fallback: `request.client.host if request.client else "127.0.0.1"`
- Schema vs validators: Pydantic schemas in `app/schemas.py` have lenient validation; strict validation uses `app/validators.py` functions
