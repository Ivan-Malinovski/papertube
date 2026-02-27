<img width="1057" height="661" alt="image" src="https://github.com/user-attachments/assets/98a510b7-8b16-4a32-84f6-b4470cd71376" /># Papertube

A self-hosted web application that summarizes YouTube videos using AI.

I built this because a lot of videos are 10-20 minutes long, but can easily be summarized and read in less than a minute. I had a TON of YouTube tabs open, where I was curious about the content, but couldn't be bothered to watch them, even at 2x speed.
There are many YouTube summarizers available, but I built this one, because I wanted a selfhosted "read it later" kind of app, rather than having to open a page, paste an URL, read it all immediately, and then go back to what I was doing.

Papertube includes a Chromium extension, that provides a button that sends a video summary to Papertube, so you can come back and read it later.

## Features

- Extract transcripts from YouTube videos
- AI-powered summarization with multiple prompt presets
- Searchable history of all summaries
- User authentication with admin/user roles
- Chrome extension for one-click summarization
- Dark mode support
- Chat with your video transcripts

## Screenshots
<img width="1057" height="661" alt="image" src="https://github.com/user-attachments/assets/6799fdb8-79ef-44a3-8880-de6a2984538a" />
<img width="951" height="799" alt="image" src="https://github.com/user-attachments/assets/e76b09b1-f549-4ad2-bb06-52037a4c1b34" />
<img width="994" height="709" alt="image" src="https://github.com/user-attachments/assets/b9a7f8b7-3521-4092-acf2-20e11fa30504" />

Chrome extension:
<img width="415" height="673" alt="image" src="https://github.com/user-attachments/assets/ece4edb1-5b34-427f-953e-efddb2d4c939" />

The Chrome extension features a button, so you can send the video to Papertube with one click, and come back to read it later.
<img width="273" height="82" alt="image" src="https://github.com/user-attachments/assets/733ac8b9-febc-4a54-824c-8a980445b8f3" />

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

## Disclaimer

**This project is entirely vibe-coded.** While reasonable precautions have been taken to implement security measures (authentication, input validation, etc.), this was built quickly with AI assistance and has not undergone formal security auditing.

**⚠️ Recommendation:** Do not run Papertube on a public-facing server. It's designed for local/self-hosted use on trusted networks. If you do expose it publicly, you do so at your own risk.

## License

GPL
