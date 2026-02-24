# TikTok Upload Manager - Enhanced Features

## Features Added from ClipEmpire

### 1. 🎬 Smart Background Manager
- **Non-repeating background selection** - Cycles through all videos before reusing
- **Theme-based matching** - Automatically selects backgrounds matching your content (scary, dating, crazy, mystery, motivational)
- **Quality scoring** - Validates brightness, resolution, duration
- **Auto-download** - Downloads gameplay videos (GTA, Minecraft, Subway Surfers) from YouTube

### 2. 👥 Multi-Account Manager
- **SQLite database tracking** - Track followers, views, likes, posts per account
- **Smart scheduling** - Queue posts with optimal timing based on account settings
- **Performance analytics** - Track growth and engagement over time
- **Status tracking** - Monitor account health (created, aging, active, monetized, banned)

### 3. 📝 Modern Subtitle Renderer
- **TikTok/Reels-style subtitles** - Word-by-word progressive reveal
- **Clean typography** - Modern fonts with soft shadows
- **Smart grouping** - 2-3 words at a time with natural phrasing
- **Crossfade animations** - Smooth transitions

### 4. 🎵 Professional Audio Pipeline
- **Auto-ducking** - Automatically reduces music when speech plays
- **LUFS normalization** - Consistent perceived loudness
- **Music looping** - Seamlessly loops background music to match video duration
- **Multiple presets** - Standard, aggressive duck, subtle duck

## Quick Start

### Python API

```python
from tiktok_features import TikTokFeatures

# Initialize
features = TikTokFeatures()

# Get a background video
background = features.get_background(theme="scary", min_duration=30)
print(f"Selected background: {background}")

# Add an account
features.add_account(
    username="myhorroraccount",
    display_name="Horror Stories",
    niche="horror",
    posts_per_day=5
)

# Track a post
features.track_post(
    account_username="myhorroraccount",
    video_path="./my_video.mp4",
    caption="Scary story time!",
    hashtags=["#horror", "#scary", "#fyp"],
    views=10000,
    likes=500
)

# Get analytics
analytics = features.get_analytics("myhorroraccount", days=30)
print(f"Total views: {analytics['total_views']}")

# Add subtitles (requires captions list)
video_with_subs = features.add_subtitles(
    video="input.mp4",
    captions=[
        {"word": "This", "start": 0.0, "end": 0.2},
        {"word": "is", "start": 0.2, "end": 0.4},
        {"word": "amazing", "start": 0.4, "end": 0.8},
    ]
)

# Add music with auto-ducking
mixed_audio = features.add_music(
    narration_path="narration.mp3",
    music_path="background_music.mp3",
    music_volume=0.15,
    preset="standard"
)
```

### Command Line Interface

```bash
# Check status
python3 ~/TikTokUploadManager/Python/tiktok_features.py status

# List available backgrounds
python3 ~/TikTokUploadManager/Python/tiktok_features.py backgrounds

# Download background videos
python3 ~/TikTokUploadManager/Python/tiktok_features.py download-backgrounds

# Add an account
python3 ~/TikTokUploadManager/Python/tiktok_features.py add-account \
    --username myaccount \
    --niche horror \
    --name "Horror Stories"

# List accounts
python3 ~/TikTokUploadManager/Python/tiktok_features.py list-accounts

# Get analytics
python3 ~/TikTokUploadManager/Python/tiktok_features.py analytics --username myaccount
```

## File Structure

```
TikTokUploadManager/
├── Python/
│   ├── tiktok_features.py      # Main integration wrapper (EASY API)
│   ├── background_manager.py   # Background video selection
│   ├── account_manager.py      # Multi-account tracking
│   ├── subtitle_renderer.py    # Modern subtitles
│   ├── audio_pipeline.py       # Audio mixing with ducking
│   └── video_processor.py      # Original video processor
├── backgrounds/                 # Background video storage
│   ├── gta/
│   ├── satisfying/
│   └── gameplay/
├── data/
│   └── accounts.db             # Account tracking database
└── music/                      # Background music files
```

## Examples

### Example 1: Create a video with smart background
```python
from tiktok_features import TikTokFeatures

features = TikTokFeatures()

# Get a non-repeating horror background
bg = features.get_background(theme="scary", min_duration=45)

# Use it in your video processing...
```

### Example 2: Track multiple accounts
```python
features = TikTokFeatures()

# Add accounts
features.add_account("account1", "Horror Stories", "horror")
features.add_account("account2", "Dating Stories", "dating")
features.add_account("account3", "Crazy Stories", "crazy")

# Track posts
features.track_post("account1", "video1.mp4", "Scary story!", ["#horror"], views=5000)
features.track_post("account2", "video2.mp4", "Wild date!", ["#dating"], views=3000)

# Get top performers
accounts = features.list_accounts()
for acc in sorted(accounts, key=lambda a: a.total_views, reverse=True):
    print(f"@{acc.username}: {acc.total_views} views")
```

### Example 3: Add professional audio
```python
from tiktok_features import TikTokFeatures

features = TikTokFeatures()

# Add music with auto-ducking
# Music automatically reduces volume when narration plays
mixed = features.add_music(
    narration_path="voice.mp3",
    music_path="background.mp3",
    music_volume=0.15,
    preset="aggressive_duck"  # More aggressive ducking for clearer speech
)

# Save the result
mixed.write_audiofile("output.mp3")
```

## Dependencies

All features use existing dependencies from ClipEmpire:
- `moviepy` - Video/audio processing
- `Pillow (PIL)` - Image processing for subtitles
- `numpy` - Audio calculations
- `sqlite3` - Account database (built-in)
- `yt-dlp` - Background video downloads

Install missing dependencies:
```bash
pip3 install moviepy Pillow numpy yt-dlp
```

## Themes Supported

- `scary` / `horror` - Horror/scary backgrounds
- `dating` / `romance` - Romantic/night driving
- `crazy` / `wild` - Chaotic/action backgrounds
- `mystery` / `suspense` - Mysterious atmospheres
- `motivational` / `inspire` - Inspirational/luxury
- `creepy` - Unsettling atmospheres
- `interesting` / `facts` - Engaging/satisfying content

## Notes

- All paths are automatically configured relative to TikTokUploadManager
- Background videos are cached and reused efficiently
- Account database is stored in `data/accounts.db`
- Features work standalone or integrated with existing video_processor.py
