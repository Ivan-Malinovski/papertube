from contextlib import asynccontextmanager
import json
import re
import secrets
from pathlib import Path
import time
from typing import Dict, Any, List, Optional, Union

from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.datastructures import Headers
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationError
from typing import Optional, Any
import zipfile
import io
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .transcription import extract_video_id, get_transcript, get_video_metadata
from .llm import summarize_transcript, stream_summarize_transcript
from .ratelimit import rate_limit
from .config import get_login_max_attempts, get_login_lockout_window
from .database import (
    DEFAULT_SETTINGS,
    init_db,
    save_summary,
    get_summaries,
    get_summary,
    delete_summary as db_delete_summary,
    get_settings,
    update_setting,
    mark_summary_read,
    get_adjacent_summaries,
    PROMPT_PRESETS,
    get_user_by_username,
    create_user,
    DB_PATH,
    get_user_count,
    get_users,
    delete_user as db_delete_user,
    update_user_role,
    update_user_profile,
    update_user_password
)
from .auth import (
    get_current_user,
    require_user,
    verify_password,
    get_password_hash,
    create_access_token
)
from .schemas import LoginRequest, RegisterRequest, SummaryRequest, ChatRequest, AdminUserCreate
from .db_manager import init_db_pool, get_db_pool, _db_pool
import aiosqlite

INVALID_TOKEN_PATTERNS = [
    "sk-your-api-token-here",
    "sk-placeholder",
    "your-api-key-here",
    "replace-me",
    "changeme",
    "demo-key",
    "test-key",
    "mock-key",
    "",
]

def check_api_token_configured(api_token: str | None) -> bool:
    """
    Check if the API token is properly configured.
    
    Uses timing-safe comparison to prevent timing attacks.
    Validates format and rejects common placeholder patterns.
    """
    if not api_token:
        return False
    
    token = str(api_token).strip()
    
    if not token:
        return False
    
    if len(token) < 10:
        return False
    
    if len(token) > 500:
        return False
    
    token_lower = token.lower()
    for pattern in INVALID_TOKEN_PATTERNS:
        if secrets.compare_digest(token_lower, pattern.lower()):
            return False
    
    if not re.match(r'^[a-zA-Z0-9_\-/.+=]+$', token):
        return False
    
    return True


def validate_api_token_format(api_token: str) -> tuple[bool, str]:
    """
    Validate API token format with detailed error message.
    
    Returns:
        (is_valid, error_message)
    """
    if not api_token:
        return False, "API token is required"
    
    token = str(api_token).strip()
    
    if not token:
        return False, "API token cannot be empty"
    
    if len(token) < 10:
        return False, "API token must be at least 10 characters"
    
    if len(token) > 500:
        return False, "API token is too long (max 500 characters)"
    
    token_lower = token.lower()
    placeholder_patterns = [
        "sk-your-api-token-here",
        "sk-placeholder", 
        "your-api-key-here",
        "replace-me",
        "changeme",
        "demo-key",
        "test-key",
    ]
    
    for pattern in placeholder_patterns:
        if secrets.compare_digest(token_lower, pattern.lower()):
            return False, f"Invalid placeholder token detected"
    
    if not re.match(r'^[a-zA-Z0-9_\-/.+=]+$', token):
        return False, "API token contains invalid characters"
    
    return True, ""


