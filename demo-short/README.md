# Demo short: "The Spotlight Effect"

A 30-second vertical (1080×1920) stickman explainer, generated end to end from code:
script → Kokoro TTS → procedural stickman animation → captions, music and SFX → MP4.
Output: `out/spotlight-effect.mp4`.

Fully local and free: no paid APIs, no GPU. On a 4-core CPU the voice takes ~13 s and the
video renders in ~25 s.

## Pipeline

| Step | File | What it does |
|---|---|---|
| Script | `script.py` | 12 narration lines, each tied to a scene id |
| Voice | `render.py --voice` (uses `../engine/audio.py`) | Kokoro-82M (ONNX, voice `af_heart`) per line → `build/voice.wav` + `build/timeline.json` |
| Rig | `../engine/stickman.py` | Stick figure with pose library, faces, hair/props, deterministic line boil |
| Render | `render.py` | `draw(frame)` per frame with cairo, 4 parallel chunks piped to ffmpeg, word-highlight captions, procedural music + SFX, loudness normalised |

Every frame is a pure function of its frame number, so chunks render in parallel and any frame can
be re-checked with `python render.py --still 120`.

## Run

```bash
python3 -m venv venv && venv/bin/pip install kokoro-onnx soundfile numpy pycairo
mkdir -p ../engine/models && cd ../engine/models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd ../../demo-short
cp assets/fonts/*.ttf ~/.fonts/ && fc-cache -f   # cairo finds fonts via fontconfig
venv/bin/python render.py --voice
venv/bin/python render.py
```

Needs ffmpeg and the cairo system library.

## Known limits

- Caption word timing is estimated from word length (kokoro-onnx returns no timestamps). Swap in
  faster-whisper alignment for exact sync.
- Scenes are hand-written per script. Turning this into a topic → video generator means an LLM
  writing `script.py` plus a scene DSL (poses, props, camera moves) instead of one function per scene.

## Credits

Fonts: Lilita One and Patrick Hand (SIL Open Font License). Voice: Kokoro-82M (Apache-2.0).
Fact: Gilovich, Medvec & Savitsky (2000), *The spotlight effect in social judgment*, JPSP 78(2).
