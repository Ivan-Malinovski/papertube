from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.datastructures import Headers
import zipfile
import io
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .transcription import extract_video_id, get_transcript, get_video_metadata
from .llm import summarize_transcript, stream_summarize_transcript
from .database import (
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
import aiosqlite

# Use lifespan to initialize the database
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

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

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = await get_user_by_username(username)
    next_url = request.query_params.get("next") or "/"
    
    if not user or not verify_password(password, user["password_hash"]):
        # Preserve 'next' on error
        error_url = "/login?error=Invalid+username+or+password"
        if next_url != "/":
            error_url += f"&next={next_url}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_303_SEE_OTHER)
    
    access_token = create_access_token(data={"sub": username})
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
async def register(username: str = Form(...), password: str = Form(...), full_name: str = Form("")):
    # Only allow registration if no users exist
    try:
        count = await get_user_count()
        if count > 0:
            raise HTTPException(status_code=403, detail="Registration is disabled")
        
        await create_user(username, get_password_hash(password), full_name, is_admin=True)
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
async def chat(
    id: int = Form(...),
    message: str = Form(...),
    user = Depends(require_user)
):
    """Stream a chat response about a specific summary using the transcript as context."""
    try:
        summary = await get_summary(id)
        if not summary or summary["user_id"] != user["id"]:
            return JSONResponse(status_code=404, content={"error": "Summary not found"})
        
        settings = await get_settings()
        api_token = settings.get("api_token")
        api_endpoint = settings.get("api_endpoint")
        model = settings.get("default_model")

        if not api_token:
            return JSONResponse(status_code=400, content={"error": "API Token not configured"})

        system_prompt = (
            f"You are a helpful assistant. The user has watched a YouTube video titled '"
            f"{summary['video_title']}' by '{summary['channel_name']}'.\n"
            f"Here is the full transcript for your reference:\n\n{summary['transcript'][:300000]}\n\n"
            "Answer the user's questions about this video concisely and accurately."
        )

        async def generator():
            async for chunk in stream_summarize_transcript(
                transcript=message,
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
    url: str = Form(...),
    preset: str = Form("detailed"),
    user = Depends(require_user)
):
    """Non-streaming summarize for re-summarize from summary page."""
    video_id = extract_video_id(url)
    if not video_id:
        return JSONResponse(content={"error": "Invalid YouTube URL"}, status_code=400)
    try:
        settings = await get_settings()
        api_token = settings.get("api_token")
        api_endpoint = settings.get("api_endpoint")
        model = settings.get("default_model")
        presets = settings.get("prompt_presets", PROMPT_PRESETS)
        if not api_token:
            return JSONResponse(content={"error": "API Token not configured"}, status_code=400)
        prompt = presets.get(preset, presets.get("detailed", "Summarize this."))
        metadata = await get_video_metadata(video_id)
        transcript = await get_transcript(video_id)
        summary_text = await summarize_transcript(
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
            summary=summary_text,
            prompt_preset=preset,
            model=model,
            api_endpoint=api_endpoint
        )
        return {"id": summary_id, "summary": summary_text, "video_title": metadata["title"],
                "channel_name": metadata["channel"], "duration": metadata["duration"],
                "thumbnail_url": metadata["thumbnail"]}
    except Exception as e:
        print(f"Summarize error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/summarize/stream")
async def summarize_stream(
    url: str = Form(...),
    preset: str = Form("detailed"),
    user = Depends(require_user)
):
    """Extract transcript and stream summary."""
    video_id = extract_video_id(url)
    if not video_id:
        return JSONResponse(content={"error": "Invalid YouTube URL"}, status_code=400)

    try:
        settings = await get_settings()
        api_token = settings.get("api_token")
        api_endpoint = settings.get("api_endpoint")
        model = settings.get("default_model")
        presets = settings.get("prompt_presets", PROMPT_PRESETS)
        
        if not api_token:
             return JSONResponse(content={"error": "API Token not configured in settings"}, status_code=400)

        prompt = presets.get(preset, presets.get("detailed", "Summarize this."))
        
        metadata = await get_video_metadata(video_id)
        transcript = await get_transcript(video_id)
        
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
                prompt=f"You are a helpful assistant that summarizes YouTube video transcripts. {prompt}",
                api_token=api_token,
                api_endpoint=api_endpoint,
                model=model
            ):
                full_summary += chunk
                yield chunk

            # After streaming is done, save to DB
            summary_id = await save_summary(
                user_id=user["id"],
                video_id=video_id,
                video_title=metadata["title"], 
                video_url=f"https://www.youtube.com/watch?v={video_id}",
                channel_name=metadata["channel"],
                duration=metadata["duration"],
                thumbnail_url=metadata["thumbnail"],
                transcript=transcript,
                summary=full_summary,
                prompt_preset=preset,
                model=model,
                api_endpoint=api_endpoint
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
        
    except Exception as e:
        print(f"Summarize stream error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

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
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    is_admin: bool = Form(False),
    user = Depends(require_user)
):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    await create_user(username, get_password_hash(password), full_name, is_admin)
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
        
    await update_user_profile(user_id_to_update, full_name)
    return RedirectResponse(url="/admin/users?success=Profile+updated!", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/users/password/{user_id_to_update}")
async def admin_reset_password(user_id_to_update: int, password: str = Form(...), user = Depends(require_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    await update_user_password(user_id_to_update, get_password_hash(password))
    return RedirectResponse(url="/admin/users?success=Password+reset+successfully!", status_code=status.HTTP_303_SEE_OTHER)


# --- Secure API Endpoints (For Extension ONLY) ---

@app.post("/api/login")
async def api_login(data: dict):
    """API login for extension to get a token."""
    username = data.get("username")
    password = data.get("password")
    user = await get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": username})
    return {"access_token": access_token, "token_type": "bearer", "username": username}

@app.post("/api/summarize")
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
        
        if not api_token:
             return JSONResponse(content={"error": "API Token not configured"}, status_code=400)

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
async def get_presets_api(user = Depends(require_user)):
    """Return available prompt presets."""
    settings = await get_settings()
    return settings.get("prompt_presets", PROMPT_PRESETS)

@app.get("/api/summary/check")
async def check_summary_by_url(url: str, user = Depends(require_user)):
    """Check if a video has already been summarized by this user."""
    video_id = extract_video_id(url)
    if not video_id:
        return {"exists": False}
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
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
async def download_extension(user = Depends(require_user)):
    """Download the extension as a ZIP file."""
    extension_dir = BASE_DIR.parent / "extension"

    # Create a ZIP file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in extension_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(extension_dir)
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
async def download_extension_firefox(user = Depends(require_user)):
    """Download the Firefox extension as a ZIP file."""
    extension_dir = BASE_DIR.parent / "extension-firefox"

    # Create a ZIP file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in extension_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(extension_dir)
                zip_file.write(file_path, arcname)

    zip_buffer.seek(0)

    return StreamingResponse(
        io.BytesIO(zip_buffer.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=papertube-extension-firefox.zip"
        }
    )
