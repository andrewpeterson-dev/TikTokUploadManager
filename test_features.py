#!/usr/bin/env python3
"""
Test script for TikTok Features
"""

import sys
from pathlib import Path

# Add Python directory to path
sys.path.insert(0, str(Path(__file__).parent / "Python"))

from tiktok_features import TikTokFeatures


def test_initialization():
    """Test that features initialize correctly."""
    print("\n" + "="*70)
    print("TEST 1: Initialization")
    print("="*70)

    try:
        features = TikTokFeatures()
        print("✅ TikTokFeatures initialized successfully")
        return features
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_backgrounds(features):
    """Test background video features."""
    print("\n" + "="*70)
    print("TEST 2: Background Manager")
    print("="*70)

    try:
        # List backgrounds
        backgrounds = features.list_backgrounds()
        print(f"✅ Found {len(backgrounds)} background videos")

        if backgrounds:
            for bg in backgrounds[:3]:
                print(f"   - {bg.name}")

        # Try to get a background
        bg = features.get_background(theme="scary", min_duration=30)
        if bg:
            print(f"✅ Selected background: {Path(bg).name}")
        else:
            print("ℹ️  No backgrounds available yet (run download-backgrounds to add)")

        return True
    except Exception as e:
        print(f"❌ Background test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_accounts(features):
    """Test account management features."""
    print("\n" + "="*70)
    print("TEST 3: Account Manager")
    print("="*70)

    try:
        # Add a test account
        success = features.add_account(
            username="test_horror_account",
            display_name="Test Horror Stories",
            niche="horror",
            bio="Testing the account manager",
            posts_per_day=5
        )

        if success:
            print("✅ Added test account: @test_horror_account")
        else:
            print("ℹ️  Account already exists (that's OK)")

        # List accounts
        accounts = features.list_accounts()
        print(f"✅ Total accounts: {len(accounts)}")

        for acc in accounts[:3]:
            print(f"   @{acc.username} - {acc.niche} - {acc.followers} followers")

        # Track a post
        success = features.track_post(
            account_username="test_horror_account",
            video_path="./test_video.mp4",
            caption="Test post",
            hashtags=["#test", "#horror", "#fyp"],
            views=100,
            likes=10
        )

        if success:
            print("✅ Tracked test post")

        # Get analytics
        analytics = features.get_analytics("test_horror_account", days=30)
        print(f"✅ Analytics: {analytics.get('total_views', 0)} views, {analytics.get('total_posts', 0)} posts")

        return True
    except Exception as e:
        print(f"❌ Account test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_subtitle_renderer(features):
    """Test subtitle renderer."""
    print("\n" + "="*70)
    print("TEST 4: Subtitle Renderer")
    print("="*70)

    try:
        # Test subtitle renderer initialization
        renderer = features.subtitle_renderer
        print(f"✅ Subtitle renderer initialized")
        print(f"   Video size: {renderer.width}x{renderer.height}")
        print(f"   Font size: {renderer.font_size}px")
        print(f"   Position: {renderer.position_y_ratio * 100}%")

        # Test subtitle image creation
        test_text = "This is a test subtitle"
        img = renderer._create_subtitle_image(test_text)
        print(f"✅ Created subtitle image: {img.shape}")

        return True
    except Exception as e:
        print(f"❌ Subtitle test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_audio_pipeline(features):
    """Test audio pipeline."""
    print("\n" + "="*70)
    print("TEST 5: Audio Pipeline")
    print("="*70)

    try:
        # Test audio pipeline initialization
        pipeline = features.audio_pipeline
        print(f"✅ Audio pipeline initialized")
        print(f"   Target LUFS: {pipeline.target_lufs}")
        print(f"   Duck amount: {pipeline.duck_amount_db} dB")
        print(f"   Music fade: {pipeline.music_fade_duration}s")

        return True
    except Exception as e:
        print(f"❌ Audio test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("TIKTOK UPLOAD MANAGER - FEATURE TESTS")
    print("="*70)

    results = {}

    # Test 1: Initialization
    features = test_initialization()
    results["initialization"] = features is not None

    if not features:
        print("\n❌ Cannot continue tests without initialization")
        return

    # Test 2: Background Manager
    results["backgrounds"] = test_backgrounds(features)

    # Test 3: Account Manager
    results["accounts"] = test_accounts(features)

    # Test 4: Subtitle Renderer
    results["subtitles"] = test_subtitle_renderer(features)

    # Test 5: Audio Pipeline
    results["audio"] = test_audio_pipeline(features)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All features working correctly!")
        features.print_status()
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
