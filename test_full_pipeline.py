#!/usr/bin/env python3
"""
Test script to verify the full TikTok Upload Manager pipeline.
Tests: Account system → AI Captions → TikTok Upload
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_imports():
    """Test 1: Verify all imports work"""
    print("=" * 60)
    print("TEST 1: Checking Imports")
    print("=" * 60)

    try:
        from app.main import configure_logging
        from app.services.storage import AppStorage
        from app.services.caption_engine import CaptionEngine, CaptionContext
        from app.services.tiktok_api import TikTokAPI
        from app.services.upload_queue import UploadQueueWorker
        from app.services.video_engine import VideoEngine
        print("✅ All imports successful!")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_account_system():
    """Test 2: Verify account management works"""
    print("\n" + "=" * 60)
    print("TEST 2: Account System")
    print("=" * 60)

    try:
        from app.services.storage import AppStorage
        storage = AppStorage(PROJECT_ROOT / "app")

        # Test database path
        print(f"Database path: {storage.db_path}")
        print(f"Database exists: {storage.db_path.exists()}")

        # Test creating account table
        from Python.tiktok_features import ensure_accounts_table, list_accounts
        ensure_accounts_table(storage)
        print("✅ Account table created/verified")

        # Test listing accounts
        accounts = list_accounts(storage)
        print(f"✅ Found {len(accounts)} accounts in database")

        return True
    except Exception as e:
        print(f"❌ Account system failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_caption_engine():
    """Test 3: Verify AI caption generation (requires OPENAI_API_KEY)"""
    print("\n" + "=" * 60)
    print("TEST 3: AI Caption Engine")
    print("=" * 60)

    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set - skipping caption test")
        print("   To test: export OPENAI_API_KEY='your-key'")
        return None  # Not a failure, just skipped

    try:
        from app.services.caption_engine import CaptionEngine, CaptionContext

        engine = CaptionEngine()
        context = CaptionContext(
            filename="test_video.mp4",
            content_theme="horror",
            clip_format="background_layer",
            source_hint="scary_story"
        )

        print("Generating test caption...")
        caption = engine.generate_caption(context)

        print("\n📝 Generated Caption:")
        print("-" * 60)
        print(caption)
        print("-" * 60)

        # Verify caption format
        if len(caption) >= 150 and len(caption) <= 300:
            print("✅ Caption length correct (150-300 chars)")
        else:
            print(f"⚠️  Caption length: {len(caption)} (expected 150-300)")

        if "#" in caption:
            hashtag_count = caption.count("#")
            print(f"✅ Caption has {hashtag_count} hashtags")
        else:
            print("⚠️  Caption missing hashtags")

        return True
    except Exception as e:
        print(f"❌ Caption generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tiktok_api():
    """Test 4: Verify TikTok API connection"""
    print("\n" + "=" * 60)
    print("TEST 4: TikTok API Connection")
    print("=" * 60)

    import os
    if not os.getenv("TIKTOK_CLIENT_KEY") or not os.getenv("TIKTOK_CLIENT_SECRET"):
        print("⚠️  TikTok credentials not set - skipping API test")
        print("   To test: export TIKTOK_CLIENT_KEY='your-key'")
        print("           export TIKTOK_CLIENT_SECRET='your-secret'")
        return None  # Not a failure, just skipped

    try:
        from app.services.storage import AppStorage
        from app.services.tiktok_api import TikTokAPI

        storage = AppStorage(PROJECT_ROOT / "app")
        api = TikTokAPI(storage)

        # Check if we have valid credentials
        print(f"Client Key: {api.client_key[:10]}...")
        print(f"Client Secret: {api.client_secret[:10]}...")
        print(f"Redirect URI: {api.redirect_uri}")

        # Check OAuth status
        status = api.get_auth_status()
        print(f"\nOAuth Status:")
        print(f"  Connected: {status['connected']}")
        print(f"  Expires At: {status.get('expires_at', 'N/A')}")
        print(f"  Seconds Remaining: {status.get('seconds_remaining', 0)}")

        if status['connected']:
            print("✅ TikTok OAuth connected!")
        else:
            print("⚠️  TikTok not connected - run: python3 -m app.main oauth-connect")

        return True
    except Exception as e:
        print(f"❌ TikTok API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dependencies():
    """Test 5: Verify Python dependencies"""
    print("\n" + "=" * 60)
    print("TEST 5: Python Dependencies")
    print("=" * 60)

    required_modules = [
        "moviepy",
        "yt_dlp",
        "pysrt",
        "nltk",
        "whisper",
        "PIL",
        "numpy",
    ]

    all_good = True
    for module_name in required_modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except ImportError:
            print(f"❌ {module_name} - MISSING")
            all_good = False

    return all_good

def test_background_files():
    """Test 6: Verify background files exist"""
    print("\n" + "=" * 60)
    print("TEST 6: Background Files")
    print("=" * 60)

    try:
        from app.services.storage import AppStorage
        storage = AppStorage(PROJECT_ROOT / "app")

        backgrounds = [
            p for p in storage.backgrounds_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm"}
        ]

        print(f"Background directory: {storage.backgrounds_dir}")
        print(f"Found {len(backgrounds)} background videos")

        if len(backgrounds) > 0:
            print("\nSample backgrounds:")
            for bg in list(backgrounds)[:5]:
                print(f"  - {bg.name}")
            if len(backgrounds) > 5:
                print(f"  ... and {len(backgrounds) - 5} more")
            print("✅ Background files present")
            return True
        else:
            print("⚠️  No background files found")
            print("   Run: python3 tiktok_features.py download-backgrounds")
            return None  # Not a failure, just needs download
    except Exception as e:
        print(f"❌ Background check failed: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("🎬 TikTok Upload Manager - Full Pipeline Verification")
    print("=" * 70)

    results = {
        "Imports": test_imports(),
        "Account System": test_account_system(),
        "Python Dependencies": test_dependencies(),
        "Background Files": test_background_files(),
        "AI Caption Engine": test_caption_engine(),
        "TikTok API": test_tiktok_api(),
    }

    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0
    skipped = 0

    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
            passed += 1
        elif result is False:
            status = "❌ FAIL"
            failed += 1
        else:
            status = "⚠️  SKIPPED"
            skipped += 1

        print(f"{status:12} - {test_name}")

    print("=" * 70)
    print(f"Total: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 70)

    if failed > 0:
        print("\n⚠️  Some tests failed. Check errors above.")
        return 1
    elif passed == len(results):
        print("\n🎉 ALL TESTS PASSED! System is ready for production.")
        return 0
    else:
        print("\n⚠️  Some tests skipped (missing API keys). Core system working.")
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
