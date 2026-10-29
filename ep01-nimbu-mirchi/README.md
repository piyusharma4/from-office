# Episode 01: Why Do Indians Hang Lemon and Chillies on Doors?

A 1:57 long-form pilot (1920×1080, 30 fps) in the channel's notebook style: ruled paper, blue
ballpoint ink, yellow highlighter, a recurring host in an orange kurta, a chapter timeline bar,
and animated props (the nimbu-mirchi charm, shops, trucks, the Alakshmi cloud, maps and meters).

- Video: `out/ep01-nimbu-mirchi.mp4`
- Thumbnail: `out/thumbnail.png` (1280×720)

## Structure

| Chapter | Scenes |
|---|---|
| Hook | shop street → "everywhere" panels → WhatsApp question → title |
| 1. The thing | recipe card, Saturday swap, the nimbu-mirchi vendor |
| 2. The legend | Lakshmi vs Alakshmi, the visit, nazar, never step on an old one |
| 3. The "science" | the forwarded message, evidence meter, mosquito scoreboard |
| 4. The truth | evil eye worldwide (Turkish bead, truck art), rituals and anxiety, the shopkeeper |
| Outro | verdict checklist, next-episode card |

Facts and sources are noted at the top of `script.py`.

## Run

Uses the shared `../engine` (stickman rig, Kokoro voice, music/SFX). Models go in `../engine/models`
(see `../demo-short/README.md` for setup).

```bash
python render.py --voice      # Kokoro narration + timeline (~45 s on 4 CPU cores)
python render.py --still 900  # check one frame
python render.py              # full render + thumbnail (~1 min 40 s on 4 CPU cores)
```

Hindi words get a phonetic spelling for the TTS (4th field in `LINES`) while captions keep the
proper spelling.
