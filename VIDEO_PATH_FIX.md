# Fix: "No such file or directory" Error

## Problem
The clip generation is failing with `ERROR: [Errno 2] No such file or directory` because the video file path is incomplete.

## What's Happening
You entered just the filename: `Obviously Lying During Job Interviews - Cameron Whitt (720p, h264).mp4`

The app needs the **full path** to the video file, like:
`/Users/andrewpeterson/Downloads/Obviously Lying During Job Interviews - Cameron Whitt (720p, h264).mp4`

## Solution: Use the Browse Button ✅

**Instead of typing the filename:**

1. **Click the "Browse" button** (next to the video URL field)
2. Navigate to where your video is stored (likely Downloads or Desktop)
3. Select the video file
4. The full path will automatically be filled in
5. Click "Generate Clips"

## Or: Paste the Full Path

If you want to type it manually:

1. Find your video file in Finder
2. Right-click the video → Hold Option key → Click "Copy ... as Pathname"
3. Paste the full path into the video URL field
4. Click "Generate Clips"

## Alternative: Move Video to Expected Location

The app also checks for videos in:
- `~/TikTokUploadManager/app/media/videos/`

You could move your video there and then just enter the filename.

---

## Quick Fix Right Now

**I've started a fresh build of the app for you.** The old .app bundle might have been stale.

To use it:
1. Close the current app if it's open
2. In Terminal, run:
   ```bash
   cd ~/TikTokUploadManager
   .build/debug/TikTokUploadManager
   ```
3. Use the **Browse** button to select your video
4. Try again

---

## Why This Happens

The app passes the video path to a Python script. If you only provide a filename (not a full path), Python can't find the file because it doesn't know which directory to look in.

**Always use the Browse button!** It ensures the full path is provided.
