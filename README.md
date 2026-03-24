# TikTok Upload Manager

A native macOS application for generating and publishing short-form vertical video content to TikTok. A SwiftUI frontend drives a Python backend that handles video rendering, cinematic post-processing, caption generation, and automated upload via the TikTok Content Posting API.

![Swift](https://img.shields.io/badge/Swift-5.9-F05138?logo=swift&logoColor=white)
![SwiftUI](https://img.shields.io/badge/SwiftUI-macOS%2014-0071E3?logo=apple&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-macOS%2013%2B-lightgrey?logo=apple)
![FFmpeg](https://img.shields.io/badge/FFmpeg-required-007808?logo=ffmpeg&logoColor=white)
![TikTok API](https://img.shields.io/badge/TikTok-Content%20Posting%20API-010101?logo=tiktok)

---

## Overview

TikTok Upload Manager is a self-contained desktop tool that covers the full content lifecycle — from raw video source to published TikTok post — without leaving the app. The macOS frontend communicates with a Python backend via subprocess with structured JSON output, keeping the UI fully responsive while rendering or uploading.

## Features

- **Clip Creator** — Generate 9:16 vertical clips from local video files or URLs (via yt-dlp). Configurable duration, clip count, and content theme.
- **AI Video Generation** — Produce fully rendered short-form videos with theme-aware cinematic grading, word-by-word subtitle overlays, and audio ducking, with automatic quality validation and local fallback rendering.
- **Cinematic Render Engine** — Per-theme FFmpeg filter pipelines (color balance, contrast, film grain, motion blur) applied in a single pass.
- **Caption Engine** — Generates TikTok-optimized captions and hashtags with hook-first structure.
- **Automated Upload Queue** — SQLite-backed retry-safe upload worker. Queued videos are posted to TikTok via the v2 Content Posting API with exponential retry on failure.
- **Multi-Account Tracking** — Register and monitor multiple TikTok accounts with per-account follower, view, and engagement stats.
- **Background Asset Manager** — Theme-matched background video pool with non-repeating selection and auto-download via yt-dlp.
- **In-App Preview** — AVKit-based video player with AVFoundation rendering previews before posting.
- **OAuth 2.0 Flow** — Browser-based TikTok authorization with local callback server; token state persisted in SQLite.

## Tech Stack

| Layer | Technology |
|---|---|
| macOS UI | Swift 5.9, SwiftUI, AVKit, AVFoundation |
| Backend | Python 3.11, FFmpeg, ffprobe |
| Video Processing | FFmpeg (libx264, AAC, LUFS normalization, filter graphs) |
| TikTok Integration | TikTok Content Posting API v2, OAuth 2.0 PKCE |
| Storage | SQLite (via Python `sqlite3`) |
| Caption Generation | OpenAI API (gpt-4.1-mini) |
| URL Ingestion | yt-dlp |
| Testing | Playwright (E2E), Python unittest |

## Architecture

```
TikTokUploadManager/
├── Sources/TikTokUploadManager/       # Swift/SwiftUI application
│   ├── TikTokUploadManagerApp.swift   # App entry point
│   ├── ContentView.swift              # NavigationSplitView shell + all tab views
│   ├── Models/
│   │   └── Clip.swift                 # Codable clip model
│   ├── ViewModels/
│   │   ├── ClipGeneratorViewModel.swift
│   │   └── FeaturesViewModel.swift
│   └── Services/
│       ├── PythonProcessService.swift  # Subprocess bridge (streaming stdout)
│       └── TikTokFeaturesService.swift # Backend command dispatch + JSON parsing
│
├── app/                               # Python backend package
│   ├── main.py                        # CLI entry point (argparse subcommands)
│   └── services/
│       ├── video_engine.py            # Clip generation and vertical render
│       ├── cinematic_engine.py        # Single-pass FFmpeg grading pipeline
│       ├── ai_video_generator.py      # AI-driven video generation
│       ├── shortform_ai_engine.py     # Short-form optimization pass
│       ├── caption_engine.py          # Caption and hashtag generation
│       ├── caption_renderer.py        # Subtitle overlay rendering
│       ├── audio_engine.py            # LUFS normalization, ducking
│       ├── tiktok_api.py              # TikTok v2 API client
│       ├── upload_queue.py            # Threaded retry-safe upload worker
│       ├── storage.py                 # SQLite persistence layer
│       ├── quality_validator.py       # ffprobe-based render validation
│       ├── style_profiles.py          # Video style/type registry
│       └── export_profiles.py        # 1080x1920 export config
│
├── Python/                            # Legacy CLI scripts (bundled in .app)
│   ├── clip_generator_cli.py
│   ├── tiktok_upload_cli.py
│   ├── tiktok_features.py
│   ├── account_manager.py
│   ├── background_manager.py
│   ├── subtitle_renderer.py
│   └── audio_pipeline.py
│
├── e2e-tests/                         # Playwright end-to-end tests
├── build_and_install_app.sh           # Build script (swiftc → .app bundle)
└── Package.swift                      # Swift Package Manager manifest
```

### Swift–Python Bridge

The Swift layer spawns Python as a subprocess via `PythonProcessService` and `TikTokFeaturesService`. The backend emits structured prefixed lines (`CLIP_JSON:`, `AUTH_JSON:`, `VIDEOS_JSON:`, `PROGRESS:`, etc.) that the Swift side parses line-by-line from the pipe, updating `@Published` properties on the main thread. This keeps the UI reactive without any shared memory or IPC framework.

## Getting Started

### Prerequisites

- macOS 13 or later
- Xcode Command Line Tools (`xcode-select --install`)
- Python 3.11+ (`brew install python`)
- FFmpeg (`brew install ffmpeg`)
- TikTok developer credentials ([developers.tiktok.com](https://developers.tiktok.com))
- OpenAI API key (required for caption generation)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/TikTokUploadManager.git
cd TikTokUploadManager

cp .env.example .env
# Edit .env and fill in TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, OPENAI_API_KEY
```

### 2. Install Python dependencies

```bash
pip3 install openai yt-dlp moviepy Pillow numpy requests
```

### 3. Build and install the macOS app

```bash
chmod +x build_and_install_app.sh
./build_and_install_app.sh
```

This compiles the Swift sources with `swiftc`, assembles a `.app` bundle at `~/Applications/TikTok Upload Manager.app`, copies the Python backend and resources into `Contents/Resources/`, and generates the app icon from `Resources/app_icon.png`.

### 4. Connect TikTok

Open the app, navigate to **Features**, and click **Connect TikTok**. This launches the OAuth flow in your browser and stores the access token locally.

### 5. Generate and post a clip

1. **Clip Creator** — paste a video path or URL, set duration and theme, click **Generate Clips**.
2. **Generated Clips** — preview the output in the built-in player.
3. **Post** — select a clip, review the auto-generated caption, and click **Upload to TikTok**.

## Configuration

All credentials are read from environment variables. Set them in `.env` or export them in your shell.

| Variable | Description |
|---|---|
| `TIKTOK_CLIENT_KEY` | TikTok app client key |
| `TIKTOK_CLIENT_SECRET` | TikTok app client secret |
| `TIKTOK_REDIRECT_URI` | OAuth callback URI (default: `http://localhost:8000/callback`) |
| `OPENAI_API_KEY` | OpenAI key for caption generation |
| `TIKTOK_PYTHON_EXECUTABLE` | Override Python binary path (optional) |

## Backend CLI

The Python backend can be used independently of the macOS app.

```bash
# Generate clips from a local file
python3 app/main.py generate --source video.mp4 --duration 30 --max-clips 3

# Generate an AI-produced video
python3 app/main.py generate-ai-video --theme motivational --duration 60 --video-type story

# Queue a video for upload
python3 app/main.py queue-upload --video clip.mp4 --process-now

# Run the upload queue worker continuously
python3 app/main.py worker

# Check TikTok OAuth status
python3 app/main.py oauth-status

# List queued videos
python3 app/main.py list-videos
```

## E2E Tests

```bash
cd e2e-tests
npm install
npx playwright test
```

## Requirements

- macOS 13+ (app), macOS 14+ (Swift Package target)
- Python 3.11+
- FFmpeg (must be on `PATH` or discoverable via Homebrew)
- TikTok app registered at [developers.tiktok.com](https://developers.tiktok.com) with `video.publish` scope
