"""
A voice for the films (the owner, 2026-11-20: "a training film with a narrating voice"): text -> speech on this
machine with Piper (pip install piper-tts; a neural voice, offline once its model is here), and the clips laid on
the film's sound track at the moments they were spoken.

The voice model: SV_VOICE=<path to a .onnx> (its .onnx.json beside it), else en_US-lessac-medium in
~/.cache/signalviewer/voices - fetched once from the Piper voices on Hugging Face when missing.
"""
import os
import urllib.request
import wave
from typing import List, Tuple

import numpy as np

VOICE = "en_US-lessac-medium"
VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "signalviewer", "voices")


def voice_path() -> str:
    p = os.environ.get("SV_VOICE")
    if p:
        return p
    p = os.path.join(CACHE, VOICE + ".onnx")
    if not (os.path.isfile(p) and os.path.isfile(p + ".json")):
        os.makedirs(CACHE, exist_ok=True)
        for f in (VOICE + ".onnx", VOICE + ".onnx.json"):
            print("fetching the voice", f)
            urllib.request.urlretrieve(VOICE_URL + f, os.path.join(CACHE, f))
    return p


class Narrator:
    """Speech for a line of text (int16 samples), and the film's sound track from (second, samples) clips."""

    def __init__(self, path: str = ""):
        from piper import PiperVoice
        self.voice = PiperVoice.load(path or voice_path())
        self.rate = int(self.voice.config.sample_rate)

    def speak(self, text: str) -> np.ndarray:
        chunks = list(self.voice.synthesize(text))
        a = np.concatenate([np.frombuffer(c.audio_int16_bytes, dtype=np.int16) for c in chunks]) if chunks else np.zeros(0, np.int16)
        return a

    def track(self, clips: List[Tuple[float, np.ndarray]], seconds: float, path: str) -> None:
        """One mono WAV of `seconds`, each clip starting at its second (a clip that would overlap the one before
        starts after it - the voice never talks over itself)."""
        out = np.zeros(int((seconds + 1) * self.rate), dtype=np.int32)
        end = 0
        for t, a in sorted(clips, key=lambda c: c[0]):
            i = max(int(t * self.rate), end)
            j = min(len(out), i + len(a))
            out[i:j] += a[: j - i]
            end = j + int(0.15 * self.rate)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(np.clip(out * 0.89, -32768, 32767).astype(np.int16).tobytes())     # peaks at -1 dB
