#!/usr/bin/env python3
"""
Background Video Manager
Selects non-repeating backgrounds that match the requested theme.
"""

import json
import random
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BackgroundManager:
    MIN_VISIBILITY_LUMA = 32.0
    MIN_VALID_DURATION = 8.0

    def __init__(self, backgrounds_dir: str = None):
        if backgrounds_dir is None:
            # Default to TikTokUploadManager/backgrounds
            base_dir = Path(__file__).parent.parent
            backgrounds_dir = base_dir / "backgrounds"
        self.backgrounds_dir = Path(backgrounds_dir)
        self.backgrounds_dir.mkdir(exist_ok=True)
        self.curated_dirs = [
            self.backgrounds_dir / "gta",
            self.backgrounds_dir / "satisfying",
            self.backgrounds_dir / "gameplay",
        ]
        for folder in self.curated_dirs:
            folder.mkdir(parents=True, exist_ok=True)
        self.state_file = self.backgrounds_dir / ".background_state.json"
        self.state = self._load_state()
        self.state.setdefault("last_download_attempt", 0.0)
        self._video_meta_cache: Dict[str, Dict[str, float]] = {}
        self._luma_cache: Dict[str, float] = {}

        self.theme_aliases = {
            "horror": "scary",
            "romance": "dating",
            "weird": "crazy",
            "suspense": "mystery",
            "inspire": "motivational",
            "facts": "interesting",
            "wise": "motivational",
            "wisdom": "motivational",
        }

        # Keyword tags used to match local filenames to a theme.
        self.theme_keywords: Dict[str, List[str]] = {
            "scary": ["horror", "outlast", "resident", "evil", "dark", "scary", "fnaf", "haunted", "ghost"],
            "dating": ["gta5", "night", "drive", "city", "neon", "romance", "date", "luxury", "car"],
            "crazy": ["gta5", "chaos", "subway", "surfers", "crazy", "wild", "action", "stunt"],
            "mystery": ["gta5", "dark", "mystery", "noir", "secret", "shadow", "investigation"],
            "motivational": [
                "luxury",
                "success",
                "cars",
                "supercar",
                "rich",
                "motivational",
                "inspire",
                "grind",
                "gta5",
                "drive",
                "satisfying",
                "gameplay",
            ],
            "creepy": ["minecraft", "cave", "creepy", "abandoned", "haunted", "scary", "dark"],
            "interesting": ["minecraft", "subway", "surfers", "interesting", "satisfying", "cool", "amazing"],
        }
        self.theme_avoid_keywords: Dict[str, List[str]] = {
            "dating": ["scary", "horror", "outlast", "creepy", "haunted"],
            "mystery": ["cute", "animals", "baby"],
            "motivational": ["scary", "horror", "outlast", "creepy", "ghost", "haunted"],
            "creepy": ["dating", "romance", "luxury", "success"],
        }

        self.entertaining_keywords = [
            "gta5", "minecraft", "subway", "surfers", "gameplay", "game",
            "luxury", "car", "drive", "city", "neon", "night",
            "horror", "scary", "action", "adventure",
        ]
        self.low_quality_markers = [
            "dark_gradient",
            "dark_plasma",
            "dynamic",
            "fallback",
            "temp",
            "testsrc",
        ]
        self.allowed_style_keywords = [
            "gta",
            "gta5",
            "minecraft",
            "subway",
            "surfers",
            "satisfying",
            "satisfy",
            "gameplay",
            "gaming",
            "driving",
            "car",
            "city",
            "horror",
            "outlast",
            "resident",
            "parkour",
            "luxury",
        ]

        # PREMIUM HIGH-QUALITY gameplay/satisfying sources (ENHANCED 2026-02-23)
        self.background_urls = [
            # === GTA 5 CINEMATIC (4K Premium) ===
            ("https://www.youtube.com/watch?v=Hj9N5lZodH4", "crazy_gta5_chaos_hq"),
            ("https://www.youtube.com/watch?v=PLe-ZZ4kpiw", "dating_gta5_night_drive_4k"),
            ("https://www.youtube.com/watch?v=_ZSh8dEr4Do", "mystery_gta5_night_rain_cinematic"),
            ("https://www.youtube.com/watch?v=MpiXzPqS2Rc", "motivational_gta5_long_drive_4k"),
            ("https://www.youtube.com/watch?v=XYWbHej2aqE", "dating_gta5_city_rain_premium"),
            ("https://www.youtube.com/watch?v=ZtLrNBdXT7M", "crazy_gta5_mega_ramp_epic"),

            # === MORE GTA 5 Premium ===
            ("https://www.youtube.com/watch?v=kH_lp0vQFxM", "motivational_gta5_luxury_car_4k"),
            ("https://www.youtube.com/watch?v=9q4yrQs3lmQ", "dating_gta5_sunset_drive_cinematic"),
            ("https://www.youtube.com/watch?v=5NV6Rdv1a3I", "crazy_gta5_drift_compilation"),
            ("https://www.youtube.com/watch?v=TIb8F-LkPKg", "mystery_gta5_dark_alley_4k"),

            # === SUBWAY SURFERS (Ultra Smooth) ===
            ("https://www.youtube.com/watch?v=61oLMj28vF8", "crazy_subway_surfers_gameplay_hd"),
            ("https://www.youtube.com/watch?v=7ghSziUQnhs", "interesting_subway_surfers_4k_60fps"),
            ("https://www.youtube.com/watch?v=zZ7AimPACzc", "crazy_subway_surfers_loop_premium"),
            ("https://www.youtube.com/watch?v=Kmv3WF0VjYQ", "interesting_subway_surfers_endless_4k"),

            # === MINECRAFT (Shaders + RTX) ===
            ("https://www.youtube.com/watch?v=85z7jqGAGcc", "interesting_minecraft_parkour_shaders"),
            ("https://www.youtube.com/watch?v=u7kdVe8q5zs", "creepy_minecraft_cave_ambient"),
            ("https://www.youtube.com/watch?v=OqPxaKs8xrk", "interesting_minecraft_rtx_4k"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "motivational_minecraft_build_timelapse"),

            # === HORROR PREMIUM ===
            ("https://www.youtube.com/watch?v=5wV_kKL4Ymw", "scary_outlast_gameplay_4k"),
            ("https://www.youtube.com/watch?v=5Z_2WNwxYrE", "scary_outlast_walkthrough_hd"),
            ("https://www.youtube.com/watch?v=zBmE_FTea6s", "scary_outlast_4k_ultra"),
            ("https://www.youtube.com/watch?v=Bz8l935Bv0Y", "scary_resident_evil_gameplay_4k"),
            ("https://www.youtube.com/watch?v=4VDEm5-6b8g", "creepy_silent_hill_ambient_4k"),

            # === SATISFYING PREMIUM (Oddly Satisfying) ===
            ("https://www.youtube.com/watch?v=3ll5jzjNIcs", "interesting_satisfying_3d_premium"),
            ("https://www.youtube.com/watch?v=ezTAhDES8bQ", "interesting_satisfying_compilation_4k"),
            ("https://www.youtube.com/watch?v=j4P8k9B5a8w", "motivational_satisfying_loops_hd"),
            ("https://www.youtube.com/watch?v=8BLSbKWZ_zE", "interesting_satisfying_visual_4k"),

            # === LUXURY/MOTIVATIONAL ===
            ("https://www.youtube.com/watch?v=YQRHrco73g4", "motivational_luxury_lifestyle_4k"),
            ("https://www.youtube.com/watch?v=bV2qU0kgFjY", "dating_luxury_car_night_drive"),
            ("https://www.youtube.com/watch?v=q9e5V8RM27g", "motivational_supercar_compilation_4k"),

            # === ANIME/AESTHETIC ===
            ("https://www.youtube.com/watch?v=V1j3GGt3y6k", "dating_anime_aesthetic_lofi"),
            ("https://www.youtube.com/watch?v=jfKfPfyJRdk", "mystery_anime_rain_ambient_4k"),
        ]

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except Exception:
                pass
        return {"last_used": {}, "recent": {}, "used_videos": []}

    def _save_state(self):
        try:
            self.state_file.write_text(json.dumps(self.state, indent=2))
        except Exception:
            # State persistence is non-critical.
            pass

    def _maybe_download_backgrounds(self, force: bool = False) -> int:
        now = time.time()
        last_attempt = float(self.state.get("last_download_attempt", 0.0))
        if not force and now - last_attempt < 1200:
            # Avoid repeated long download attempts in short bursts.
            return 0

        self.state["last_download_attempt"] = now
        self._save_state()
        return self.download_all_backgrounds()

    def _normalize_theme(self, theme: str) -> str:
        value = (theme or "scary").strip().lower()
        value = self.theme_aliases.get(value, value)
        if value not in self.theme_keywords:
            return "scary"
        return value

    def _theme_candidates(self, theme: str, files: List[Path]) -> List[Path]:
        keywords = self.theme_keywords.get(theme, [])
        scored: List[Tuple[int, Path]] = []
        for file_path in files:
            search_text = self._path_search_text(file_path)
            score = sum(1 for keyword in keywords if keyword in search_text)
            if theme in search_text:
                score += 2
            if score > 0:
                scored.append((score, file_path))
        scored.sort(key=lambda item: (item[0], item[1].name), reverse=True)
        return [file_path for _, file_path in scored]

    def _list_background_files(self) -> List[Path]:
        files: List[Path] = []
        for path in self.backgrounds_dir.rglob("*.mp4"):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            if path.stat().st_size <= 0:
                continue
            files.append(path)
        return sorted(files)

    def _path_search_text(self, file_path: Path) -> str:
        try:
            rel = file_path.resolve().relative_to(self.backgrounds_dir.resolve())
            return str(rel).replace("\\", "/").lower()
        except Exception:
            return file_path.name.lower()

    def _pick_non_repeating(self, theme: str, files: List[Path]) -> Optional[Path]:
        """Pick a video that has NEVER been used before. Cycles through all videos once before reusing."""
        if not files:
            return None

        files_ordered = list(files)
        used_videos = set(self.state.get("used_videos", []))

        # Filter out ALL videos that have been used before
        unused_videos = [f for f in files_ordered if f.name not in used_videos]

        # If all videos have been used, reset and start over
        if not unused_videos:
            print("🔄 All background videos have been used once. Starting fresh cycle...")
            self.state["used_videos"] = []
            used_videos = set()
            unused_videos = files_ordered

        # Select from top candidates only
        pool = unused_videos[:3] if len(unused_videos) > 3 else unused_videos
        selected = random.choice(pool)

        # Mark this video as used
        used_list = self.state.get("used_videos", [])
        used_list.append(selected.name)
        self.state["used_videos"] = used_list

        # Keep legacy tracking for compatibility
        self.state["last_used"][theme] = selected.name
        recent = self.state["recent"].get(theme, [])
        recent.append(selected.name)
        self.state["recent"][theme] = recent[-6:]

        self._save_state()

        total_available = len(files_ordered)
        videos_used = len(used_list)
        print(f"📊 Video uniqueness: {videos_used}/{total_available} backgrounds used in this cycle")

        return selected

    def _probe_video(self, file_path: Path) -> Optional[Dict[str, float]]:
        cache_key = str(file_path.resolve())
        if cache_key in self._video_meta_cache:
            return self._video_meta_cache[cache_key]

        if not file_path.exists() or file_path.stat().st_size == 0:
            return None

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration",
            "-of",
            "json",
            str(file_path),
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            data = json.loads(result.stdout or "{}")
            streams = data.get("streams", [])
            if not streams:
                return None

            stream = streams[0]
            duration = float((data.get("format") or {}).get("duration") or 0.0)
            metadata = {
                "width": float(stream.get("width") or 0),
                "height": float(stream.get("height") or 0),
                "duration": max(0.0, duration),
            }
            self._video_meta_cache[cache_key] = metadata
            return metadata
        except Exception:
            return None

    def _sample_luma(self, file_path: Path, second: float) -> Optional[float]:
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{max(0.0, second):.2f}",
            "-i",
            str(file_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=1:1,format=gray",
            "-f",
            "rawvideo",
            "-",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=15, check=False)
            if result.returncode != 0 or not result.stdout:
                return None
            return float(result.stdout[0])
        except Exception:
            return None

    def _estimate_visibility_luma(self, file_path: Path) -> Optional[float]:
        cache_key = str(file_path.resolve())
        if cache_key in self._luma_cache:
            return self._luma_cache[cache_key]

        metadata = self._probe_video(file_path)
        if not metadata:
            return None

        duration = metadata["duration"]
        sample_points = [1.0]
        if duration > 4:
            sample_points.append(duration / 2.0)
            sample_points.append(max(0.0, duration - 1.0))

        values = []
        for point in sample_points:
            value = self._sample_luma(file_path, point)
            if value is not None:
                values.append(value)

        if not values:
            return None

        avg_luma = sum(values) / len(values)
        self._luma_cache[cache_key] = avg_luma
        return avg_luma

    def _theme_relevance_score(self, theme: str, file_path: Path) -> float:
        search_text = self._path_search_text(file_path)
        score = 0.0

        if theme in search_text:
            score += 16.0

        for keyword in self.theme_keywords.get(theme, []):
            if keyword in search_text:
                score += 5.0

        for keyword in self.entertaining_keywords:
            if keyword in search_text:
                score += 1.0

        for keyword in self.theme_avoid_keywords.get(theme, []):
            if keyword in search_text:
                score -= 8.0

        for marker in self.low_quality_markers:
            if marker in search_text:
                score -= 10.0

        return score

    def _is_allowed_style(self, file_path: Path) -> bool:
        """Only allow GTA/satisfying/gameplay-style backgrounds."""
        search_text = self._path_search_text(file_path)
        if any(marker in search_text for marker in self.low_quality_markers):
            return False
        return any(keyword in search_text for keyword in self.allowed_style_keywords)

    def _candidate_score(self, theme: str, file_path: Path, min_duration: int) -> float:
        if not self._is_allowed_style(file_path):
            return -999.0

        metadata = self._probe_video(file_path)
        if not metadata:
            return -999.0

        width = metadata["width"]
        height = metadata["height"]
        duration = metadata["duration"]

        long_side = max(width, height)
        short_side = min(width, height)
        if long_side < 480 or short_side < 270:
            return -999.0
        if duration < self.MIN_VALID_DURATION:
            return -999.0

        score = self._theme_relevance_score(theme, file_path)

        if short_side >= 720:
            score += 6.0
        elif short_side >= 540:
            score += 2.0
        elif short_side < 360:
            score -= 8.0
        else:
            score -= 3.0

        if duration >= float(min_duration):
            score += 12.0
        elif duration >= max(12.0, min_duration * 0.6):
            score += 5.0
        else:
            score -= 14.0

        avg_luma = self._estimate_visibility_luma(file_path)
        if avg_luma is not None:
            if avg_luma < self.MIN_VISIBILITY_LUMA:
                return -999.0
            if avg_luma < 42:
                score -= 2.0
            elif avg_luma <= 165:
                score += 8.0
            elif avg_luma <= 225:
                score += 4.0
            else:
                score -= 2.0

        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb < 1.0:
            score -= 8.0
        elif size_mb > 700:
            score -= 4.0

        return score

    def _rank_candidates(self, theme: str, files: List[Path], min_duration: int) -> List[Tuple[float, Path]]:
        ranked: List[Tuple[float, Path]] = []
        for file_path in files:
            score = self._candidate_score(theme, file_path, min_duration=min_duration)
            if score > -900.0:
                ranked.append((score, file_path))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked

    def get_background_for_theme(self, theme: str, min_duration: int = 30) -> Optional[str]:
        """Get a non-repeating background that best fits theme."""
        theme = self._normalize_theme(theme)
        min_duration = max(15, int(min_duration))

        existing = self._list_background_files()
        if len(existing) < 8:
            print("📥 Need more usable backgrounds available locally...")
            self._maybe_download_backgrounds()
            existing = self._list_background_files()

        themed = self._theme_candidates(theme, existing)
        ranked_theme = self._rank_candidates(theme, themed, min_duration=min_duration) if themed else []
        qualified_theme = [(score, path) for score, path in ranked_theme if score >= 6.0]

        # No procedural/dynamic backgrounds: pull more gameplay clips instead.
        if len(qualified_theme) == 0:
            self._maybe_download_backgrounds(force=False)
            existing = self._list_background_files()
            themed = self._theme_candidates(theme, existing)
            ranked_theme = self._rank_candidates(theme, themed, min_duration=min_duration) if themed else []
            qualified_theme = [(score, path) for score, path in ranked_theme if score >= 6.0]

        if qualified_theme:
            ordered = [path for _, path in qualified_theme[:6]]
            selected = self._pick_non_repeating(theme, ordered)
            if selected:
                score_by_name = {path.name: score for score, path in qualified_theme}
                selected_score = score_by_name.get(selected.name, 0.0)
                luma = self._estimate_visibility_luma(selected)
                print(
                    f"🎬 Theme '{theme}' background: {selected.name}"
                    f" (score={selected_score:.1f}, luma={luma:.1f})"
                    if luma is not None
                    else f"🎬 Theme '{theme}' background: {selected.name}"
                )
                return str(selected)

        # Fallback: allow high-quality non-themed files so render still succeeds.
        ranked_all = self._rank_candidates(theme, existing, min_duration=min_duration)
        qualified_all = [(score, path) for score, path in ranked_all if score >= 6.0]
        if qualified_all:
            ordered = [path for _, path in qualified_all[:6]]
            selected = self._pick_non_repeating(theme, ordered)
            if selected:
                score_by_name = {path.name: score for score, path in qualified_all}
                selected_score = score_by_name.get(selected.name, 0.0)
                luma = self._estimate_visibility_luma(selected)
                print(
                    f"⚠️ Theme fallback background: {selected.name}"
                    f" (score={selected_score:.1f}, luma={luma:.1f})"
                    if luma is not None
                    else f"⚠️ Theme fallback background: {selected.name}"
                )
                return str(selected)

        print("❌ No valid GTA/satisfying background clips available.")
        return None

    def _download_with_yt_dlp(self, yt_dlp_bin: str, url: str, output_path: Path) -> bool:
        # ENHANCED: Download in highest quality possible (4K/1080p60)
        base_cmd = [
            yt_dlp_bin,
            "--extractor-args",
            "youtube:player_client=android",
            "--no-playlist",
            "--no-check-certificates",
            "--geo-bypass",
            "--retries",
            "3",
            "--fragment-retries",
            "3",
            "-f",
            # PREMIUM QUALITY: Prefer 4K/1080p60 with high bitrate
            "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160][ext=mp4]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o",
            str(output_path),
            url,
        ]

        attempts = [
            base_cmd[:8] + ["--download-sections", "*0-120"] + base_cmd[8:],
            base_cmd,
        ]

        for cmd in attempts:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                    return True
                output_path.unlink(missing_ok=True)
            except Exception:
                output_path.unlink(missing_ok=True)

        return False

    def download_all_backgrounds(self):
        """Download entertaining gameplay and engaging background footage."""
        print("📥 Downloading entertaining gameplay backgrounds...")
        print("   GTA 5, Minecraft, Subway Surfers, Horror games, etc.")

        yt_dlp_bin = shutil.which("yt-dlp")
        fallback_bin = Path.home() / "Library/Python/3.9/bin/yt-dlp"
        if not yt_dlp_bin and fallback_bin.exists():
            yt_dlp_bin = str(fallback_bin)
        if not yt_dlp_bin:
            print("❌ yt-dlp not found, cannot download backgrounds")
            return 0

        downloaded = 0
        for i, (url, name) in enumerate(self.background_urls, 1):
            output_path = self.backgrounds_dir / f"{name}.mp4"

            if output_path.exists() and output_path.stat().st_size > 0:
                downloaded += 1
                continue

            try:
                print(f"  ⬇️  {i}/{len(self.background_urls)}: {name}")

                ok = self._download_with_yt_dlp(yt_dlp_bin, url, output_path)

                theme_hint = name.split("_")[0]
                if ok and self._candidate_score(theme_hint, output_path, min_duration=20) > -900:
                    downloaded += 1
                    print(f"    ✅ {name}")
                elif output_path.exists():
                    output_path.unlink(missing_ok=True)
                    print(f"    ❌ Quality check failed")

                time.sleep(1.0)
            except Exception as e:
                print(f"    ❌ Error: {str(e)[:100]}")
                continue

        print(f"\n✅ Entertaining backgrounds ready: {downloaded}/{len(self.background_urls)}")
        return downloaded

    def ensure_background_exists(self, theme: str = "scary") -> str:
        """Compatibility wrapper used by existing call sites."""
        bg = self.get_background_for_theme(theme)
        if bg:
            return bg

        self._maybe_download_backgrounds()
        bg = self.get_background_for_theme(theme)
        if bg:
            return bg

        raise FileNotFoundError(
            "No valid GTA/satisfying backgrounds available. "
            "Please download gameplay clips into the backgrounds folder."
        )


if __name__ == "__main__":
    manager = BackgroundManager()
    selected = manager.ensure_background_exists("scary")
    print(f"Selected background: {selected}")
