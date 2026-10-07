# CLAUDE.md

TikTok Upload Manager is a native macOS (SwiftUI) app with a Python backend that turns source
footage or AI-generated scripts into 9:16 short-form videos and posts them to TikTok through the
official Content Posting API v2 (OAuth 2.0, `video.publish` scope). The Swift UI never touches
video or network code itself: it spawns Python subprocesses and parses prefixed stdout lines
(`CLIP_JSON:`, `AUTH_JSON:`, `PROGRESS:`, `AI_VIDEO_JSON:`, `ERROR:` ...). FFmpeg/ffprobe do all
rendering, SQLite holds the upload queue and OAuth tokens, and OpenAI generates captions.

**Status (2026-10-06):** Maintenance — in use alongside `clip-empire`; 14 commits (2026-02-23 → 2026-03-23), none since. Public repo.

## Architecture

- **macOS app** — `Sources/TikTokUploadManager/` (the only Swift tree that is built; see Rules).
  `ContentView.swift` holds the NavigationSplitView and all tabs (Clip Creator, Generated Clips,
  Post, Features). `PythonProcessService` streams `Python/clip_generator_cli.py`;
  `TikTokFeaturesService` runs `Python/tiktok_features.py` and `Python/tiktok_upload_cli.py`;
  `ClipGeneratorViewModel` shells out with `cd ~/TikTokUploadManager && python3 -m app.main ...`
  for `generate-ai-video` and `import-upload`. The checkout therefore **must live at
  `~/TikTokUploadManager`** (also the fallback script location when not running from the .app).
- **Backend package** — `app/`: `main.py` is an argparse CLI; `services/` holds the engines.
  Storage root is `app/`: SQLite at `app/database/app.db`, media under `app/media/{videos,
  backgrounds,exports}`, JSON logs at `logs/app.log`. AI renders land in `~/TikTok_Videos/<date>/`.
- **AI video path** — `app/services/ai_video_generator.py` imports `ContentGenerator`,
  `ViralVideoEditor` and `BackgroundManager` from the **sibling checkout `~/clip-empire`**
  (adds `~/clip-empire` and `~/clip-empire/src` to `sys.path`, parses `~/clip-empire/.env` into
  `os.environ`, writes `~/clip-empire/generated_content/latest_caption.txt`). If the import fails
  the generator returns `None` and `main.py` renders a local fallback from `app/media/backgrounds/`.
  Output then goes through `cinematic_engine` → `quality_validator` → `shortform_ai_engine`.
- **Upload path** — `tiktok_api.py` (authorize → token → creator_info → video/init → status/fetch)
  driven by `upload_queue.UploadQueueWorker` (thread, 3 retries, 8 s poll). `oauth-connect` opens the
  browser and listens on `127.0.0.1:8000/callback`.
- **Legacy CLI** — `Python/`: older monolithic pipeline (`video_processor.py` 2.3k lines,
  `account_manager.py`, `background_manager.py`, ...) plus the three bridge scripts the Swift app
  calls. `build_and_install_app.sh` copies both `Python/` and `app/` into the .app bundle.

## How to run

Prereqs: macOS 13+, Xcode CLT, Python 3.11+, FFmpeg on PATH, and these env vars exported in the
shell/app environment: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `OPENAI_API_KEY`
(optional: `TIKTOK_REDIRECT_URI`, `OPENAI_CAPTION_MODEL`, `TIKTOK_PYTHON_EXECUTABLE`,
`TIKTOK_PYTHON_SCRIPT`, `SHORTFORM_AI_ENABLED`, `AESTHETIC_THRESHOLD`, `ENGAGEMENT_THRESHOLD`).

```bash
pip3 install openai yt-dlp moviepy Pillow numpy requests   # README; no requirements.txt exists
./build_and_install_app.sh      # swiftc build -> ~/Applications/TikTok Upload Manager.app
swift build                     # same target via Package.swift (macOS 14+), compile check only

python3 -m app.main generate --source video.mp4 --duration 30 --max-clips 3
python3 -m app.main generate-ai-video --theme motivational --duration 60 --video-type story
python3 -m app.main oauth-connect [--timeout 240]   # then: oauth-status
python3 -m app.main queue-upload --video clip.mp4 --process-now
python3 -m app.main import-upload --videos a.mp4 b.mp4 --theme interesting --process-now
python3 -m app.main worker [--once]                 # also: list-videos, retry, delete, list-backgrounds
python3 Python/tiktok_features.py status            # backgrounds | download-backgrounds |
                                                    # add-account | list-accounts | analytics

python3 test_full_pipeline.py   # plain scripts, no pytest/unittest; others: test_ffmpeg_fix.py,
                                # test_fixes.py, test_video_generation.py
cd e2e-tests && npm install && npm test             # Playwright; also test:headed, test:debug, test:report
```

`python3 app/main.py ...` (README form) is equivalent to `python3 -m app.main ...`.

