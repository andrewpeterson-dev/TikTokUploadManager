#!/usr/bin/env python3
"""
FULLY AUTOMATED YouTube downloader using youtube-dl.
NO manual steps - paste URL and it downloads!
"""

import subprocess
from pathlib import Path
from datetime import datetime


class AutoDownloader:
    """Fully automated YouTube downloader using youtube-dl."""

    def __init__(self, downloads_dir=None):
        self.downloads_dir = downloads_dir or Path.home() / "Downloads"
        self.downloads_dir.mkdir(exist_ok=True)

    def download_via_api(self, youtube_url: str, progress_callback=None) -> Path:
        """
        FULLY AUTOMATED download using youtube-dl.
        NO browser, NO manual steps!
        """
        if progress_callback:
            progress_callback("🚀 FULL AUTO-DOWNLOAD: Starting download...")

        try:
            # Find youtube-dl
            youtube_dl_paths = [
                str(Path.home() / 'Library/Python/3.9/bin/youtube-dl'),
                '/usr/local/bin/youtube-dl',
                'youtube-dl'
            ]

            youtube_dl_path = None
            for path in youtube_dl_paths:
                try:
                    result = subprocess.run([path, '--version'], capture_output=True, timeout=5)
                    if result.returncode == 0:
                        youtube_dl_path = path
                        break
                except:
                    continue

            if not youtube_dl_path:
                if progress_callback:
                    progress_callback("❌ youtube-dl not found, installing...")
                # Try to install it
                subprocess.run(['pip3', 'install', '--user', 'youtube-dl'], capture_output=True)
                youtube_dl_path = str(Path.home() / 'Library/Python/3.9/bin/youtube-dl')

            output_template = str(self.downloads_dir / '%(title)s.%(ext)s')

            # Get files before download
            before_files = set(self.downloads_dir.glob("*.mp4"))

            if progress_callback:
                progress_callback("📥 Downloading video from YouTube...")

            # Download with youtube-dl (simpler, more reliable than yt-dlp)
            cmd = [
                youtube_dl_path,
                '--format', 'best[ext=mp4]/best',
                '--output', output_template,
                '--no-playlist',
                '--no-warnings',
                youtube_url
            ]

            # Run download with live output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # Read output
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                if '[download]' in line and '%' in line:
                    # Extract progress
                    try:
                        percent = line.split('%')[0].split()[-1]
                        if progress_callback:
                            progress_callback(f"📥 Downloading... {percent}%")
                    except:
                        pass

            process.wait()

            # Find new file
            after_files = set(self.downloads_dir.glob("*.mp4"))
            new_files = after_files - before_files

            if new_files:
                newest = max(new_files, key=lambda p: p.stat().st_mtime)
                if progress_callback:
                    progress_callback(f"✅ Downloaded: {newest.name}")
                return newest

            if progress_callback:
                progress_callback("❌ Download failed - YouTube may be blocking")
            return None

        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ Error: {str(e)[:100]}")
            return None


def test_auto_download():
    """Test the auto downloader."""
    downloader = AutoDownloader()

    def log(msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    # Test URL
    url = "https://youtu.be/8clGFN6PJKo"

    print(f"\n🚀 Testing FULLY AUTOMATED Download")
    print(f"📺 URL: {url}\n")

    result = downloader.download_via_api(url, progress_callback=log)

    if result:
        print(f"\n✅ SUCCESS!")
        print(f"📁 File: {result.name}")
        print(f"📊 Size: {result.stat().st_size / (1024*1024):.1f} MB")
        print(f"📍 Location: {result}")
    else:
        print(f"\n❌ FAILED")


if __name__ == "__main__":
    test_auto_download()
