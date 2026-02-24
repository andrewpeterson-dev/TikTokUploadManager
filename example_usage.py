#!/usr/bin/env python3
"""
Example: Using TikTok Features
Simple examples showing how to use each feature.
"""

import sys
from pathlib import Path

# Add Python directory to path
sys.path.insert(0, str(Path(__file__).parent / "Python"))

from tiktok_features import TikTokFeatures


def example_backgrounds():
    """Example: Get themed backgrounds."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Smart Background Selection")
    print("="*70)

    features = TikTokFeatures()

    # Get backgrounds for different themes
    themes = ["scary", "dating", "crazy", "motivational"]

    print("\nGetting non-repeating backgrounds for each theme:")
    for theme in themes:
        bg = features.get_background(theme=theme, min_duration=30)
        if bg:
            print(f"  {theme:15s} → {Path(bg).name}")
        else:
            print(f"  {theme:15s} → No backgrounds yet (run download-backgrounds)")

    # Download more backgrounds
    print("\nTo download gameplay backgrounds:")
    print("  python3 Python/tiktok_features.py download-backgrounds")


def example_accounts():
    """Example: Manage multiple accounts."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Multi-Account Management")
    print("="*70)

    features = TikTokFeatures()

    # Add accounts for different niches
    print("\nAdding accounts...")
    accounts_data = [
        ("horror_stories_daily", "Horror Stories Daily", "horror"),
        ("wild_dates_official", "Wild Dates", "dating"),
        ("crazy_facts_hub", "Crazy Facts Hub", "interesting"),
    ]

    for username, display_name, niche in accounts_data:
        success = features.add_account(
            username=username,
            display_name=display_name,
            niche=niche,
            posts_per_day=5
        )
        status = "✅ Added" if success else "ℹ️  Already exists"
        print(f"  {status}: @{username}")

    # List all accounts
    print("\nAll accounts:")
    accounts = features.list_accounts()
    for acc in accounts:
        print(f"  @{acc.username:25s} {acc.niche:15s} {acc.followers:6d} followers")

    # Track some posts
    print("\nTracking posts...")
    features.track_post(
        account_username="horror_stories_daily",
        video_path="video1.mp4",
        caption="Scary story time!",
        hashtags=["#horror", "#scary", "#fyp"],
        views=5000,
        likes=250
    )
    print("  ✅ Tracked post for @horror_stories_daily")

    # Get analytics
    print("\nAnalytics for @horror_stories_daily:")
    analytics = features.get_analytics("horror_stories_daily")
    print(f"  Views: {analytics.get('total_views', 0):,}")
    print(f"  Likes: {analytics.get('total_likes', 0):,}")
    print(f"  Posts: {analytics.get('post_count', 0)}")


def example_subtitles():
    """Example: Add modern subtitles."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Modern Subtitle Rendering")
    print("="*70)

    features = TikTokFeatures()

    print("\nSubtitle renderer configuration:")
    renderer = features.subtitle_renderer
    print(f"  Video size: {renderer.width}x{renderer.height}")
    print(f"  Font size: {renderer.font_size}px")
    print(f"  Position Y: {renderer.position_y}px")
    print(f"  Words per phrase: {renderer.words_per_phrase}")

    # Example captions (you would get these from speech-to-text)
    captions = [
        {"word": "This", "start": 0.0, "end": 0.2},
        {"word": "is", "start": 0.2, "end": 0.4},
        {"word": "an", "start": 0.4, "end": 0.5},
        {"word": "example", "start": 0.5, "end": 0.9},
        {"word": "subtitle", "start": 0.9, "end": 1.3},
    ]

    print("\nExample captions:")
    for cap in captions:
        print(f"  {cap['start']:.1f}s - {cap['end']:.1f}s: {cap['word']}")

    print("\nTo add subtitles to video:")
    print("  video = features.add_subtitles('input.mp4', captions)")
    print("  video.write_videofile('output.mp4')")


def example_audio():
    """Example: Audio mixing with auto-ducking."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Professional Audio Mixing")
    print("="*70)

    features = TikTokFeatures()

    print("\nAudio pipeline configuration:")
    pipeline = features.audio_pipeline
    print(f"  Target LUFS: {pipeline.target_lufs}")
    print(f"  Duck amount: {pipeline.duck_amount_db} dB")
    print(f"  Fade duration: {pipeline.music_fade_duration}s")

    print("\nAvailable presets:")
    presets = {
        "standard": "Balanced music/speech",
        "aggressive_duck": "Music very quiet during speech (clearest)",
        "subtle_duck": "Music only slightly reduced (atmospheric)"
    }
    for name, desc in presets.items():
        print(f"  {name:18s} - {desc}")

    print("\nTo add music with auto-ducking:")
    print("  mixed = features.add_music(")
    print("      narration_path='voice.mp3',")
    print("      music_path='background.mp3',")
    print("      music_volume=0.15,")
    print("      preset='standard'")
    print("  )")
    print("  mixed.write_audiofile('output.mp3')")


def example_complete_workflow():
    """Example: Complete video creation workflow."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Complete Workflow")
    print("="*70)

    features = TikTokFeatures()

    print("\nComplete video creation workflow:")
    print("""
    # 1. Get a non-repeating background
    bg = features.get_background(theme="scary", min_duration=45)

    # 2. Create your video with the background
    # ... your video processing code ...

    # 3. Add TikTok-style subtitles
    video = features.add_subtitles(video, captions)

    # 4. Add music with auto-ducking
    audio = features.add_music(
        narration_path="voice.mp3",
        music_path="music.mp3",
        music_volume=0.15
    )

    # 5. Combine and export
    final_video = video.set_audio(audio)
    final_video.write_videofile("final.mp4")

    # 6. Track the post
    features.track_post(
        account_username="myaccount",
        video_path="final.mp4",
        caption="Amazing story!",
        hashtags=["#scary", "#fyp"],
        views=0  # Update later with actual views
    )

    # 7. Check analytics later
    analytics = features.get_analytics("myaccount")
    print(f"Total views: {analytics['total_views']}")
    """)


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("TIKTOK FEATURES - USAGE EXAMPLES")
    print("="*70)

    try:
        example_backgrounds()
        example_accounts()
        example_subtitles()
        example_audio()
        example_complete_workflow()

        print("\n" + "="*70)
        print("✅ All examples shown!")
        print("="*70)
        print("\nFor more details, see:")
        print("  - QUICKSTART.md (quick start guide)")
        print("  - FEATURES.md (complete documentation)")
        print("\nTo test features:")
        print("  python3 test_features.py")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
