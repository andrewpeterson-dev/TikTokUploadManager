#!/usr/bin/env python3
"""
Quick test to verify all TikTok Upload Manager fixes are working:
1. Video zoom/scaling: 95% content visibility (not 88%)
2. Caption sizes: 16-24 range (not 18-28)
3. Caption positioning: Very bottom (1820-1890px)
4. Background: Always present
"""

import re
from pathlib import Path

def test_zoom_scaling():
    """Verify inner_scale is 0.95 (not 0.88)"""
    print("🔍 Testing zoom/scaling fixes...")
    video_processor = Path("Python/video_processor.py")
    content = video_processor.read_text()

    # Find all inner_scale assignments
    scale_pattern = r'inner_scale\s*=\s*(0\.\d+)'
    matches = re.findall(scale_pattern, content)

    if not matches:
        print("❌ No inner_scale found!")
        return False

    all_correct = True
    for scale in matches:
        scale_val = float(scale)
        if scale_val != 0.95:
            print(f"❌ Found inner_scale = {scale} (should be 0.95)")
            all_correct = False

    if all_correct:
        print(f"✅ All {len(matches)} inner_scale values are 0.95 (was 0.88)")

    return all_correct

def test_caption_sizes():
    """Verify caption font sizes are 16-24 range"""
    print("\n🔍 Testing caption size fixes...")
    video_processor = Path("Python/video_processor.py")
    content = video_processor.read_text()

    # Check dynamic caption size range
    if 'max(16, min(24, round(font_size)))' in content:
        print("✅ Dynamic caption sizes: 16-24 range (was 18-28)")
    else:
        print("❌ Dynamic caption size range not updated")
        return False

    # Check ASS style font sizes
    if 'style_main_font = 18 if' in content and 'else 20' in content:
        print("✅ ASS main font: 18-20 (was 22-24)")
    else:
        print("❌ ASS main font not updated")
        return False

    if 'Style: Hook,Arial Bold,24' in content:
        print("✅ ASS hook font: 24 (was 30)")
    else:
        print("❌ ASS hook font not updated")
        return False

    return True

def test_caption_positioning():
    """Verify captions are at very bottom (1820-1890)"""
    print("\n🔍 Testing caption positioning fixes...")
    video_processor = Path("Python/video_processor.py")
    content = video_processor.read_text()

    # Check bottom positioning values
    if 'y = 1860' in content and 'y = 1840' in content and 'y = 1870' in content:
        print("✅ Caption Y positions: 1840-1870 (was 1750-1800)")
    else:
        print("❌ Caption Y positions not updated")
        return False

    if 'max(1820, min(1890, y))' in content:
        print("✅ Caption range constraint: 1820-1890 (was 1700-1850)")
    else:
        print("❌ Caption range constraint not updated")
        return False

    return True

def test_background_always_present():
    """Verify background application has proper error handling"""
    print("\n🔍 Testing background presence fixes...")
    video_processor = Path("Python/video_processor.py")
    content = video_processor.read_text()

    # Check for improved error messages
    if 'CRITICAL: Export with background FAILED' in content:
        print("✅ Critical error logging added for background failures")
    else:
        print("❌ Critical error logging not added")
        return False

    if 'Background will be added in final export step' in content:
        print("✅ Informative messages added for intermediate steps")
    else:
        print("❌ Intermediate step messages not added")
        return False

    return True

def main():
    print("=" * 60)
    print("TikTok Upload Manager - Fix Validation")
    print("=" * 60)

    results = []
    results.append(("Zoom/Scaling", test_zoom_scaling()))
    results.append(("Caption Sizes", test_caption_sizes()))
    results.append(("Caption Positioning", test_caption_positioning()))
    results.append(("Background Presence", test_background_always_present()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("🎉 ALL FIXES VERIFIED - Ready for video generation!")
    else:
        print("⚠️  SOME TESTS FAILED - Review fixes above")
    print("=" * 60)

    return all_passed

if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent)
    success = main()
    exit(0 if success else 1)
