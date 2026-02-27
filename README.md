# Papertube

A self-hosted web application that summarizes YouTube videos using AI.

## Features

- Extract transcripts from YouTube videos
- AI-powered summarization with multiple prompt presets
- Searchable history of all summaries
- User authentication with admin/user roles
- Chrome extension for one-click summarization
- Dark mode support
- Chat with your video transcripts

## Tech Stack

- **Backend**: Python + FastAPI
- **Database**: SQLite (aiosqlite)
- **Frontend**: Vanilla HTML/CSS/JS with Jinja2 templates
- **AI**: OpenAI-compatible API (configurable endpoint)
- **Container**: Docker + Docker Compose

## Quick Start

### Docker (Recommended)

```bash
docker-compose up -d
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

## License

MIT