async def _prepare_summarize(url: str, preset: str) -> tuple[dict, str, str, str]:
    """
    Common logic for both summarize endpoints.
    
    Returns:
        tuple of (metadata, transcript, prompt, video_id)
    
    Raises:
        ValueError: If URL is invalid or API token not configured
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")
    
    settings = await get_settings()
    api_token = settings.get("api_token")
    api_endpoint = settings.get("api_endpoint")
    model = settings.get("default_model")
    presets = settings.get("prompt_presets", PROMPT_PRESETS)
    
    if not check_api_token_configured(api_token):
        raise ValueError("API Token not configured. Please set your API token in Settings before generating summaries.")
    
    prompt = presets.get(preset, presets.get("detailed", "Summarize this."))
    prompt = f"You are a helpful assistant that summarizes YouTube video transcripts. {prompt}"
    
    metadata = await get_video_metadata(video_id)
    transcript = await get_transcript(video_id)
    
    return metadata, transcript, prompt, video_id


async def _save_summary_to_db(
    user_id: int,
    video_id: str,
    metadata: dict,
    transcript: str,
    summary_text: str,
    preset: str,
    model: str,
    api_endpoint: str
) -> int:
    """Save summary to database and return the summary ID."""
    return await save_summary(
        user_id=user_id,
        video_id=video_id,
        video_title=metadata["title"],
        video_url=f"https://www.youtube.com/watch?v={video_id}",
        channel_name=metadata["channel"],
        duration=metadata["duration"],
        thumbnail_url=metadata["thumbnail"],
        transcript=transcript,
        summary=summary_text,
        prompt_preset=preset,
        model=model,
        api_endpoint=api_endpoint
    )

# Use lifespan to initialize the database
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_db_pool(str(DB_PATH))
    yield
    if _db_pool:
        await _db_pool.close_all()

app = FastAPI(
    title="Papertube",
    description="Summarize YouTube videos efficiently using AI.",
    version="1.0.0",
    lifespan=lifespan
)

# Secure CORS for Browser Extensions ONLY (No public web origins)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension|moz-extension)://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files setup
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Templates setup
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    errors = exc.errors()
    error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed",
            "details": error_messages
        }
    )

# --- Auth Routes ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None, success: Optional[str] = None):
    settings = await get_settings()
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "error": error, 
        "success": success,
        "settings": settings,
        "next": request.query_params.get("next")
    })

# Login rate limiting (IP-based, before authentication)
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
LOGIN_MAX_ATTEMPTS = get_login_max_attempts()
LOGIN_LOCKOUT_WINDOW = get_login_lockout_window()
LOGIN_CLEANUP_THRESHOLD = 3600  # 1 hour

def _cleanup_login_attempts():
    """Remove old IP entries from login attempts to prevent memory leak."""
    now = time.time()
    expired_ips = [
        ip for ip, attempts in LOGIN_ATTEMPTS.items()
        if not attempts or (now - max(attempts)) > LOGIN_CLEANUP_THRESHOLD
    ]
    for ip in expired_ips:
        del LOGIN_ATTEMPTS[ip]

def check_login_rate_limit(client_ip: str) -> tuple[bool, str]:
    """Check if IP is rate limited for login. Returns (is_allowed, error_message)."""
    # Periodic cleanup
    if len(LOGIN_ATTEMPTS) > 0 and sum(len(a) for a in LOGIN_ATTEMPTS.values()) % 50 == 0:
        _cleanup_login_attempts()
    
    now = time.time()
    attempts = LOGIN_ATTEMPTS.get(client_ip, [])
    # Clean old attempts outside the window (FIX: use <=)
    attempts = [t for t in attempts if now - t <= LOGIN_LOCKOUT_WINDOW]
    
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        # FIX: Use max(attempts) instead of min(attempts)
        latest_attempt = max(attempts)
        remaining = LOGIN_LOCKOUT_WINDOW - (now - latest_attempt)
        
        # Ensure we don't show negative or zero
        if remaining <= 0:
            LOGIN_ATTEMPTS[client_ip] = []
            return True, ""
        
        minutes = int(remaining / 60) + 1
        return False, f"Too many login attempts. Please try again in {minutes} minutes."
    
    # Update the attempts list
    LOGIN_ATTEMPTS[client_ip] = attempts
    return True, ""

def record_failed_login(client_ip: str):
    """Record a failed login attempt for rate limiting."""
    now = time.time()
    attempts = LOGIN_ATTEMPTS.get(client_ip, [])
    attempts = [t for t in attempts if now - t <= LOGIN_LOCKOUT_WINDOW]
    attempts.append(now)
    LOGIN_ATTEMPTS[client_ip] = attempts

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        form_data = LoginRequest(username=username, password=password)
    except ValidationError as e:
        errors = e.errors()
        error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]
        return JSONResponse(
            status_code=422,
            content={"error": "Validation failed", "details": error_messages}
        )
    
    client_ip = request.client.host if request.client else "127.0.0.1"
    
    # Check rate limit
    allowed, error_msg = check_login_rate_limit(client_ip)
    if not allowed:
        return RedirectResponse(url=f"/login?error={error_msg.replace(' ', '+')}", status_code=status.HTTP_303_SEE_OTHER)
    
    user = await get_user_by_username(form_data.username)
    next_url = request.query_params.get("next") or "/"
    
    if not user or not verify_password(form_data.password, user["password_hash"]):
        # Record failed attempt for rate limiting
        record_failed_login(client_ip)
        # Preserve 'next' on error
        error_url = "/login?error=Invalid+username+or+password"
        if next_url != "/":
            error_url += f"&next={next_url}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_303_SEE_OTHER)
    
    access_token = create_access_token(data={"sub": form_data.username})
    redirect = RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)
    # Set cookie for web UI
    redirect.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return redirect

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    # Only allow registration if no users exist (Setup Mode)
    count = await get_user_count()
    if count > 0:
        return RedirectResponse(url="/login")
    
    settings = await get_settings()
    return templates.TemplateResponse("register.html", {
        "request": request,
        "settings": settings
    })

@app.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...), full_name: str = Form("")):
    try:
        form_data = RegisterRequest(username=username, password=password, full_name=full_name)
    except ValidationError as e:
        errors = e.errors()
        error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]
        return JSONResponse(
            status_code=422,
            content={"error": "Validation failed", "details": error_messages}
        )
    
    # Only allow registration if no users exist
    try:
        count = await get_user_count()
        if count > 0:
            raise HTTPException(status_code=403, detail="Registration is disabled")
        
        await create_user(form_data.username, get_password_hash(form_data.password), form_data.full_name, is_admin=True)
        return RedirectResponse(url="/login?success=Account+created!+Please+login.", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        print(f"Registration error: {e}")
        return RedirectResponse(url=f"/login?error=Registration+failed:+{str(e)}", status_code=status.HTTP_303_SEE_OTHER)

# --- App Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    
    settings = await get_settings()
    recent_summaries = await get_summaries(user["id"], limit=5)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "presets": settings.get("prompt_presets", PROMPT_PRESETS),
        "recent_summaries": recent_summaries,
        "user": user,
        "settings": settings
    })

@app.get("/api/metadata")
@rate_limit(max_requests=10, window_seconds=60)
async def get_video_info(url: str, user = Depends(require_user)):
    """Fetch video metadata for live preview."""
    video_id = extract_video_id(url)
    if not video_id:
        return JSONResponse(status_code=400, content={"error": "Invalid YouTube URL"})
    
    try:
        metadata = await get_video_metadata(video_id)
        return metadata
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/chat")
@rate_limit(max_requests=10, window_seconds=60)
async def chat(
    request: Request,
    id: int = Form(...),
    message: str = Form(...),
    user = Depends(require_user)
):
    """Stream a chat response about a specific summary using the transcript as context."""
    try:
        form_data = ChatRequest(id=id, message=message)
    except ValidationError as e:
        errors = e.errors()
        error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]
        return JSONResponse(
            status_code=422,
            content={"error": "Validation failed", "details": error_messages}
        )
    
    try:
        summary = await get_summary(form_data.id)
        if not summary or summary["user_id"] != user["id"]:
            return JSONResponse(status_code=404, content={"error": "Summary not found"})
        
        settings = await get_settings()
        api_token = settings.get("api_token")
        api_endpoint = settings.get("api_endpoint")
        model = settings.get("default_model")

        if not check_api_token_configured(api_token):
            return JSONResponse(status_code=400, content={"error": "API Token not configured. Please set your API token in Settings before generating summaries."})

        system_prompt = (
            f"You are a helpful assistant. The user has watched a YouTube video titled '"
            f"{summary['video_title']}' by '{summary['channel_name']}'.\n"
            f"Here is the full transcript for your reference:\n\n{summary['transcript'][:300000]}\n\n"
            "Answer the user's questions about this video concisely and accurately."
        )

        async def generator():
            async for chunk in stream_summarize_transcript(
                transcript=form_data.message,
                prompt=system_prompt,
                api_token=api_token,
                api_endpoint=api_endpoint,
                model=model
            ):
                yield chunk

        return StreamingResponse(
            generator(),
            media_type="text/plain",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
        )
    except Exception as e:
        print(f"Chat error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/summarize")
async def summarize_legacy(
    request: Request,
    url: str = Form(...),
    preset: str = Form("detailed"),
    user = Depends(require_user)
):
    """Non-streaming summarize for re-summarize from summary page."""
    try:
        form_data = SummaryRequest(url=url, preset=preset)
    except ValidationError as e:
        errors = e.errors()
        error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]
        return JSONResponse(
            status_code=422,
            content={"error": "Validation failed", "details": error_messages}
        )
    
    try:
        metadata, transcript, prompt, video_id = await _prepare_summarize(form_data.url, form_data.preset)
        settings = await get_settings()
        
        summary_text = await summarize_transcript(
            transcript=transcript,
            prompt=prompt,
            api_token=settings.get("api_token", ""),
            api_endpoint=settings.get("api_endpoint", ""),
            model=settings.get("default_model", "")
        )
        
        summary_id = await _save_summary_to_db(
            user_id=user["id"],
            video_id=video_id,
            metadata=metadata,
            transcript=transcript,
            summary_text=summary_text,
            preset=form_data.preset,
            model=settings.get("default_model", ""),
            api_endpoint=settings.get("api_endpoint", "")
        )
        
        return {"id": summary_id, "summary": summary_text, "video_title": metadata["title"],
                "channel_name": metadata["channel"], "duration": metadata["duration"],
                "thumbnail_url": metadata["thumbnail"]}
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
    except Exception as e:
        print(f"Summarize error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/summarize/stream")
async def summarize_stream(
    request: Request,
    url: str = Form(...),
    preset: str = Form("detailed"),
    user = Depends(require_user)
):
    """Extract transcript and stream summary."""
    try:
        form_data = SummaryRequest(url=url, preset=preset)
    except ValidationError as e:
        errors = e.errors()
        error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]
        return JSONResponse(
            status_code=422,
            content={"error": "Validation failed", "details": error_messages}
        )
    
    try:
        metadata, transcript, prompt, video_id = await _prepare_summarize(form_data.url, form_data.preset)
        settings = await get_settings()
        
        async def generator():
            full_summary = ""
            # Yield metadata first as a JSON string on the first line
            metadata_json = json.dumps({
                "type": "metadata",
                "video_title": metadata["title"],
                "channel_name": metadata["channel"],
                "duration": metadata["duration"],
                "thumbnail_url": metadata["thumbnail"]
            })
            yield f"{metadata_json}\n"

            async for chunk in stream_summarize_transcript(
                transcript=transcript,
                prompt=prompt,
                api_token=settings.get("api_token", ""),
                api_endpoint=settings.get("api_endpoint", ""),
                model=settings.get("default_model", "")
            ):
                full_summary += chunk
                yield chunk

            # After streaming is done, save to DB
            summary_id = await _save_summary_to_db(
                user_id=user["id"],
                video_id=video_id,
                metadata=metadata,
                transcript=transcript,
                summary_text=full_summary,
                preset=form_data.preset,
                model=settings.get("default_model", ""),
                api_endpoint=settings.get("api_endpoint", "")
            )
            # Yield final ID
            yield f"\n[ID:{summary_id}]"

        return StreamingResponse(
            generator(), 
            media_type="text/plain",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
        
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
    except Exception as e:
        print(f"Summarize stream error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
        
        async def generator():
            full_summary = ""
            # Yield metadata first as a JSON string on the first line
@app.get("/history", response_class=HTMLResponse)
async def history(request: Request, q: Optional[str] = None, unread: bool = False, user = Depends(require_user)):
    summaries = await get_summaries(user_id=user["id"], search=q, unread_only=unread)
    settings = await get_settings()
    return templates.TemplateResponse("history.html", {
        "request": request, 
        "summaries": summaries, 
        "q": q or "",
        "unread": unread,
        "user": user,
        "settings": settings
    })

@app.get("/summary/{summary_id}", response_class=HTMLResponse)
async def view_summary(request: Request, summary_id: int, user = Depends(require_user)):
    summary = await get_summary(summary_id)
    if not summary or summary["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Summary not found")

    # Mark as read
    await mark_summary_read(summary_id, user["id"])

    # Get adjacent summaries for navigation
    nav = await get_adjacent_summaries(user["id"], summary_id)

    settings = await get_settings()
    return templates.TemplateResponse("summary.html", {
        "request": request,
        "summary": summary,
        "user": user,
        "settings": settings,
        "nav": nav
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user = Depends(require_user)):
    # Only admin can view settings for now
    if not user.get("is_admin"):
        return RedirectResponse(url="/")
        
    settings = await get_settings()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings,
        "user": user
    })

@app.post("/settings")
async def update_settings_route(request: Request, user = Depends(require_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    form_data = await request.form()
    for key, value in form_data.items():
        if key == "prompt_presets":
            try:
                # Expecting JSON string from the textarea
                value = json.loads(str(value))
            except json.JSONDecodeError:
                continue
        await update_setting(key, value)
    
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)
@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, user = Depends(require_user)):
    if not user.get("is_admin"):
        return RedirectResponse(url="/")
    
    users_list = await get_users()
    settings = await get_settings()
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users_list,
        "user": user,
        "settings": settings
    })

@app.post("/admin/users/create")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    is_admin: bool = Form(False),
    user = Depends(require_user)
):
    try:
        form_data = AdminUserCreate(username=username, password=password, full_name=full_name, is_admin=is_admin)
    except ValidationError as e:
        errors = e.errors()
        error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in errors]
        return JSONResponse(
            status_code=422,
            content={"error": "Validation failed", "details": error_messages}
        )
    
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    await create_user(form_data.username, get_password_hash(form_data.password), form_data.full_name, form_data.is_admin)
    return RedirectResponse(url="/admin/users?success=User+created!", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/users/delete/{user_id_to_delete}")
async def admin_delete_user(user_id_to_delete: int, user = Depends(require_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Don't allow deleting self
    if user_id_to_delete == user["id"]:
        return RedirectResponse(url="/admin/users?error=Cannot+delete+yourself!", status_code=status.HTTP_303_SEE_OTHER)
        
    await db_delete_user(user_id_to_delete)
    return RedirectResponse(url="/admin/users?success=User+deleted!", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/users/role/{user_id_to_update}")
async def admin_toggle_role(user_id_to_update: int, is_admin: bool = Form(...), user = Depends(require_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Don't allow demoting self
    if user_id_to_update == user["id"] and not is_admin:
        return RedirectResponse(url="/admin/users?error=Cannot+demote+yourself!", status_code=status.HTTP_303_SEE_OTHER)
        
    await update_user_role(user_id_to_update, is_admin)
    return RedirectResponse(url="/admin/users?success=Role+updated!", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/users/update/{user_id_to_update}")
async def admin_update_user(user_id_to_update: int, full_name: str = Form(...), user = Depends(require_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    full_name = full_name.strip()
    if len(full_name) > 100:
        full_name = full_name[:100]
        
    await update_user_profile(user_id_to_update, full_name)
    return RedirectResponse(url="/admin/users?success=Profile+updated!", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/users/password/{user_id_to_update}")
async def admin_reset_password(user_id_to_update: int, password: str = Form(...), user = Depends(require_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if len(password) < 8:
        return RedirectResponse(url="/admin/users?error=Password+must+be+at+least+8+characters!", status_code=status.HTTP_303_SEE_OTHER)
    if len(password) > 128:
        password = password[:128]
        
    await update_user_password(user_id_to_update, get_password_hash(password))
    return RedirectResponse(url="/admin/users?success=Password+reset+successfully!", status_code=status.HTTP_303_SEE_OTHER)


# --- Secure API Endpoints (For Extension ONLY) ---

@app.post("/api/login")
async def api_login(request: Request, data: dict):
    """API login for extension to get a token."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    
    # Check rate limit
    allowed, error_msg = check_login_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(status_code=429, detail=error_msg)
    
    username = data.get("username")
    password = data.get("password")
    user = await get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        # Record failed attempt for rate limiting
        record_failed_login(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": username})
    return {"access_token": access_token, "token_type": "bearer", "username": username}

@app.get("/api/ping")
async def api_ping():
    """Simple ping endpoint to test server connectivity (no auth required)."""
    return {"ok": True}

@app.post("/api/summarize")
@rate_limit(max_requests=10, window_seconds=60)
async def api_summarize(request: Request, user = Depends(require_user)):
    """API endpoint for background summarization (e.g. from extension)."""
    try:
        data = await request.json()
        url = data.get("url")
        preset = data.get("preset", "detailed")
        
        if not url:
            return JSONResponse(content={"error": "URL is required"}, status_code=400)
            
        video_id = extract_video_id(url)
        if not video_id:
            return JSONResponse(content={"error": "Invalid YouTube URL"}, status_code=400)

        settings = await get_settings()
        api_token = settings.get("api_token")
        api_endpoint = settings.get("api_endpoint")
        model = settings.get("default_model")
        presets = settings.get("prompt_presets", PROMPT_PRESETS)
        
        if not check_api_token_configured(api_token):
             return JSONResponse(content={"error": "API Token not configured. Please set your API token in Settings before generating summaries."}, status_code=400)

        prompt = presets.get(preset, presets.get("detailed", "Summarize this."))
        metadata = await get_video_metadata(video_id)
        transcript = await get_transcript(video_id)
        
        summary = await summarize_transcript(
            transcript=transcript,
            prompt=f"You are a helpful assistant that summarizes YouTube video transcripts. {prompt}",
            api_token=api_token,
            api_endpoint=api_endpoint,
            model=model
        )
        
        summary_id = await save_summary(
            user_id=user["id"],
            video_id=video_id,
            video_title=metadata["title"], 
            video_url=f"https://www.youtube.com/watch?v={video_id}",
            channel_name=metadata["channel"],
            duration=metadata["duration"],
            thumbnail_url=metadata["thumbnail"],
            transcript=transcript,
            summary=summary,
            prompt_preset=preset,
            model=model,
            api_endpoint=api_endpoint
        )
        
        return {"id": summary_id, "status": "Summarized successfully", "summary": summary}
    except Exception as e:
        print(f"API Summarize error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/presets")
@rate_limit(max_requests=10, window_seconds=60)
async def get_presets_api(user = Depends(require_user)):
    """Return available prompt presets."""
    settings = await get_settings()
    return settings.get("prompt_presets", PROMPT_PRESETS)

@app.get("/api/summary/check")
@rate_limit(max_requests=10, window_seconds=60)
async def check_summary_by_url(url: str, user = Depends(require_user)):
    """Check if a video has already been summarized by this user."""
    video_id = extract_video_id(url)
    if not video_id:
        return {"exists": False}
    
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, summary, video_title, channel_name FROM summaries WHERE video_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1",
            (video_id, user["id"])
        )
        row = await cursor.fetchone()
        if row:
            return {
                "exists": True,
                "id": row["id"],
                "summary": row["summary"],
                "title": row["video_title"],
                "channel": row["channel_name"]
            }
    
    return {"exists": False}

