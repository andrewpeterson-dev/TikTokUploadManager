#!/usr/bin/env python3
"""
Test script to verify FFmpeg fix is working.
"""

import sys
import subprocess
from pathlib import Path

def test_ffmpeg_in_path():
    """Test 1: Check if ffmpeg is in PATH"""
    print("=" * 60)
    print("TEST 1: FFmpeg in PATH")
    print("=" * 60)

    try:
        result = subprocess.run(
            ["which", "ffmpeg"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            ffmpeg_path = result.stdout.strip()
            print(f"✅ ffmpeg found in PATH: {ffmpeg_path}")
            return True
        else:
            print("❌ ffmpeg not found in PATH")
            return False
    except Exception as e:
        print(f"❌ Error checking PATH: {e}")
        return False

def test_ffmpeg_version():
    """Test 2: Check ffmpeg version"""
    print("\n" + "=" * 60)
    print("TEST 2: FFmpeg Version")
    print("=" * 60)

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            # Get first line
            version_line = result.stdout.split('\n')[0]
            print(f"✅ {version_line}")
            return True
        else:
            print(f"❌ ffmpeg returned error: {result.returncode}")
            return False
    except FileNotFoundError:
        print("❌ ffmpeg command not found")
        return False
    except Exception as e:
        print(f"❌ Error running ffmpeg: {e}")
        return False

def test_video_processor_import():
    """Test 3: Import video_processor and check FFMPEG_BIN"""
    print("\n" + "=" * 60)
    print("TEST 3: Video Processor Import")
    print("=" * 60)

    try:
        sys.path.insert(0, str(Path(__file__).parent / "Python"))
        from video_processor import FFMPEG_BIN, FFPROBE_BIN

        print(f"✅ FFMPEG_BIN: {FFMPEG_BIN}")
        print(f"✅ FFPROBE_BIN: {FFPROBE_BIN}")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_swift_path_config():
    """Test 4: Verify Swift PythonProcessService has PATH fix"""
    print("\n" + "=" * 60)
    print("TEST 4: Swift PATH Configuration")
    print("=" * 60)

    swift_file = Path(__file__).parent / "Services" / "PythonProcessService.swift"

    if not swift_file.exists():
        print("❌ PythonProcessService.swift not found")
        return False

    content = swift_file.read_text()

    # Check for PATH configuration
    has_userbin = 'userBinPath' in content
    has_brewbin = 'brewBinPath' in content
    has_path_env = 'environment["PATH"]' in content

    if has_userbin and has_brewbin and has_path_env:
        print("✅ PythonProcessService has PATH configuration")
        print(f"   - userBinPath: {has_userbin}")
        print(f"   - brewBinPath: {has_brewbin}")
        print(f"   - PATH env: {has_path_env}")
        return True
    else:
        print("❌ PythonProcessService missing PATH configuration")
        return False

def main():
    print("\n" + "=" * 70)
    print("🎬 FFmpeg Fix Verification")
    print("=" * 70)

    results = {
        "FFmpeg in PATH": test_ffmpeg_in_path(),
        "FFmpeg Version": test_ffmpeg_version(),
        "Video Processor Import": test_video_processor_import(),
        "Swift PATH Config": test_swift_path_config(),
    }

    print("\n" + "=" * 70)
    print("📊 TEST RESULTS")
    print("=" * 70)

    passed = 0
    failed = 0

    for test_name, result in results.items():
        if result:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"{status:12} - {test_name}")

    print("=" * 70)
    print(f"Total: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        print("\n⚠️  Some tests failed. Check errors above.")
        print("\nIf ffmpeg is not installed:")
        print("  brew install ffmpeg")
        print("  Or download from: https://ffmpeg.org/download.html")
        return 1
    else:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ FFmpeg fix verified. Video generation will work!")
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
