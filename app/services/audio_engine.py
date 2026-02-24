from __future__ import annotations

from .style_profiles import StyleProfile


def build_audio_filter(profile: StyleProfile) -> str:
    """
    Build a stable normalization/compression chain.

    - Normalize speech to broadcast-safe loudness.
    - Keep dynamics open enough for speech articulation.
    - Mild ducking behavior via conservative dynamic compression when music intent is high.
    """
    music_intensity = float(profile.music_intensity)

    # Voice-first normalization target.
    chain = [
        "loudnorm=I=-14:LRA=11:TP=-1.6",
        "acompressor=threshold=-26dB:ratio=2.2:attack=8:release=160:makeup=1",
    ]

    if music_intensity > 0.65:
        chain.append("acompressor=threshold=-22dB:ratio=1.8:attack=20:release=240")
        chain.append("lowpass=f=15000")
        chain.append("highpass=f=40")
    else:
        chain.append("acompressor=threshold=-30dB:ratio=1.8:attack=12:release=180")

    # Optional dynamic ducking-like behavior by flattening low-frequency energy.
    if music_intensity >= 0.75:
        chain.append("afftfilt=real='1.0',volume=0.96")

    # Keep it light for clip readability.
    chain.append("dynaudnorm=g=5:p=0.6:m=65")

    return ",".join(chain)
