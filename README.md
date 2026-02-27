# Papertube

A self-hosted web application that summarizes YouTube videos using AI.

## Why I Built This

Let's face it — a lot of YouTube videos are 10-20 minutes long but could be summarized in under a minute. I used to have dozens of tabs open, videos I was curious about but never got around to watching, even at 2x speed.

There are plenty of YouTube summarizers out there, but I wanted something different: a self-hosted "read it later" experience. Instead of pasting a URL, reading the summary immediately, and moving on, Papertube lets you queue up videos and come back to them when you're ready.

The included Chromium extension makes this seamless — just hit "Summarize" on any YouTube video, and it's saved to your Papertube history for later.

## Features

- Extract transcripts from YouTube videos
- AI-powered summarization with multiple prompt presets
- Searchable history of all summaries
- User authentication with admin/user roles
- Chrome extension for one-click summarization
- Dark mode support
- Chat with your video transcripts

## Screenshots

<p align="center">
  <img width="400" alt="Home page" src="https://github.com/user-attachments/assets/6799fdb8-79ef-44a3-8880-de6a2984538a" />
  <img width="400" alt="Summary view" src="https://github.com/user-attachments/assets/e76b09b1-f549-4ad2-bb06-52037a4c1b34" />
</p>
<p align="center">
  <img width="400" alt="History" src="https://github.com/user-attachments/assets/b9a7f8b7-3521-4092-acf2-20e11fa30504" />
  <img width="400" alt="Chat with transcript" src="https://github.com/user-attachments/assets/ece4edb1-5b34-427f-953e-efddb2d4c939" />
</p>
<p align="center">
  <img width="400" alt="Chrome extension" src="https://github.com/user-attachments/assets/733ac8b9-febc-4a54-824c-8a980445b8f3" />
</p>

## Tech Stack

- **Backend**: Python + FastAPI
- **Database**: SQLite (aiosqlite)
- **Frontend**: Vanilla HTML/CSS/JS with Jinja2 templates
- **AI**: OpenAI-compatible API (configurable endpoint)
- **Container**: Docker + Docker Compose

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/Ivan-Malinovski/papertube.git
cd papertube
docker compose up -d --build
```

The app will be available at `http://localhost:8080`

### Manual Setup

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Configuration

1. First launch will show a setup page to create the admin account
2. Navigate to Settings (admin only)
3. Set your OpenAI-compatible API endpoint and token
4. Choose your default model

## Chrome Extension

1. Open `chrome://extensions/`
2. Enable Developer Mode
3. Click "Load unpacked"
4. Select the `extension/` folder
5. Configure the server URL in extension settings
6. Login with your Papertube credentials

## Prompt Presets

Customize your summarization style with built-in presets:
- **Brief**: Quick 2-3 sentence summary
- **Detailed**: Comprehensive breakdown
- **Bullets**: Key points as bullet list
- **Chapters**: Logical section breakdown

Add your own custom presets in Settings.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main page |
| POST | `/summarize/stream` | Stream summary generation |
| GET | `/history` | View all summaries |
| GET | `/summary/{id}` | View single summary |
| DELETE | `/api/summary/{id}` | Delete a summary |
| GET | `/settings` | Configuration page |
| POST | `/api/login` | API authentication |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (random) | JWT secret key |

## Credits

Papertube wouldn't be possible without these projects:

- **[youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)** — Makes transcript extraction dead simple
- **[FastAPI](https://fastapi.tiangolo.com/)** — The excellent async Python web framework

## Disclaimer

**This project is entirely vibe-coded.** While reasonable precautions have been taken to implement security measures (authentication, input validation, etc.), this was built quickly with AI assistance and has not undergone formal security auditing.

**⚠️ Recommendation:** Do not run Papertube on a public-facing server. It's designed for local/self-hosted use on trusted networks. If you do expose it publicly, you do so at your own risk.

## License

GPL
