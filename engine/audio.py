"""Voice, music and sound effects shared by every video.

make_voice(): Kokoro TTS per line -> <build>/voice.wav and <build>/timeline.json
(line start/end and estimated per-word times for captions).
mix(): procedural music bed + SFX cues + voice, with the music ducked under speech.
"""
import json
import os

import numpy as np
import soundfile as sf

SR = 24000
MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


def trim_silence(x, thresh=0.01):
    """Return (start, end) sample indices of the voiced part."""
    env = np.convolve(np.abs(x), np.ones(240) / 240, mode="same")
    idx = np.where(env > thresh)[0]
    if len(idx) == 0:
        return 0, len(x)
    return max(0, idx[0] - 120), min(len(x), idx[-1] + 240)


def word_times(text, t0, t1):
    """Spread words across [t0, t1] by character weight (Kokoro-onnx has no timestamps)."""
    words = text.split()
    weights = np.array([len(w.strip(",.?!'\"")) + 2.2 + (2.5 if w[-1] in ",.?!" else 0) for w in words])
    edges = np.concatenate([[0], np.cumsum(weights)]) / weights.sum() * (t1 - t0) + t0
    return [{"w": w, "s": float(edges[i]), "e": float(edges[i + 1])} for i, w in enumerate(words)]


def make_voice(script_lines, voice_name, speed, lead_in, build, extra=None):
    """script_lines: [(scene, text, pause_after[, spoken_text])]. `extra` maps line index -> dict merged into the timeline entry."""
    from kokoro_onnx import Kokoro

    os.makedirs(build, exist_ok=True)
    k = Kokoro(os.path.join(MODELS, "kokoro-v1.0.onnx"), os.path.join(MODELS, "voices-v1.0.bin"))
    pieces = [np.zeros(int(lead_in * SR), dtype=np.float32)]
    t = lead_in
    lines = []
    for entry in script_lines:
        scene, text, pause = entry[:3]
        say = entry[3] if len(entry) > 3 else text  # optional phonetic spelling for TTS
        samples, sr = k.create(say, voice=voice_name, speed=speed, lang="en-us")
        assert sr == SR
        a, b = trim_silence(samples)
        clip = samples[a:b].astype(np.float32)
        dur = len(clip) / SR
        lines.append({"scene": scene, "text": text, "start": t, "end": t + dur,
                      "words": word_times(text, t + 0.02, t + dur - 0.05)})
        pieces += [clip, np.zeros(int(pause * SR), dtype=np.float32)]
        t += dur + pause
        print(f"  {scene:9s} {dur:5.2f}s  {text}")
    voice = np.concatenate(pieces)
    for i, extra_info in (extra or {}).items():
        lines[i].update(extra_info)
    sf.write(os.path.join(build, "voice.wav"), voice, SR)
    with open(os.path.join(build, "timeline.json"), "w") as f:
        json.dump({"duration": len(voice) / SR, "lines": lines}, f, indent=1)
    print(f"voice: {len(voice) / SR:.2f}s")


# ---------- procedural music + sfx ----------

def _env(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na) if na else 1
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def _note(freq, dur, amp=1.0, a=0.01, r=0.3, kind="pluck"):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "pluck":
        sig = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
        sig *= np.exp(-t * 5.5)
    else:  # pad
        sig = sum(np.sin(2 * np.pi * freq * d * t + p) for d, p in ((1, 0), (1.004, 1.3), (0.996, 2.1))) / 3
        sig += 0.15 * np.sin(4 * np.pi * freq * t)
    return amp * sig * _env(n, a, r)


def music(total):
    """Soft I-vi-IV-V pad with a plucked arpeggio, 90 BPM."""
    out = np.zeros(int(total * SR) + SR)
    beat = 60 / 90
    chords = [(261.63, 329.63, 392.00), (220.00, 261.63, 329.63), (174.61, 220.00, 261.63), (196.00, 246.94, 293.66)]
    bar = 4 * beat
    t = 0.0
    i = 0
    while t < total:
        ch = chords[i % 4]
        s = int(t * SR)
        pad = sum(_note(f / 2, bar + 0.4, 0.10, a=0.6, r=0.8, kind="pad") for f in ch)
        out[s:s + len(pad)] += pad[: len(out) - s]
        for k in range(8):  # eighth-note arpeggio
            f = ch[[0, 1, 2, 1, 0, 2, 1, 2][k]] * (2 if k in (2, 5) else 1)
            ss = int((t + k * beat / 2) * SR)
            if ss >= len(out):
                break
            nt = _note(f, 0.6, 0.05)
            out[ss:ss + len(nt)] += nt[: len(out) - ss]
        t += bar
        i += 1
    # gentle low-pass
    out = np.convolve(out, np.ones(6) / 6, mode="same")
    return out[: int(total * SR)]


def sfx(kind):
    rng = np.random.default_rng(7)
    if kind == "whoosh":
        n = int(0.45 * SR)
        noise = rng.standard_normal(n)
        k = np.linspace(2, 40, n).astype(int)
        sig = np.array([noise[max(0, i - kk):i + 1].mean() for i, kk in enumerate(k)])
        return 0.5 * sig * np.sin(np.linspace(0, np.pi, n)) ** 2
    if kind == "pop":
        n = int(0.12 * SR)
        t = np.arange(n) / SR
        f = 900 * np.exp(-t * 18) + 300
        return 0.45 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30)
    if kind == "splash":
        n = int(0.5 * SR)
        t = np.arange(n) / SR
        noise = np.convolve(rng.standard_normal(n), np.ones(3) / 3, mode="same")
        return 0.35 * noise * np.exp(-t * 9) + 0.3 * np.sin(2 * np.pi * 90 * t) * np.exp(-t * 14)
    if kind == "ding":
        n = int(1.2 * SR)
        t = np.arange(n) / SR
        return 0.25 * (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t)) * np.exp(-t * 3.5)
    if kind == "spot":  # spotlight "clunk"
        n = int(0.35 * SR)
        t = np.arange(n) / SR
        return 0.6 * np.sin(2 * np.pi * 70 * t) * np.exp(-t * 16) + 0.15 * rng.standard_normal(n) * np.exp(-t * 40)
    if kind == "tick":
        n = int(0.05 * SR)
        t = np.arange(n) / SR
        return 0.25 * np.sin(2 * np.pi * 2000 * t) * np.exp(-t * 90)
    raise ValueError(kind)


def mix(voice_path, cues, out_path, music_gain=0.55):
    """cues: list of (time_seconds, sfx_kind)."""
    voice, sr = sf.read(voice_path)
    total = len(voice) / SR + 0.6
    n = int(total * SR)
    v = np.zeros(n)
    v[: len(voice)] = voice
    m = music(total)
    # duck music under speech
    env = np.convolve(np.abs(v), np.ones(2400) / 2400, mode="same")
    duck = 1.0 - 0.6 * np.clip(env / 0.03, 0, 1)
    duck = np.convolve(duck, np.ones(4800) / 4800, mode="same")
    fade = np.ones(n)
    fade[: SR // 2] = np.linspace(0, 1, SR // 2)
    fade[-SR:] = np.linspace(1, 0, SR)
    out = v + music_gain * m * duck * fade
    for t, kind in cues:
        s = sfx(kind)
        i = int(t * SR)
        if 0 <= i < n:
            out[i:i + len(s)] += s[: n - i]
    out /= max(1.0, np.abs(out).max() / 0.95)
    sf.write(out_path, out.astype(np.float32), SR)
    return total

