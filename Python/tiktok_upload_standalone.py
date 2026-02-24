#!/usr/bin/env python3
"""Standalone TikTok upload script - works without app module dependencies"""

import argparse
import json
import sys
import warnings
from pathlib import Path

# Try importing tiktok-uploader
try:
    from tiktok_uploader.upload import upload_video
    UPLOADER_AVAILABLE = True
except ImportError:
    UPLOADER_AVAILABLE = False
    print("ERROR: tiktok-uploader not installed. Run: pip3 install tiktok-uploader", file=sys.stderr)

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")


def log(message: str) -> None:
    """Print message with flush for real-time feedback"""
    print(message, flush=True)


def upload_to_tiktok(video_path: str, caption: str, cookies_path: str = None) -> int:
    """
    Upload video to TikTok with auto-filled caption.

    Args:
        video_path: Path to video file
        caption: Caption text to use
        cookies_path: Optional path to cookies file

    Returns:
        0 on success, 1 on error
    """
    if not UPLOADER_AVAILABLE:
        return 1

    video_file = Path(video_path)
    if not video_file.exists():
        log(f"ERROR: Video file not found: {video_path}")
        return 1

    # Default cookies location
    if cookies_path is None:
        cookies_path = str(Path.home() / ".tiktok-uploader" / "cookies.json")

    cookies_file = Path(cookies_path)
    if not cookies_file.exists():
        log(f"⚠️  Cookies file not found: {cookies_path}")
        log("🔧 Please set up authentication:")
        log("   1. Go to TikTok.com and log in")
        log("   2. Open Developer Tools (F12)")
        log("   3. Go to Application → Cookies → https://www.tiktok.com")
        log("   4. Copy the 'sessionid' cookie value")
        log("   5. Save to ~/.tiktok-uploader/cookies.json:")
        log('      [{"name": "sessionid", "value": "YOUR_VALUE", "domain": ".tiktok.com", "path": "/", "secure": true}]')
        return 1

    # Validate cookies file has sessionid
    try:
        with open(cookies_file, 'r') as f:
            cookies_data = json.load(f)
            has_sessionid = any(cookie.get('name') == 'sessionid' for cookie in cookies_data)
            if not has_sessionid:
                log(f"⚠️  Cookies file is missing 'sessionid' cookie")
                log("🔧 Please add your TikTok sessionid:")
                log("   1. Go to TikTok.com and log in")
                log("   2. Open Developer Tools (F12)")
                log("   3. Go to Application → Cookies → https://www.tiktok.com")
                log("   4. Copy the 'sessionid' cookie value")
                log("   5. Add to ~/.tiktok-uploader/cookies.json:")
                log('      [{"name": "sessionid", "value": "YOUR_SESSIONID_VALUE", "domain": ".tiktok.com", "path": "/", "secure": true}]')
                return 1
    except json.JSONDecodeError:
        log("⚠️  Cookies file is not valid JSON")
        return 1

    try:
        log(f"📹 Uploading video: {video_file.name}")
        log(f"📝 Caption: {caption[:50]}..." if len(caption) > 50 else f"📝 Caption: {caption}")
        log("")
        log("⏳ Opening TikTok Studio and auto-filling...")
        log("⚠️  Please wait for the browser to open and fields to be filled...")
        log("")

        # Upload with auto-fill
        # This will:
        # 1. Open Chrome with Selenium
        # 2. Navigate to TikTok upload page
        # 3. Auto-fill video file
        # 4. Auto-fill caption
        # 5. Leave browser open for user to click POST

        result = upload_video(
            filename=str(video_file),
            description=caption,
            cookies=cookies_path
        )

        if result:
            log("✅ Video and caption auto-filled successfully!")
            log("👉 Please review and click POST in the browser")
            return 0
        else:
            log("❌ Upload failed - check browser for errors")
            return 1

    except Exception as e:
        log(f"ERROR: Upload failed: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload video to TikTok with auto-fill")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--caption", required=True, help="Caption text")
    parser.add_argument("--cookies", help="Path to cookies file (default: ~/.tiktok-uploader/cookies.json)")

    args = parser.parse_args()

    return upload_to_tiktok(args.video, args.caption, args.cookies)


if __name__ == "__main__":
    sys.exit(main())