## Key files

| Path | Role |
|---|---|
| `Sources/TikTokUploadManager/TikTokUploadManagerApp.swift` | `@main` SwiftUI entry |
| `Sources/TikTokUploadManager/ContentView.swift` | Split view + all tab UIs |
| `Sources/TikTokUploadManager/ViewModels/ClipGeneratorViewModel.swift` | Clip/AI/import flows, post queue (`post_queue.json` in Application Support), stdout parsing |
| `Sources/TikTokUploadManager/ViewModels/FeaturesViewModel.swift` | OAuth status, accounts, backgrounds, analytics |
| `Sources/TikTokUploadManager/Services/PythonProcessService.swift` | Subprocess runner; resolves python3 and bundled script |
| `Sources/TikTokUploadManager/Services/TikTokFeaturesService.swift` | Command dispatch to `tiktok_features.py` / `tiktok_upload_cli.py` |
| `Package.swift` | SwiftPM manifest (`Sources`, excludes the stale `.py` inside it) |
| `build_and_install_app.sh` | Builds .app, bundles `Python/` + `app/`, makes the icon from `Resources/app_icon.png` |
| `app/main.py` | Backend CLI: all subcommands, OAuth callback server, fallback render |
| `app/services/ai_video_generator.py` | AI pipeline; hard dependency on `~/clip-empire` |
| `app/services/video_engine.py` | Clip extraction (yt-dlp for URLs) and vertical render |
| `app/services/cinematic_engine.py` | Single-pass FFmpeg grading/motion/grain filter graph |
| `app/services/shortform_ai_engine.py` | OpenAI aesthetic/engagement scoring + cleanup pass |
| `app/services/quality_validator.py` | ffprobe checks (black/clipped frames, 1080x1920, codecs) |
| `app/services/caption_engine.py` | Captions via OpenAI Responses API (`gpt-4.1-mini` default) |
| `app/services/tiktok_api.py` | TikTok v2 OAuth + Direct Post client |
| `app/services/upload_queue.py` / `app/services/storage.py` | Retry-safe worker / SQLite schema and paths |
| `Python/clip_generator_cli.py` | Bridge the Clip Creator tab streams; wraps `app.services` |
| `Python/tiktok_features.py` | Accounts/backgrounds/analytics CLI on the same `app.db` |
| `Python/tiktok_upload_cli.py` | Cookie-based `tiktok-uploader` wrapper (see Rules) |
| `e2e-tests/playwright.config.js` | Serves repo root on :8000 via `python3 -m http.server` |
| `.env.example` | Documents the env vars above (no loader reads a repo-root `.env`) |

## Rules and conventions

- **Edit `Sources/TikTokUploadManager/` only.** Root-level `ContentView.swift`, `Models/`,
  `Services/`, `ViewModels/`, `TikTokUploadManagerApp.swift` and
  `Sources/TikTokUploadManager/Services/ai_video_generator.py` are stale copies that nothing builds.
- **Secrets:** credentials are read with `os.getenv` only; nothing loads a repo-root `.env`, and
  `.env` is *not* in this repo's `.gitignore` (only a machine-level global ignore keeps it out).
  Never commit `.env`, `*.db`, `app/media/`, `logs/app.log`, `TikTok_AI_*.mp4` or `build/`
  (`build/AppIcon.iconset/*.png` were committed before the ignore and are regenerated by the build).
- **clip-empire coupling:** `generate-ai-video` only produces AI content when `~/clip-empire` is
  present with its own `.env` and deps; without it you get the local-background fallback. Keep the
  import names (`content_generator`, `viral_video_editor`, `background_manager`) in sync with that repo.
- **Known mismatch:** the Features tab, upload worker and retry/delete buttons invoke
  `Python/tiktok_upload_cli.py` with `--oauth-connect`, `--oauth-status`, `--list-videos-json`,
  `--retry-video`, `--delete-video`, `--queue-only`, `--worker`; the current script (rewritten in
  `ca002a6`) only defines `--video/--caption/--cookies/--content-theme/--clip-format`. The official
  API flow lives in `app/main.py`.
- **Port 8000** is shared by the OAuth callback server and the Playwright `webServer`; the e2e spec
  expects a web UI ("Video Library", `.video-card`) that this repo does not contain.
  `test_features.py` and `example_usage.py` import a `TikTokFeatures` class that no longer exists.
- Stdout protocol: new backend output must keep the `PREFIX: payload` line format; the Swift side
  treats `ERROR:` as fatal and parses JSON after the known prefixes.
- Single branch `main`; no CI, no PR template, no package manifest for Python.

## Related repos

ShortGen (canonical short-form video repo), clip-empire (older TikTok automation; runtime dependency of this app).

See also: [hub](https://github.com/andrewpeterson-dev/hub) — index of all Andrew's projects (PROJECTS.md, ABOUT-ME.md).
