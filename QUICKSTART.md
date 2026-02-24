# TikTok Upload Manager - Quick Start Guide

## ✅ Installation Complete!

All features from ClipEmpire have been successfully added to your TikTok Upload Manager. Everything is working and ready to use!

## 🚀 Quick Start (Python)

### 1. Basic Usage

```python
from Python.tiktok_features import TikTokFeatures

# Initialize (automatic setup)
features = TikTokFeatures()

# That's it! You're ready to use all features
```

### 2. Get a Background Video

```python
# Get a non-repeating background for your theme
background = features.get_background(theme="scary", min_duration=30)
print(f"Using background: {background}")

# Themes: scary, dating, crazy, mystery, motivational, creepy, interesting
```

### 3. Manage Multiple Accounts

```python
# Add an account
features.add_account(
    username="myaccount",
    display_name="My Horror Stories",
    niche="horror",
    posts_per_day=5
)

# Track a post
features.track_post(
    account_username="myaccount",
    video_path="./my_video.mp4",
    caption="Scary story time!",
    hashtags=["#horror", "#fyp"],
    views=5000,
    likes=250
)

# Get analytics
analytics = features.get_analytics("myaccount")
print(f"Total views: {analytics['total_views']:,}")
```

### 4. Add Modern Subtitles

```python
# Captions format: list of dicts with word, start, end
captions = [
    {"word": "This", "start": 0.0, "end": 0.3},
    {"word": "is", "start": 0.3, "end": 0.5},
    {"word": "amazing", "start": 0.5, "end": 1.0},
]

# Add TikTok-style subtitles
video_with_subs = features.add_subtitles(
    video="input.mp4",
    captions=captions,
    font_size=28,
    words_per_phrase=2
)

# Save result
video_with_subs.write_videofile("output.mp4")
```

### 5. Add Music with Auto-Ducking

```python
# Music automatically reduces when narration plays
mixed_audio = features.add_music(
    narration_path="voice.mp3",
    music_path="background.mp3",
    music_volume=0.15,
    preset="standard"  # or "aggressive_duck", "subtle_duck"
)

# Save result
mixed_audio.write_audiofile("output.mp3")
```

## 🖥️ Command Line Usage

```bash
# Go to the app directory
cd ~/TikTokUploadManager

# Check status of all features
python3 Python/tiktok_features.py status

# List available backgrounds
python3 Python/tiktok_features.py backgrounds

# Download background videos (GTA, Minecraft, etc.)
python3 Python/tiktok_features.py download-backgrounds

# Add an account
python3 Python/tiktok_features.py add-account \
    --username myaccount \
    --niche horror \
    --name "Horror Stories"

# List accounts
python3 Python/tiktok_features.py list-accounts

# Get analytics
python3 Python/tiktok_features.py analytics --username myaccount
```

## 📁 What Was Added

### New Files:
- `Python/tiktok_features.py` - **Main easy-to-use API** (use this!)
- `Python/background_manager.py` - Smart background selection
- `Python/account_manager.py` - Multi-account tracking
- `Python/subtitle_renderer.py` - Modern subtitles
- `Python/audio_pipeline.py` - Professional audio mixing

### New Folders:
- `backgrounds/` - Background videos (auto-created)
- `data/` - Account database (auto-created)
- `music/` - Background music files (create manually)

### Documentation:
- `FEATURES.md` - Complete feature documentation
- `QUICKSTART.md` - This quick start guide (you're reading it!)

## 🎯 Most Common Use Cases

### Use Case 1: Create a video with non-repeating background
```python
features = TikTokFeatures()

# Get background (automatically selects different one each time)
bg = features.get_background(theme="scary", min_duration=45)

# Use it in your video processing
# ... your video processing code here ...
```

### Use Case 2: Track performance across multiple accounts
```python
features = TikTokFeatures()

# Add accounts
features.add_account("account1", "Horror Stories", "horror")
features.add_account("account2", "Dating Stories", "dating")

# Track posts for each
features.track_post("account1", "video1.mp4", "Story!", ["#horror"], views=10000)
features.track_post("account2", "video2.mp4", "Date!", ["#dating"], views=5000)

# Compare performance
for acc in features.list_accounts():
    analytics = features.get_analytics(acc.username)
    print(f"@{acc.username}: {analytics['total_views']} views")
```

### Use Case 3: Professional audio mixing
```python
features = TikTokFeatures()

# Add music that automatically ducks when speech plays
mixed = features.add_music(
    narration_path="narration.mp3",
    music_path="background_music.mp3",
    music_volume=0.2,
    preset="aggressive_duck"  # Clearer speech
)

mixed.write_audiofile("final_audio.mp3")
```

## 🔧 Customization

### Subtitle Styles
```python
# Custom subtitle appearance
video = features.add_subtitles(
    video="input.mp4",
    captions=captions,
    font_size=32,              # Bigger text
    position_y_ratio=0.75,     # Higher on screen (0.0=top, 1.0=bottom)
    words_per_phrase=3         # Show 3 words at once
)
```

### Audio Presets
```python
# Standard - Balanced music/speech
features.add_music(..., preset="standard")

# Aggressive duck - Music very quiet during speech (clearest)
features.add_music(..., preset="aggressive_duck")

# Subtle duck - Music only slightly reduced (more atmospheric)
features.add_music(..., preset="subtle_duck")
```

### Background Themes
Available themes:
- `scary` / `horror` - Horror gameplay (Outlast, Resident Evil)
- `dating` / `romance` - Night driving, city lights
- `crazy` / `wild` - Chaotic action (Subway Surfers)
- `mystery` / `suspense` - Dark, mysterious
- `motivational` / `inspire` - Luxury, success visuals
- `creepy` - Unsettling atmospheres
- `interesting` / `facts` - Satisfying, engaging content

## 📊 See It in Action

```bash
# Quick demo
cd ~/TikTokUploadManager
python3 test_features.py
```

This will:
1. Initialize all features
2. Show available backgrounds
3. Add a test account
4. Create test subtitles
5. Test audio pipeline
6. Display full status report

## 💡 Tips

1. **Backgrounds never repeat** - The system cycles through all videos before reusing any
2. **Accounts auto-track** - Database automatically maintains state
3. **Subtitles are TikTok-style** - Modern, word-by-word with smooth transitions
4. **Audio ducking is automatic** - No manual volume adjustments needed
5. **Everything is self-contained** - No external services required

## ❓ Need Help?

Read `FEATURES.md` for complete documentation with more examples.

## 🎉 You're Ready!

All features are installed, tested, and working. Start creating amazing TikTok videos!