@app.delete("/api/summary/{summary_id}")
@rate_limit(max_requests=10, window_seconds=60)
async def delete_summary_api(summary_id: int, user = Depends(require_user)):
    await db_delete_summary(summary_id, user["id"])
    return {"success": True}

# --- Extension Routes ---

@app.get("/extension", response_class=HTMLResponse)
async def extension_page(request: Request, user = Depends(require_user)):
    settings = await get_settings()
    return templates.TemplateResponse("extension.html", {
        "request": request,
        "user": user,
        "settings": settings
    })

@app.get("/extension/download")
async def download_extension(request: Request, user = Depends(require_user)):
    """Download the extension as a ZIP file."""
    extension_dir = BASE_DIR.parent / "extension"
    
    # Get the server URL from the request for the default server URL in popup.js
    server_url = str(request.base_url).rstrip('/')

    # Create a ZIP file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in extension_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(extension_dir)
                
                # Replace placeholder in popup.js with actual server URL
                if file_path.name == "popup.js":
                    content = file_path.read_text(encoding='utf-8')
                    content = content.replace("'__SERVER_URL__'", f"'{server_url}'")
                    zip_file.writestr(str(arcname), content)
                else:
                    zip_file.write(file_path, arcname)

    zip_buffer.seek(0)

    return StreamingResponse(
        io.BytesIO(zip_buffer.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=papertube-extension.zip"
        }
    )

@app.get("/extension/firefox/download")
async def download_extension_firefox(request: Request, user = Depends(require_user)):
    """Download the Firefox extension as a ZIP file."""
    extension_dir = BASE_DIR.parent / "extension-firefox"
    
    # Get the server URL from the request for the default server URL in popup.js
    server_url = str(request.base_url).rstrip('/')

    # Create a ZIP file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in extension_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(extension_dir)
                
                # Replace placeholder in popup.js with actual server URL
                if file_path.name == "popup.js":
                    content = file_path.read_text(encoding='utf-8')
                    content = content.replace("'__SERVER_URL__'", f"'{server_url}'")
                    zip_file.writestr(str(arcname), content)
                else:
                    zip_file.write(file_path, arcname)

    zip_buffer.seek(0)

    return StreamingResponse(
        io.BytesIO(zip_buffer.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=papertube-extension-firefox.zip"
        }
    )
