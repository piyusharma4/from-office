"""Episode 01 renderer (16:9 long form, notebook style).

    python render.py --voice       # narration -> build/voice.wav + build/timeline.json
    python render.py --still 300   # one PNG per frame number into build/
    python render.py --thumb       # out/thumbnail.png
    python render.py               # full render -> out/ep01-nimbu-mirchi.mp4

Every frame is a pure function of its frame number. Scenes are groups of
consecutive script lines; each scene function gets its local time `lt` and the
start time of each of its lines (`b`), so animation can hit narration beats.
"""
import argparse
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cairo
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "engine"))
import audio  # noqa: E402
import stickman as S  # noqa: E402
from stickman import Face, Look, POSES, ease, ease_out_back, mix, walk  # noqa: E402

import script  # noqa: E402

W, H = 1920, 1080
FPS = 30
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "out")

PAPER = (0.985, 0.978, 0.952)
RULE = (0.74, 0.83, 0.93)
MARGIN = (0.92, 0.55, 0.55)
BLUE = (0.12, 0.21, 0.52)
HL = (1.0, 0.88, 0.22)
LEMON = (0.98, 0.84, 0.2)
GREEN = (0.2, 0.6, 0.24)
DGREEN = (0.1, 0.36, 0.14)
RED = (0.86, 0.22, 0.22)
ORANGE = (1.0, 0.6, 0.22)
BROWN = (0.55, 0.42, 0.22)
S.PAPER = PAPER  # head fill matches the notebook paper
GROUND = 900

HOST = Look(color=BLUE, hair="tuft", glasses=True, shirt=ORANGE, shirt_len=0.07)
KEEPER = Look(color=BLUE, mustache=True, shirt=(1, 1, 1))


def L(**kw):
    return Look(color=BLUE, **kw)


if "--voice" in sys.argv:
    audio.make_voice(script.LINES, script.VOICE, script.SPEED, script.LEAD_IN, BUILD)
    sys.exit(0)

TL = json.load(open(os.path.join(BUILD, "timeline.json")))
LINES = TL["lines"]
TOTAL = TL["duration"] + 0.4

# group consecutive lines into scenes
SCENE_LIST = []  # (scene, start, end, [line starts])
for i, ln in enumerate(LINES):
    start = 0.0 if i == 0 else ln["start"]
    if SCENE_LIST and SCENE_LIST[-1][0] == ln["scene"]:
        SCENE_LIST[-1][3].append(ln["start"])
    else:
        SCENE_LIST.append([ln["scene"], start, None, [ln["start"]]])
for k, sc in enumerate(SCENE_LIST):
    sc[2] = SCENE_LIST[k + 1][1] if k + 1 < len(SCENE_LIST) else TOTAL

# chapter time ranges for the timeline bar
CH_RANGE = {}
for sc, s0, s1, _ in SCENE_LIST:
    c = script.CHAPTER_OF[sc]
    if c is not None:
        a, b = CH_RANGE.get(c, (s0, s1))
        CH_RANGE[c] = (min(a, s0), max(b, s1))

# ---------------------------------------------------------------- primitives


def seg(t, a, b):
    return min(1.0, max(0.0, (t - a) / (b - a))) if b > a else float(t >= a)


def pop(t, a, d=0.22):
    return ease_out_back(seg(t, a, a + d))


def camera(ctx, zoom, cx=W / 2, cy=H / 2):
    ctx.translate(W / 2, H / 2)
    ctx.scale(zoom, zoom)
    ctx.translate(-cx, -cy)


def notebook(ctx):
    ctx.set_source_rgb(*PAPER)
    ctx.paint()
    ctx.set_source_rgb(*RULE)
    ctx.set_line_width(2)
    for y in range(130, H, 56):
        ctx.move_to(0, y)
        ctx.line_to(W, y)
    ctx.stroke()
    ctx.set_source_rgb(*MARGIN)
    ctx.set_line_width(3)
    ctx.move_to(150, 0)
    ctx.line_to(150, H)
    ctx.stroke()


def ink(ctx, w=6, color=BLUE):
    ctx.set_source_rgb(*color)
    ctx.set_line_width(w)
    ctx.set_line_cap(1)
    ctx.set_line_join(1)


def wline(ctx, x0, y0, x1, y1, frame, w=6, color=BLUE, ident=0, amp=2.0):
    """Hand-drawn line with a little boil."""
    ink(ctx, w, color)
    b = frame // 4
    n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 80))
    ctx.move_to(x0, y0)
    for k in range(1, n + 1):
        f = k / n
        j = amp * S.noise(ident, k, b) if k < n else 0
        ctx.line_to(x0 + (x1 - x0) * f + j, y0 + (y1 - y0) * f + j)
    ctx.stroke()


def wrect(ctx, x, y, w, h, frame, lw=6, color=BLUE, fill=None, ident=0):
    if fill:
        ctx.set_source_rgb(*fill)
        ctx.rectangle(x, y, w, h)
        ctx.fill()
    for i, (a, b) in enumerate((((x, y), (x + w, y)), ((x + w, y), (x + w, y + h)), ((x + w, y + h), (x, y + h)), ((x, y + h), (x, y)))):
        wline(ctx, *a, *b, frame, lw, color, ident=(ident, i))


def text(ctx, s, x, y, size, font="Patrick Hand", fill=BLUE, stroke=None, sw=0, scale=1.0, alpha=1.0, align="c", rot=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return 0
    ctx.save()
    ctx.select_font_face(font)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(scale, scale)
    ox = {"c": -ext.x_advance / 2, "l": 0, "r": -ext.x_advance}[align]
    ctx.move_to(ox, -(ext.y_bearing + ext.height / 2))
    ctx.text_path(s)
    if sw:
        ctx.set_source_rgba(*(stroke or BLUE), alpha)
        ctx.set_line_width(sw)
        ctx.set_line_join(1)
        ctx.stroke_preserve()
    ctx.set_source_rgba(*fill, alpha)
    ctx.fill()
    ctx.restore()
    return ext.x_advance * scale


def text_w(ctx, s, size, font="Patrick Hand"):
    ctx.save()
    ctx.select_font_face(font)
    ctx.set_font_size(size)
    w = ctx.text_extents(s).x_advance
    ctx.restore()
    return w


def highlight(ctx, x, y, w, h, p, color=HL, alpha=0.6):
    """Highlighter swipe from left to right; p is progress 0..1."""
    if p <= 0:
        return
    ctx.save()
    ctx.set_source_rgba(*color, alpha)
    ww = w * ease(p)
    ctx.move_to(x, y - h / 2 + 4)
    ctx.line_to(x + ww, y - h / 2)
    ctx.line_to(x + ww - 6, y + h / 2)
    ctx.line_to(x - 4, y + h / 2 - 3)
    ctx.close_path()
    ctx.fill()
    ctx.restore()


def label(ctx, s, x, y, size, t, t0, hl=False, color=BLUE, font="Patrick Hand", align="c"):
    k = pop(t, t0)
    if k <= 0.01:
        return
    w = text_w(ctx, s, size, font)
    if hl:
        x0 = x - w / 2 if align == "c" else x
        highlight(ctx, x0 - 10, y + 4, w + 20, size * 0.75, seg(t, t0 + 0.1, t0 + 0.45))
    text(ctx, s, x, y, size, font=font, fill=color, scale=k, align=align)


def arrow(ctx, x0, y0, x1, y1, p, frame, color=BLUE, w=5):
    if p <= 0:
        return
    xm, ym = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
    cx, cy = (x0 + x1) / 2 + (y1 - y0) * 0.2, (y0 + y1) / 2 - (x1 - x0) * 0.2
    ink(ctx, w, color)
    ctx.move_to(x0, y0)
    ctx.curve_to(x0, y0, cx * p + x0 * (1 - p), cy * p + y0 * (1 - p), xm, ym)
    ctx.stroke()
    if p >= 1:
        a = math.atan2(y1 - cy, x1 - cx)
        for s in (-1, 1):
            ctx.move_to(x1, y1)
            ctx.line_to(x1 - 22 * math.cos(a + s * 0.45), y1 - 22 * math.sin(a + s * 0.45))
        ctx.stroke()


def stamp(ctx, s, x, y, size, t, t0, color=RED, rot=-0.12):
    k = seg(t, t0, t0 + 0.18)
    if k <= 0:
        return
    sc = 1.6 - 0.6 * ease(k)
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(sc, sc)
    w = text_w(ctx, s, size, "Lilita One") + 50
    ctx.set_source_rgba(*color, 0.9 * k)
    ctx.set_line_width(8)
    ctx.rectangle(-w / 2, -size * 0.75, w, size * 1.5)
    ctx.stroke()
    ctx.restore()
    text(ctx, s, x, y, size, font="Lilita One", fill=color, scale=sc, alpha=0.9 * k, rot=rot)


# ---------------------------------------------------------------- props


def chilli(ctx, x, y, ang, s, fresh=True):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(ang)
    L_ = 70 * s
    ctx.move_to(0, -L_ / 2)
    ctx.curve_to(12 * s, -L_ / 4, 9 * s, L_ / 4, 3 * s, L_ / 2)
    ctx.curve_to(-2 * s, L_ / 4, -8 * s, -L_ / 4, 0, -L_ / 2)
    ctx.close_path()
    ctx.set_source_rgb(*(GREEN if fresh else BROWN))
    ctx.fill_preserve()
    ctx.set_source_rgb(*BLUE)
    ctx.set_line_width(2.5 * s)
    ctx.stroke()
    ctx.set_source_rgb(*(DGREEN if fresh else (0.35, 0.27, 0.15)))
    ctx.set_line_width(5 * s)
    ctx.move_to(0, -L_ / 2)
    ctx.line_to(-6 * s, -L_ / 2 - 10 * s)
    ctx.stroke()
    ctx.restore()


def lemon(ctx, x, y, s, fresh=True, bites=0):
    ctx.save()
    ctx.translate(x, y)
    ctx.move_to(0, -48 * s)
    ctx.curve_to(40 * s, -40 * s, 42 * s, 38 * s, 0, 48 * s)
    ctx.curve_to(-42 * s, 38 * s, -40 * s, -40 * s, 0, -48 * s)
    ctx.close_path()
    ctx.set_source_rgb(*(LEMON if fresh else (0.72, 0.62, 0.3)))
    ctx.fill_preserve()
    ctx.set_source_rgb(*BLUE)
    ctx.set_line_width(3.5 * s)
    ctx.stroke()
    ctx.set_source_rgba(1, 1, 1, 0.55)
    ctx.arc(-12 * s, -16 * s, 8 * s, 0, 2 * math.pi)
    ctx.fill()
    for k in range(int(bites)):
        a = -0.6 + k * 0.9
        ctx.set_source_rgb(*PAPER)
        ctx.arc(34 * s * math.cos(a), 34 * s * math.sin(a), 16 * s, 0, 2 * math.pi)
        ctx.fill()
    ctx.restore()


def charm(ctx, x, y, s=1.0, swing=0.0, fresh=True, bites=0, nchili=7, glow=0.0, nail=True):
    """Nimbu-mirchi hanging from a nail at (x, y)."""
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(swing)
    if glow > 0:
        g = cairo.RadialGradient(0, 230 * s, 10, 0, 230 * s, 220 * s)
        g.add_color_stop_rgba(0, 1, 0.9, 0.3, 0.7 * glow)
        g.add_color_stop_rgba(1, 1, 0.9, 0.3, 0)
        ctx.set_source(g)
        ctx.arc(0, 230 * s, 220 * s, 0, 2 * math.pi)
        ctx.fill()
    top = 18 * s
    bottom = (60 + 7 * 34) * s
    ink(ctx, 3 * s, (0.95, 0.95, 0.92) if False else BLUE)
    ctx.move_to(0, 0)
    ctx.line_to(0, bottom + 10 * s)
    ctx.stroke()
    for k in range(7):
        if k < 7 - nchili:
            continue
        cy = top + 40 * s + k * 34 * s
        chilli(ctx, 0, cy, (1 if k % 2 else -1) * 1.15, s, fresh)
    lemon(ctx, 0, bottom + 55 * s, s, fresh, bites)
    if nail:
        ctx.set_source_rgb(*BLUE)
        ctx.arc(0, 0, 7 * s, 0, 2 * math.pi)
        ctx.fill()
    ctx.restore()


def swing_at(t, k=0.08, speed=2.2, ph=0.0):
    return k * math.sin(t * speed + ph)


def shopfront(ctx, x, y, w, h, frame, name="SHARMA STORES", keeper=True, t=0.0, ident=0, shutter=0.0):
    """Shop with awning, sign and open front. (x, y) = top-left of the sign."""
    wrect(ctx, x, y, w, 90, frame, fill=(1, 1, 1), ident=(ident, "sign"))
    text(ctx, name, x + w / 2, y + 47, 54, font="Lilita One", fill=BLUE)
    ay = y + 90
    n = 8
    for k in range(n):  # striped scalloped awning
        x0 = x + k * w / n
        ctx.set_source_rgb(*(HL if k % 2 else (1, 1, 1)))
        ctx.move_to(x0, ay)
        ctx.line_to(x0 + w / n, ay)
        ctx.line_to(x0 + w / n, ay + 70)
        ctx.arc(x0 + w / n / 2, ay + 70, w / n / 2, 0, math.pi)
        ctx.close_path()
        ctx.fill_preserve()
        ink(ctx, 4)
        ctx.stroke()
    oy = ay + 70
    wline(ctx, x, oy, x, GROUND, frame, ident=(ident, "l"))
    wline(ctx, x + w, oy, x + w, GROUND, frame, ident=(ident, "r"))
    for r in range(3):  # shelves with jars
        sy = oy + 80 + r * 95
        if sy > GROUND - 200:
            break
        wline(ctx, x + 30, sy, x + w - 30, sy, frame, w=4, ident=(ident, "s", r))
        for j in range(6):
            jx = x + 70 + j * (w - 140) / 5
            ctx.set_source_rgb(*((1, 0.75, 0.5), (0.7, 0.85, 1), (1, 0.9, 0.5))[(j + r) % 3])
            ctx.rectangle(jx - 22, sy - 52, 44, 52)
            ctx.fill_preserve()
            ink(ctx, 3)
            ctx.stroke()
    if keeper:
        S.draw(ctx, x + w * 0.76, GROUND - 40, 330, mix(POSES["stand"], POSES["wave"], 0.3 + 0.3 * math.sin(t * 2)),
               Face(mouth="smile", look=(-0.5, 0)), KEEPER, -1, frame, ident=(ident, "keeper"))
    wrect(ctx, x + 20, GROUND - 170, w - 40, 170, frame, fill=(0.93, 0.88, 0.8), ident=(ident, "counter"))
    if shutter > 0:
        ctx.set_source_rgb(0.75, 0.76, 0.8)
        sh = (GROUND - oy) * shutter
        ctx.rectangle(x, oy, w, sh)
        ctx.fill()
        ink(ctx, 3)
        for yy in np.arange(oy + 20, oy + sh, 24):
            ctx.move_to(x, yy)
            ctx.line_to(x + w, yy)
        ctx.stroke()
    return oy  # y of the top of the opening (where the charm hangs)


def door(ctx, x, y, w, h, frame, ident=0, window=True):
    wrect(ctx, x - 30, y - 30, w + 60, h + 30, frame, lw=7, ident=(ident, "frame"))
    wrect(ctx, x, y, w, h, frame, fill=(0.85, 0.62, 0.42), ident=(ident, "door"))
    for k in range(2):
        wrect(ctx, x + 30, y + 40 + k * (h / 2), w - 60, h / 2 - 70, frame, lw=4, ident=(ident, "pan", k))
    ctx.set_source_rgb(*BLUE)
    ctx.arc(x + w - 35, y + h / 2 + 10, 9, 0, 2 * math.pi)
    ctx.fill()


def truck_back(ctx, x, y, s, frame, t):
    w, h = 620 * s, 460 * s
    wrect(ctx, x, y, w, h, frame, fill=(0.98, 0.6, 0.25), ident="truck")
    for k in range(12):  # scalloped trim
        ctx.set_source_rgb(*((0.2, 0.55, 0.3), RED, HL)[k % 3])
        ctx.arc(x + (k + 0.5) * w / 12, y, w / 24, 0, math.pi)
        ctx.fill()
    ctx.set_source_rgb(1, 1, 1)
    ctx.rectangle(x + 40 * s, y + 60 * s, w - 80 * s, 220 * s)
    ctx.fill()
    text(ctx, "BURI NAZAR WALE", x + w / 2, y + 120 * s, 52 * s, font="Lilita One", fill=RED)
    text(ctx, "TERA MUH KALA", x + w / 2, y + 200 * s, 56 * s, font="Lilita One", fill=(0.1, 0.1, 0.12))
    text(ctx, "HORN OK PLEASE", x + w / 2, y + 340 * s, 46 * s, font="Lilita One", fill=(0.2, 0.45, 0.85))
    for sx in (x + 70 * s, x + w - 70 * s):
        ctx.set_source_rgb(0.15, 0.15, 0.18)
        ctx.arc(sx, y + h + 10 * s, 50 * s, 0, 2 * math.pi)
        ctx.fill()
    wrect(ctx, x - 20 * s, y + h - 20 * s, w + 40 * s, 30 * s, frame, fill=(0.3, 0.3, 0.35), ident="bumper")
    charm(ctx, x + w / 2, y + h + 10 * s, 0.45 * s, swing_at(t, 0.15, 3))


def car(ctx, x, y, s, frame, t, ident=0):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    ctx.move_to(-260, 40)
    ctx.line_to(-250, -40)
    ctx.line_to(-140, -60)
    ctx.line_to(-80, -140)
    ctx.line_to(110, -140)
    ctx.line_to(180, -60)
    ctx.line_to(260, -40)
    ctx.line_to(265, 40)
    ctx.close_path()
    ctx.set_source_rgb(0.85, 0.2, 0.25)
    ctx.fill_preserve()
    ink(ctx, 6)
    ctx.stroke()
    ctx.set_source_rgb(0.8, 0.9, 1)
    ctx.move_to(-60, -125)
    ctx.line_to(95, -125)
    ctx.line_to(150, -62)
    ctx.line_to(-115, -62)
    ctx.close_path()
    ctx.fill()
    for wx in (-150, 160):
        ctx.set_source_rgb(0.15, 0.15, 0.18)
        ctx.arc(wx, 40, 48, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.8, 0.8, 0.8)
        ctx.arc(wx, 40, 18, 0, 2 * math.pi)
        ctx.fill()
    # ribbon bow on the bonnet
    ctx.set_source_rgb(*HL)
    for sgn in (-1, 1):
        ctx.move_to(200, -55)
        ctx.line_to(200 + sgn * 40, -85)
        ctx.line_to(200 + sgn * 40, -25)
        ctx.close_path()
        ctx.fill()
    ctx.restore()
    charm(ctx, x + 245 * s, y - 20 * s, 0.32 * s, swing_at(t, 0.2, 3.5))


def phone(ctx, x, y, w, h, frame, k=1.0):
    if k <= 0.01:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(k, k)
    ctx.set_source_rgb(0.12, 0.12, 0.15)
    rr = 40
    ctx.new_sub_path()
    for (cx, cy, a0) in ((w / 2 - rr, -h / 2 + rr, -math.pi / 2), (w / 2 - rr, h / 2 - rr, 0), (-w / 2 + rr, h / 2 - rr, math.pi / 2), (-w / 2 + rr, -h / 2 + rr, math.pi)):
        ctx.arc(cx, cy, rr, a0, a0 + math.pi / 2)
    ctx.close_path()
    ctx.fill()
    ctx.set_source_rgb(0.93, 0.91, 0.86)
    ctx.rectangle(-w / 2 + 18, -h / 2 + 50, w - 36, h - 100)
    ctx.fill()
    ctx.set_source_rgb(0.1, 0.45, 0.35)
    ctx.rectangle(-w / 2 + 18, -h / 2 + 50, w - 36, 70)
    ctx.fill()
    text(ctx, "Family Group", -w / 2 + 50, -h / 2 + 86, 34, font="Lilita One", fill=(1, 1, 1), align="l")
    ctx.restore()


def mosquito(ctx, x, y, s, frame):
    ink(ctx, 3 * s)
    ctx.set_source_rgb(0.15, 0.15, 0.2)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    ctx.save()
    ctx.scale(18, 7)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.fill()
    flap = 0.6 + 0.4 * math.sin(frame * 2.5)
    ctx.set_source_rgba(0.6, 0.75, 0.95, 0.7)
    for sgn in (-1, 1):
        ctx.save()
        ctx.translate(-2, -4)
        ctx.rotate(sgn * 0.5 * flap - math.pi / 2)
        ctx.scale(22, 8)
        ctx.arc(1, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.fill()
    ctx.set_source_rgb(0.15, 0.15, 0.2)
    ctx.set_line_width(2)
    for k in range(3):
        ctx.move_to(-6 + k * 6, 4)
        ctx.line_to(-12 + k * 8, 20)
    ctx.move_to(18, 0)
    ctx.line_to(34, 4)
    ctx.stroke()
    ctx.restore()


def cloud(ctx, x, y, s, t, mood="hungry", alpha=1.0):
    """Alakshmi shown as a dark ink cloud with eyes."""
    if alpha <= 0.01:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    ctx.push_group()
    ctx.set_source_rgb(0.18, 0.17, 0.25)
    for k in range(9):
        a = k / 9 * 2 * math.pi + 0.2 * math.sin(t * 2 + k)
        ctx.arc(math.cos(a) * 70, math.sin(a) * 45, 55 + 8 * math.sin(t * 3 + k * 1.7), 0, 2 * math.pi)
        ctx.fill()
    ctx.arc(0, 0, 80, 0, 2 * math.pi)
    ctx.fill()
    for sgn in (-1, 1):
        ctx.set_source_rgb(1, 1, 1)
        ctx.arc(sgn * 30, -10, 18, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.1, 0.1, 0.1)
        ctx.arc(sgn * 30 - 6, -8, 8, 0, 2 * math.pi)
        ctx.fill()
    ctx.set_source_rgb(1, 1, 1)
    ctx.set_line_width(6)
    if mood == "happy":
        ctx.arc(0, 18, 26, 0.2, math.pi - 0.2)
        ctx.stroke()
    elif mood == "chomp":
        ctx.arc(0, 25, 18 + 8 * abs(math.sin(t * 14)), 0, 2 * math.pi)
        ctx.fill()
    else:
        ctx.move_to(-22, 28)
        ctx.line_to(22, 28)
        ctx.stroke()
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def lotus(ctx, x, y, s, t):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    g = cairo.RadialGradient(0, -40, 10, 0, -40, 230)
    g.add_color_stop_rgba(0, 1, 0.9, 0.4, 0.55 + 0.1 * math.sin(t * 2))
    g.add_color_stop_rgba(1, 1, 0.9, 0.4, 0)
    ctx.set_source(g)
    ctx.arc(0, -40, 230, 0, 2 * math.pi)
    ctx.fill()
    for k, a in enumerate((-1.1, -0.55, 0, 0.55, 1.1)):
        ctx.save()
        ctx.rotate(a)
        ctx.move_to(0, 0)
        ctx.curve_to(45, -50, 30, -120, 0, -150)
        ctx.curve_to(-30, -120, -45, -50, 0, 0)
        ctx.set_source_rgb(1.0, 0.62, 0.72) if k % 2 == 0 else ctx.set_source_rgb(0.98, 0.5, 0.62)
        ctx.fill_preserve()
        ink(ctx, 4)
        ctx.stroke()
        ctx.restore()
    ctx.restore()


def laddoos(ctx, x, y, s):
    rows = [3, 2, 1]
    for r, n in enumerate(rows):
        for k in range(n):
            cx = x + (k - (n - 1) / 2) * 52 * s
            cy = y - r * 44 * s
            ctx.set_source_rgb(1.0, 0.68, 0.2)
            ctx.arc(cx, cy, 25 * s, 0, 2 * math.pi)
            ctx.fill_preserve()
            ink(ctx, 3 * s)
            ctx.stroke()


def nazar_bead(ctx, x, y, r, t):
    for rr, c in ((1.0, (0.1, 0.25, 0.7)), (0.72, (1, 1, 1)), (0.5, (0.45, 0.75, 0.95)), (0.25, (0.05, 0.05, 0.1))):
        ctx.set_source_rgb(*c)
        ctx.arc(x, y, r * rr, 0, 2 * math.pi)
        ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.5)
    ctx.arc(x - r * 0.35, y - r * 0.4, r * 0.15, 0, 2 * math.pi)
    ctx.fill()
    ink(ctx, 5)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.stroke()


def big_eye(ctx, x, y, s, t, frame):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    ctx.move_to(-120, 0)
    ctx.curve_to(-60, -80, 60, -80, 120, 0)
    ctx.curve_to(60, 80, -60, 80, -120, 0)
    ctx.close_path()
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill_preserve()
    ink(ctx, 6)
    ctx.stroke()
    lx = 20 * math.sin(t * 1.5)
    ctx.set_source_rgb(0.35, 0.55, 0.3)
    ctx.arc(lx, 0, 42, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgb(0.05, 0.05, 0.1)
    ctx.arc(lx, 0, 20, 0, 2 * math.pi)
    ctx.fill()
    ink(ctx, 6)
    for k in range(5):
        a = math.pi + 0.35 + k * 0.6
        ctx.move_to(130 * math.cos(a) * 0.95, -55 + 0 * k)
    ctx.restore()


def checkmark(ctx, x, y, s, p, color=GREEN):
    if p <= 0:
        return
    ink(ctx, 10, color)
    pts = [(x - 25 * s, y), (x - 5 * s, y + 22 * s), (x + 32 * s, y - 28 * s)]
    ctx.move_to(*pts[0])
    if p < 0.4:
        f = p / 0.4
        ctx.line_to(pts[0][0] + (pts[1][0] - pts[0][0]) * f, pts[0][1] + (pts[1][1] - pts[0][1]) * f)
    else:
        f = (p - 0.4) / 0.6
        ctx.line_to(*pts[1])
        ctx.line_to(pts[1][0] + (pts[2][0] - pts[1][0]) * f, pts[1][1] + (pts[2][1] - pts[1][1]) * f)
    ctx.stroke()


def cross(ctx, x, y, s, p, color=RED):
    if p <= 0:
        return
    ink(ctx, 10, color)
    for k, (a, b) in enumerate((((-1, -1), (1, 1)), ((1, -1), (-1, 1)))):
        f = min(1, max(0, p * 2 - k))
        if f > 0:
            ctx.move_to(x + a[0] * 28 * s, y + a[1] * 28 * s)
            ctx.line_to(x + (a[0] + (b[0] - a[0]) * f) * 28 * s, y + (a[1] + (b[1] - a[1]) * f) * 28 * s)
            ctx.stroke()


def bubble(ctx, cx, cy, w, h, lines_, tail, k=1.0, size=40):
    if k <= 0.01:
        return
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(k, k)
    ink(ctx, 5)
    for f, rr in ((0.9, 10), (0.72, 16)):
        ctx.arc((tail[0] - cx) * f, (tail[1] - cy) * f, rr, 0, 2 * math.pi)
        ctx.set_source_rgb(1, 1, 1)
        ctx.fill_preserve()
        ink(ctx, 5)
        ctx.stroke()
    ctx.save()
    ctx.scale(w / 2, h / 2)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill_preserve()
    ink(ctx, 5)
    ctx.stroke()
    n = len(lines_)
    for i, ln in enumerate(lines_):
        text(ctx, ln, 0, (i - (n - 1) / 2) * size * 1.1, size)
    ctx.restore()


def ground(ctx, frame, y=GROUND, x0=-300, x1=W + 300):
    wline(ctx, x0, y, x1, y, frame, w=6, ident="ground")


# ---------------------------------------------------------------- scenes


def s_street(ctx, lt, d, b, frame):
    notebook(ctx)
    z = 1 + 1.2 * ease(seg(lt, b[1] - 0.35, b[1] + 0.5))
    cx, cy = 1180 * ease(seg(lt, b[1] - 0.35, b[1] + 0.5)) + 960 * (1 - ease(seg(lt, b[1] - 0.35, b[1] + 0.5))), 540 + 20 * ease(seg(lt, b[1] - 0.35, b[1] + 0.5))
    ctx.save()
    camera(ctx, z, cx, cy)
    ground(ctx, frame)
    oy = shopfront(ctx, 900, 170, 560, 0, frame, t=lt)
    charm(ctx, 1180, oy + 6, 0.62, swing_at(lt, 0.1))
    walk_t = 2.4
    x = -120 + 640 * seg(lt, 0, walk_t)
    pose = walk(lt * 9) if lt < walk_t else mix(POSES["stand"], POSES["point"], seg(lt, walk_t, walk_t + 0.3))
    S.draw(ctx, x, GROUND, 400, pose, Face(mouth="smile", look=(1, -0.5)), HOST, 1, frame, ident="host")
    t1 = b[1] - b[0] if len(b) > 1 else 99
    rel = lt - (b[1] - b[0]) if len(b) > 1 else -1
    s = 1 / max(1, z)
    if rel > 0:
        label(ctx, "1 lemon", 1060, oy + 235, 40, rel, 0.1, hl=True, align="r")
        arrow(ctx, 1068, oy + 235, 1138, oy + 230, seg(rel, 0.15, 0.4), frame, w=4)
        label(ctx, "a few green chillies", 1240, oy + 95, 40, rel, 0.9, hl=True, align="l")
        arrow(ctx, 1235, oy + 95, 1200, oy + 110, seg(rel, 0.95, 1.2), frame, w=4)
        label(ctx, "1 thread", 1250, oy + 15, 40, rel, 2.0, hl=True, align="l")
        arrow(ctx, 1242, oy + 15, 1186, oy + 22, seg(rel, 2.05, 2.3), frame, w=4)
    ctx.restore()


def s_everywhere(ctx, lt, d, b, frame):
    notebook(ctx)
    panels = [(210, 150, "shops"), (1000, 150, "homes"), (210, 560, "trucks"), (1000, 560, "new cars")]
    times = [0.15, 1.05, 1.9, 2.75]
    for i, ((px, py, name), t0) in enumerate(zip(panels, times)):
        k = pop(lt, t0, 0.25)
        if k <= 0.01:
            continue
        ctx.save()
        ctx.translate(px + 355, py + 190)
        ctx.scale(k, k)
        ctx.translate(-(px + 355), -(py + 190))
        wrect(ctx, px, py, 710, 380, frame, lw=7, fill=(1, 1, 1), ident=("panel", i))
        ctx.save()
        ctx.rectangle(px, py, 710, 380)
        ctx.clip()
        ctx.translate(px, py)
        if i == 0:
            ctx.save()
            ctx.scale(0.55, 0.55)
            ctx.translate(120, -100)
            oy = shopfront(ctx, 100, 120, 560, 0, frame, t=lt, ident="p0")
            charm(ctx, 380, oy + 6, 0.7, swing_at(lt, 0.1))
            ctx.restore()
        elif i == 1:
            ctx.save()
            ctx.scale(0.6, 0.6)
            door(ctx, 450, 90, 260, 520, frame, ident="p1")
            charm(ctx, 580, 70, 0.55, swing_at(lt, 0.1, 2.4, 1))
            wline(ctx, 0, 615, 1200, 615, frame, ident="p1g")
            ctx.restore()
        elif i == 2:
            ctx.save()
            ctx.scale(0.62, 0.62)
            truck_back(ctx, 260, 60, 0.95, frame, lt)
            ctx.restore()
        else:
            car(ctx, 330, 250, 0.95, frame, lt)
        ctx.restore()
        text(ctx, name, px + 40, py + 345, 50, align="l", fill=BLUE)
        ctx.restore()


def s_question(ctx, lt, d, b, frame):
    notebook(ctx)
    ground(ctx, frame)
    S.draw(ctx, 700, GROUND, 520, POSES["shrug"], Face(mouth="o", brows="worried", look=(1 if lt > 2.0 else 0, -0.3)),
           HOST, 1, frame, ident="host")
    for i, (qx, qy, sz) in enumerate(((520, 300, 150), (880, 250, 110), (640, 160, 90))):
        text(ctx, "?", qx, qy + 8 * math.sin(lt * 3 + i), sz, font="Lilita One", fill=BLUE, scale=pop(lt, 0.1 + i * 0.25))
    k = pop(lt, 1.9, 0.3)
    phone(ctx, 1380, 520, 420, 760, frame, k)
    if k > 0.5:
        ctx.save()
        bx, by = 1200, 300
        ctx.set_source_rgb(0.86, 0.97, 0.8)
        ctx.rectangle(bx, by, 360, 250)
        ctx.fill()
        text(ctx, "Forwarded many times", bx + 18, by + 30, 26, fill=(0.4, 0.4, 0.4), align="l")
        text(ctx, "SCIENTIFIC REASON", bx + 18, by + 80, 36, font="Lilita One", fill=(0.15, 0.15, 0.15), align="l")
        text(ctx, "behind nimbu mirchi!!!", bx + 18, by + 125, 34, fill=(0.15, 0.15, 0.15), align="l")
        ink(ctx, 6, (0.6, 0.6, 0.6))
        for r in range(3):
            ctx.move_to(bx + 18, by + 170 + r * 26)
            ctx.line_to(bx + 330 - r * 60, by + 170 + r * 26)
        ctx.stroke()
        ctx.restore()


def s_title(ctx, lt, d, b, frame):
    notebook(ctx)
    charm(ctx, 1500, 150, 1.35, swing_at(lt, 0.12, 2.5))
    text(ctx, "WHY LEMON", 300, 380, 170, font="Lilita One", fill=BLUE, align="l", scale=pop(lt, 0.05, 0.3))
    w = text_w(ctx, "& CHILLI?", 190, "Lilita One")
    highlight(ctx, 290, 600, w + 30, 150, seg(lt, 0.5, 0.95))
    text(ctx, "& CHILLI?", 300, 590, 190, font="Lilita One", fill=BLUE, align="l", scale=pop(lt, 0.25, 0.3))
    text(ctx, "the honest answer", 310, 760, 64, fill=RED, align="l", scale=pop(lt, 0.8, 0.3), rot=-0.03)


def s_recipe(ctx, lt, d, b, frame):
    notebook(ctx)
    ctx.save()
    ctx.translate(560, 540)
    ctx.rotate(-0.04)
    ctx.set_source_rgba(0, 0, 0, 0.1)
    ctx.rectangle(-370, -300, 760, 620)
    ctx.fill()
    ctx.set_source_rgb(1, 1, 1)
    ctx.rectangle(-380, -310, 760, 620)
    ctx.fill()
    ctx.set_source_rgb(*MARGIN)
    ctx.set_line_width(3)
    ctx.move_to(-380, -200)
    ctx.line_to(380, -200)
    ctx.stroke()
    ctx.set_source_rgb(*RULE)
    ctx.set_line_width(2)
    for y in range(-130, 300, 70):
        ctx.move_to(-380, y)
        ctx.line_to(380, y)
    ctx.stroke()
    text(ctx, "RECIPE: Nimbu Mirchi", 0, -255, 58, font="Lilita One", fill=BLUE)
    rel = lt - (b[1] - b[0]) if len(b) > 1 else -1
    items = [("1 lemon", 0.2), ("7 green chillies", 1.0), ("1 cotton string", 2.3), ("Serves: 1 doorway", 3.2)]
    for i, (s_, t0) in enumerate(items):
        text(ctx, s_, -320, -95 + i * 70, 50, align="l", scale=pop(rel, t0))
    ctx.restore()
    # assemble the charm on the right
    cx, top = 1450, 170
    n = int(7 * seg(rel, 1.0, 2.6)) if rel > 0 else 0
    lem = rel > 0.2
    ink(ctx, 3)
    ctx.move_to(cx, top)
    ctx.line_to(cx, top + 330 * min(1, max(0.1, seg(rel, 0, 2.6))) + 10)
    ctx.stroke()
    for k in range(n):
        chilli(ctx, cx, top + 25 + k * 34, (1 if k % 2 else -1) * 1.15, 1.0)
        text(ctx, str(k + 1), cx + (110 if k % 2 else -110), top + 25 + k * 34, 36, font="Lilita One", fill=RED)
    if lem:
        lemon(ctx, cx, top + 60 + 7 * 34 + 55 - 120 * (1 - ease(seg(rel, 0.2, 0.5))), 1.0)
    ctx.set_source_rgb(*BLUE)
    ctx.arc(cx, top, 7, 0, 2 * math.pi)
    ctx.fill()


def s_saturday(ctx, lt, d, b, frame):
    notebook(ctx)
    rel = lt - (b[1] - b[0]) if len(b) > 1 else -1
    zt = ease(seg(rel, -0.2, 0.8))
    ctx.save()
    camera(ctx, 1.6 - 0.6 * zt, 700 + 260 * zt, 520 + 20 * zt)
    ground(ctx, frame)
    names = ["SHARMA STORES", "GUPTA SWEETS", "MOBILE POINT"]
    vx = W + 200 - 2300 * seg(rel, 0.2, 4.6)
    for i, nm in enumerate(names):
        x0 = 120 + i * 600
        oy = shopfront(ctx, x0, 210, 520, 0, frame, name=nm, keeper=(i == 0), t=lt, ident=("shop", i))
        hx = x0 + 260
        if i == 0:
            swap = seg(lt, 2.0, 2.6)
            if swap < 0.5:
                charm(ctx, hx, oy + 6, 0.55, swing_at(lt, 0.05), fresh=False)
                if swap > 0:
                    pass
            else:
                charm(ctx, hx, oy + 6 - 200 * (1 - ease((swap - 0.5) * 2)), 0.55, swing_at(lt, 0.1), fresh=True)
            if 0 < swap < 1:  # old one falls
                charm(ctx, hx + 60 * swap, oy + 6 + 500 * swap * swap, 0.55, swap * 2, fresh=False, nail=False)
        else:
            fresh = vx < hx
            charm(ctx, hx, oy + 6, 0.55, swing_at(lt + i, 0.1 if fresh else 0.03), fresh=fresh)
    if rel > 0:  # vendor with a pole of charms
        pose = walk(lt * 8, POSES["stand"])
        j = S.draw(ctx, vx, GROUND, 380, pose, Face(mouth="grin", look=(-1, 0)), L(hair="cap", accent=RED, shirt=(0.6, 0.85, 0.6)),
                   -1, frame, ident="vendor")
        sx, sy = j["shoulder"]
        ink(ctx, 8, BROWN)
        ctx.move_to(sx - 220, sy - 20)
        ctx.line_to(sx + 220, sy - 20)
        ctx.stroke()
        for k_ in range(4):
            px = sx - 200 + k_ * 130
            charm(ctx, px, sy - 20, 0.36, swing_at(lt, 0.18, 6, k_))
    ctx.restore()
    if rel > 0:
        bubble(ctx, min(max(vx, 300), 1620), 175, 360, 110, ["Nimbu mirchi!"], (min(max(vx, 300), 1620) + 20, 290),
               pop(rel, 0.8), size=48)
    # calendar page (screen space)
    k = pop(lt, 0.3) * (1 - seg(rel, -0.4, 0.0))
    if k > 0.01:
        ctx.save()
        ctx.translate(330, 330)
        ctx.scale(k * 0.9, k * 0.9)
        wrect(ctx, -170, -150, 340, 300, frame, fill=(1, 1, 1), ident="cal")
        ctx.set_source_rgb(*RED)
        ctx.rectangle(-170, -150, 340, 70)
        ctx.fill()
        text(ctx, "THIS WEEK", 0, -115, 40, font="Lilita One", fill=(1, 1, 1))
        days = ["M", "T", "W", "T", "F", "S", "S"]
        for i, dd in enumerate(days):
            text(ctx, dd, -135 + i * 45, -30, 40)
        p = seg(lt, 0.8, 1.6)
        if p > 0:
            ink(ctx, 6, RED)
            ctx.arc(-135 + 5 * 45, -30, 32, -math.pi / 2, -math.pi / 2 + 2 * math.pi * p)
            ctx.stroke()
        text(ctx, "fresh one!", 0, 70, 44, fill=RED, scale=pop(lt, 1.6))
        ctx.restore()


def s_legend(ctx, lt, d, b, frame):
    notebook(ctx)
    r1 = lt - (b[1] - b[0]) if len(b) > 1 else -1
    r2 = lt - (b[2] - b[0]) if len(b) > 2 else -1
    text(ctx, "THE LEGEND", 960, 210, 110, font="Lilita One", fill=BLUE, scale=pop(lt, 0.05),
         alpha=1 - seg(r1, -0.3, 0.1) * 0.0)
    for y in range(300, 980, 40):  # dashed divider
        if r1 > 0:
            wline(ctx, 960, y, 960, y + 20, frame, w=4, ident=("div", y), amp=0)
    if r1 > 0:
        k = pop(r1, 0.0, 0.3)
        ctx.save()
        ctx.translate(500, 560)
        ctx.scale(k, k)
        ctx.translate(-500, -560)
        lotus(ctx, 420, 600, 1.15, lt)
        laddoos(ctx, 680, 640, 1.0)
        ctx.restore()
        label(ctx, "LAKSHMI", 520, 760, 80, r1, 0.2, font="Lilita One")
        label(ctx, "goddess of wealth", 520, 830, 48, r1, 0.6)
        label(ctx, "loves: SWEET", 520, 905, 56, r1, 1.6, hl=True)
    if r2 > 0:
        cloud(ctx, 1440, 540, 1.3, lt, "hungry", alpha=ease(seg(r2, 0, 0.4)))
        lemon(ctx, 1225, 470, 0.8 * pop(r2, 2.6))
        chilli(ctx, 1655, 470, 0.6, 1.2 * pop(r2, 2.9))
        label(ctx, "ALAKSHMI", 1440, 760, 80, r2, 0.6, font="Lilita One")
        label(ctx, "goddess of misfortune", 1440, 830, 48, r2, 1.2)
        label(ctx, "loves: SOUR + SPICY", 1440, 905, 56, r2, 2.6, hl=True)


def s_visit(ctx, lt, d, b, frame):
    notebook(ctx)
    r1 = lt - (b[1] - b[0]) if len(b) > 1 else -1
    ground(ctx, frame, 960)
    ctx.save()
    ctx.translate(0, 60)
    door(ctx, 760, 180, 400, 720, frame, ident="hdoor")
    # host peeking through a small window
    wrect(ctx, 860, 470, 200, 130, frame, fill=(0.85, 0.93, 1), ident="win")
    ctx.save()
    ctx.rectangle(860, 470, 200, 130)
    ctx.clip()
    ctx.set_source_rgb(*PAPER)
    ctx.arc(960, 555, 52, 0, 2 * math.pi)
    ctx.fill_preserve()
    ink(ctx, 6)
    ctx.stroke()
    ctx.set_source_rgb(*BLUE)
    for sgn in (-1, 1):
        ctx.arc(960 + sgn * 18 + 10, 545, 7, 0, 2 * math.pi)
        ctx.fill()
    ctx.restore()
    # charm and cloud
    bites = min(3, int(seg(lt, 3.0, 4.6) * 4))
    nch = 7 - int(7 * seg(lt, 2.3, 4.4))
    happy = lt > 4.6
    charm(ctx, 960, 150, 0.7, swing_at(lt, 0.06 if nch else 0.02), bites=bites, nchili=nch,
          fresh=True)
    if r1 < 0 or r1 < 0.3:
        cx = 1700 - 530 * ease(seg(lt, 0.0, 2.0))
        cy = 390 + 20 * math.sin(lt * 2)
        alpha = 1.0
    else:
        p = ease(seg(r1, 0.6, 2.4))
        cx, cy = 1170 + 700 * p, 390 - 250 * p
        alpha = 1 - seg(r1, 1.8, 2.6)
    mood = "happy" if happy else ("chomp" if 2.3 < lt < 4.6 else "hungry")
    cloud(ctx, cx, cy, 1.0, lt, mood, alpha)
    if 2.4 < lt < 4.6:
        text(ctx, "chomp", cx - 60, cy - 150 - 10 * math.sin(lt * 9), 54, font="Lilita One", fill=RED, rot=-0.15)
    if r1 > 0:
        text(ctx, "burp!", cx + 40, cy - 140, 56, font="Lilita One", fill=BLUE, scale=pop(r1, 0.1), alpha=1 - seg(r1, 1.0, 1.4))
        label(ctx, "door stays shut", 1400, 820, 54, r1, 1.6, hl=True)
    ctx.restore()


def s_nazar(ctx, lt, d, b, frame):
    notebook(ctx)
    r1 = lt - (b[1] - b[0]) if len(b) > 1 else -1
    if r1 < 0:
        ground(ctx, frame)
        oy = shopfront(ctx, 1150, 170, 560, 0, frame, t=lt)
        glow = seg(lt, 2.0, 3.0)
        charm(ctx, 1430, oy + 6, 0.62, swing_at(lt, 0.08), glow=glow)
        big_eye(ctx, 460, 300, 0.9 * pop(lt, 0.4), lt, frame)
        label(ctx, "NAZAR = the evil eye", 460, 450, 60, lt, 0.9, hl=True, font="Lilita One")
        for i in range(3):
            x = -200 + 900 * seg(lt, 1.5 + i * 0.7, 5.8) + i * 40
            S.draw(ctx, x, GROUND, 330 + i * 15, walk(lt * 8 + i), Face(eyes="closed", mouth="flat", brows="worried", look=(1, 0)),
                   L(hair=["bun", "cap", "spiky"][i], accent=RED), 1, frame, ident=("pass", i))
            if 0 < x < 1100:  # jealous glare into the charm
                ink(ctx, 4, RED)
                ctx.set_dash([14, 12], -frame * 3)
                ctx.move_to(x + 30, GROUND - 300 - i * 12)
                ctx.curve_to(x + 300, GROUND - 600, 1250, oy + 100, 1430, oy + 250)
                ctx.stroke()
                ctx.set_dash([])
    else:
        ground(ctx, frame)
        charm(ctx, 1100, GROUND - 22, 0.5, -math.pi / 2 + 0.1, fresh=False, nail=False)
        for k in range(4):  # bad-luck wisps
            ph = r1 * 1.5 + k
            yy = GROUND - 60 - (ph % 1.5) * 120
            ink(ctx, 4, (0.35, 0.3, 0.45))
            ctx.move_to(1000 + k * 60, yy)
            ctx.curve_to(1020 + k * 60, yy - 30, 980 + k * 60, yy - 60, 1000 + k * 60, yy - 90)
            ctx.stroke()
        step = 1.9
        x = 300 + 560 * seg(r1, 0, step)
        froze = r1 > step
        pose = walk(r1 * 9) if not froze else POSES["flail"]
        S.draw(ctx, x, GROUND, 420, pose, Face(eyes="wide" if froze else "dot", mouth="o" if froze else "smile", look=(1, 1)),
               HOST, 1, frame, ident="host")
        if froze:
            cross(ctx, 1100, GROUND - 160, 2.2, seg(r1, step + 0.1, step + 0.5))
            label(ctx, "never step on an old one!", 960, 260, 70, r1, step + 0.4, hl=True, font="Lilita One")


def s_forward(ctx, lt, d, b, frame):
    notebook(ctx)
    r1 = lt - (b[1] - b[0]) if len(b) > 1 else -1
    ground(ctx, frame)
    S.draw(ctx, 330, GROUND, 460, POSES["think"], Face(brows="up", mouth="flat", look=(1, -0.2)), HOST, 1, frame, ident="host")
    k = pop(lt, 0.05, 0.3)
    phone(ctx, 820, 520, 520, 860, frame, k)
    if k > 0.6:
        bx, by = 600, 220
        ctx.set_source_rgb(0.86, 0.97, 0.8)
        ctx.rectangle(bx, by, 440, 560)
        ctx.fill()
        text(ctx, "Forwarded many times", bx + 20, by + 34, 28, fill=(0.4, 0.4, 0.4), align="l")
        lines_ = [("SCIENTIFIC REASON", "Lilita One", 40), ("behind nimbu mirchi!!!", "Patrick Hand", 36),
                  ("Cotton thread absorbs", "Patrick Hand", 34), ("citric acid + capsaicin.", "Patrick Hand", 34),
                  ("The smell keeps", "Patrick Hand", 34), ("insects AWAY!!", "Patrick Hand", 34),
                  ("Our ancestors were", "Patrick Hand", 34), ("SCIENTISTS!!!", "Lilita One", 38)]
        for i, (s_, f, sz) in enumerate(lines_):
            text(ctx, s_, bx + 20, by + 90 + i * 56, sz, font=f, fill=(0.15, 0.15, 0.15), align="l",
                 alpha=seg(lt, 0.3 + i * 0.12, 0.4 + i * 0.12))
    if r1 > 0:  # the claimed mechanism, as a diagram
        cx = 1480
        charm(ctx, cx, 180, 0.6, swing_at(lt, 0.04))
        for k_ in range(3):
            p = (r1 * 0.6 + k_ / 3) % 1
            ink(ctx, 4, (0.4, 0.65, 0.3))
            yy = 350 + k_ * 70
            ctx.move_to(cx + 60, yy)
            for s_ in range(6):
                ctx.line_to(cx + 60 + 40 * s_ + 120 * p, yy + (12 if s_ % 2 else -12))
            ctx.stroke()
        label(ctx, "citric acid", 1680, 300, 44, r1, 0.9, hl=True)
        label(ctx, "capsaicin", 1680, 380, 44, r1, 1.6, hl=True)
        for i in range(4):
            mx = 1700 + 300 * seg(r1, 3.4, 5.5) + i * 30
            mosquito(ctx, mx, 520 + i * 60 + 10 * math.sin(frame * 0.4 + i), 1.4, frame)
        label(ctx, "bugs flee??", 1690, 820, 50, r1, 3.6, color=RED)


def s_verdict(ctx, lt, d, b, frame):
    notebook(ctx)
    r1 = lt - (b[1] - b[0]) if len(b) > 1 else -1
    if r1 < 0:
        cx, cy, R = 960, 640, 300
        ink(ctx, 8)
        ctx.arc(cx, cy, R, math.pi, 2 * math.pi)
        ctx.stroke()
        for k in range(11):
            a = math.pi + k * math.pi / 10
            ctx.move_to(cx + (R - 30) * math.cos(a), cy + (R - 30) * math.sin(a))
            ctx.line_to(cx + R * math.cos(a), cy + R * math.sin(a))
        ctx.stroke()
        text(ctx, "none", cx - R + 20, cy + 50, 44)
        text(ctx, "proven", cx + R - 20, cy + 50, 44)
        text(ctx, "EVIDENCE METER", cx, cy - R - 70, 70, font="Lilita One")
        v = 0.75 * seg(lt, 0.2, 0.8) - 0.72 * ease(seg(lt, 0.9, 1.9))
        a = math.pi + math.pi * max(0.03, v) + 0.03 * math.sin(frame * 0.9) * seg(lt, 1.9, 2.2)
        ink(ctx, 10, RED)
        ctx.move_to(cx, cy)
        ctx.line_to(cx + (R - 50) * math.cos(a), cy + (R - 50) * math.sin(a))
        ctx.stroke()
        ctx.set_source_rgb(*BLUE)
        ctx.arc(cx, cy, 20, 0, 2 * math.pi)
        ctx.fill()
        stamp(ctx, "NO REAL EVIDENCE", cx, cy - 80, 90, lt, 2.0)
    else:
        ground(ctx, frame)
        oy = shopfront(ctx, 820, 170, 560, 0, frame, t=lt)
        charm(ctx, 1100, oy + 6, 0.62, swing_at(lt, 0.08))
        S.draw(ctx, 380, GROUND, 440, POSES["proud"], Face(mouth="flat", eyes="dot", look=(1, -0.6)), HOST, 1, frame, ident="host")
        p = seg(r1, 0.3, 3.8)
        mx = 1800 - 800 * p
        my = 300 + 150 * math.sin(p * 9) + 120 * p
        mosquito(ctx, mx, my, 2.2, frame)
        if 0.3 < r1 < 3.8:
            text(ctx, "bzzz", mx + 40, my - 60, 44, fill=(0.4, 0.4, 0.4), rot=-0.1)
        k = pop(r1, 3.4)
        if k > 0.01:
            wrect(ctx, 1460, 640, 380, 170, frame, fill=(1, 1, 1), ident="score")
            text(ctx, "MOSQUITO  1", 1650, 690, 52, font="Lilita One", fill=RED, scale=k)
            text(ctx, "LEMON  0", 1650, 760, 52, font="Lilita One", fill=BLUE, scale=k)


def s_world(ctx, lt, d, b, frame):
    notebook(ctx)
    r1 = lt - (b[1] - b[0]) if len(b) > 1 else -1
    r2 = lt - (b[2] - b[0]) if len(b) > 2 else -1
    if r1 < 0:
        ground(ctx, frame)
        S.draw(ctx, 960, GROUND, 520, POSES["think"], Face(brows="up", mouth="flat", look=(-1, -1)), HOST, 1, frame, ident="host")
        bubble(ctx, 1260, 300, 300, 160, ["hmm..."], (1010, GROUND - 560), pop(lt, 0.2), size=54)
        return
    k = pop(r1, 0.0, 0.3)
    nazar_bead(ctx, 500, 470, 190 * k, lt)
    label(ctx, "Turkey: the blue glass eye", 500, 760, 54, r1, 1.2, hl=True)
    if r2 > 0:
        kk = pop(r2, 0.0, 0.3)
        ctx.save()
        ctx.translate(1420, 520)
        ctx.scale(kk, kk)
        ctx.translate(-1420, -520)
        truck_back(ctx, 1130, 240, 0.95, frame, lt)
        ctx.restore()
        label(ctx, "India: truck art", 1420, 880, 54, r2, 1.0, hl=True)
        label(ctx, "(\"evil-eyed one, may your face go black\")", 1420, 950, 38, r2, 2.2, color=RED)


def s_brain(ctx, lt, d, b, frame):
    notebook(ctx)
    ground(ctx, frame)
    cyc = int(lt / 0.8) % 3
    pose = [POSES["wave"], POSES["celebrate"], POSES["proud"]][cyc] if lt > 1.5 else POSES["stand"]
    S.draw(ctx, 520, GROUND, 480, pose, Face(eyes="closed" if lt > 1.5 else "dot", mouth="smile" if lt > 3.5 else "flat",
                                              brows="" if lt > 3.5 else "worried"), HOST, 1, frame, ident="host")
    label(ctx, "a made-up ritual", 520, 260, 56, lt, 1.6, hl=True)
    # anxiety meter
    x0, y0, h = 1300, 220, 600
    wrect(ctx, x0, y0, 140, h, frame, fill=(1, 1, 1), ident="meter")
    level = 0.82 - 0.38 * ease(seg(lt, 2.2, 5.2))
    ctx.set_source_rgb(*RED)
    ctx.rectangle(x0 + 10, y0 + h - h * level, 120, h * level - 10)
    ctx.fill()
    text(ctx, "ANXIETY", x0 + 70, y0 - 50, 60, font="Lilita One")
    text(ctx, f"{round(level * 100)}%", x0 + 260, y0 + h - h * level, 60, font="Lilita One", fill=RED)
    k = pop(lt, 4.2)
    if k > 0.01:
        ctx.save()
        ctx.translate(1660, 820)
        ctx.rotate(0.06)
        ctx.scale(k, k)
        ctx.set_source_rgb(1.0, 0.9, 0.45)
        ctx.rectangle(-170, -70, 340, 140)
        ctx.fill()
        text(ctx, "Brooks et al., 2016", 0, -20, 40)
        text(ctx, "Harvard / Wharton", 0, 30, 34)
        ctx.restore()


def s_shop(ctx, lt, d, b, frame):
    r1 = lt - (b[1] - b[0]) if len(b) > 1 else -1
    notebook(ctx)
    sun = ease(seg(lt, 0, 3.5))
    ctx.set_source_rgba(1, 0.75, 0.3, 0.55)
    ctx.arc(1560, GROUND - 40 - 420 * sun, 140, 0, 2 * math.pi)
    ctx.fill()
    ground(ctx, frame)
    oy = shopfront(ctx, 520, 170, 620, 0, frame, name="KUMAR TEA STALL", keeper=False, t=lt, shutter=1 - ease(seg(lt, 0.4, 2.4)))
    # savings jar on the counter
    if lt > 2.4:
        wrect(ctx, 900, GROUND - 260, 110, 90, frame, fill=(0.85, 0.95, 1), ident="jar")
        text(ctx, "SAVINGS", 955, GROUND - 285, 30, font="Lilita One", fill=BLUE)
    hang = r1 > 2.6
    pose = POSES["phone"] if r1 < 0 else (mix(POSES["stand"], POSES["wave"], seg(r1, 2.0, 2.6)) if not hang else POSES["proud"])
    worried = not (r1 > 3.2)
    S.draw(ctx, 380, GROUND, 440, pose, Face(brows="worried" if worried else "", mouth="wobble" if worried else "smile",
                                              look=(1, -0.5)), KEEPER, 1, frame, ident="keeper")
    if r1 > 0:
        sz = 1 - 0.35 * ease(seg(r1, 2.8, 3.6))
        bubble(ctx, 360, 290, 480 * sz, 230 * sz, ["rent?  customers?", "loan?  rain?"], (380, GROUND - 470), pop(r1, 0.2) * 1.0, size=44 * sz)
    if hang:
        charm(ctx, 830, oy + 6 - 200 * (1 - ease(seg(r1, 2.6, 3.0))), 0.6, swing_at(lt, 0.1))
    label(ctx, "every morning = a gamble", 1500, 940, 50, r1, 0.4, hl=True)


def s_end(ctx, lt, d, b, frame):
    notebook(ctx)
    r1 = lt - (b[1] - b[0]) if len(b) > 1 else -1
    ground(ctx, frame)
    j = S.draw(ctx, 520, GROUND, 520, POSES["cup"], Face(mouth="smile", eyes="happy" if r1 > 0 else "dot"), HOST, 1, frame, ident="host")
    charm(ctx, j["rhand"][0], j["rhand"][1] - 20, 0.5, swing_at(lt, 0.15, 3), nail=False)
    rows = [("Stops bad luck?", 0.3, "x"), ("Stops worrying?", None, "tick"), ("Cost: 1 lemon", None, "")]
    for i, (s_, t0, mark) in enumerate(rows):
        tt = lt if i == 0 else r1
        t0 = t0 if t0 is not None else [0.0, 0.3, 1.5, 2.4][i + 1]
        y = 330 + i * 150
        label(ctx, s_, 1000, y, 70, tt, t0, align="l", hl=(i == 2))
        if mark == "x":
            cross(ctx, 1640, y, 1.4, seg(lt, 1.5, 2.0))
        elif mark == "tick":
            checkmark(ctx, 1640, y, 1.4, seg(r1, 1.0, 1.5))
            text(ctx, "maybe", 1760, y, 48, fill=GREEN, scale=pop(r1, 1.3))
    # end card
    end_t = d - 1.6
    if lt > end_t:
        a = seg(lt, end_t, end_t + 0.4)
        ctx.set_source_rgba(*PAPER, 0.93 * a)
        ctx.paint()
        text(ctx, "NEXT EPISODE", 960, 380, 70, font="Lilita One", fill=RED, alpha=a)
        text(ctx, "Why is chai everywhere in India?", 960, 500, 90, font="Lilita One", alpha=a)
        text(ctx, "(the honest history)", 960, 600, 56, alpha=a)


SCENES = {
    "street": s_street, "everywhere": s_everywhere, "question": s_question, "title": s_title, "recipe": s_recipe,
    "saturday": s_saturday, "legend": s_legend, "visit": s_visit, "nazar": s_nazar, "forward": s_forward,
    "verdict": s_verdict, "world": s_world, "brain": s_brain, "shop": s_shop, "end": s_end,
}

SFX = {  # scene -> [(beat_index, offset, kind)]
    "street": [(0, 0.1, "whoosh"), (1, -0.3, "whoosh"), (1, 0.1, "pop"), (1, 0.9, "pop"), (1, 2.0, "pop")],
    "everywhere": [(0, 0.15, "pop"), (0, 1.05, "pop"), (0, 1.9, "pop"), (0, 2.75, "pop")],
    "question": [(0, 0.1, "pop"), (0, 0.35, "pop"), (0, 1.9, "whoosh")],
    "title": [(0, 0.0, "spot"), (0, 0.25, "pop"), (0, 0.8, "ding")],
    "recipe": [(0, 0.0, "whoosh")] + [(1, 1.0 + k * 0.23, "tick") for k in range(7)] + [(1, 0.4, "pop")],
    "saturday": [(0, 2.0, "whoosh"), (0, 2.5, "pop"), (1, 0.8, "pop")],
    "legend": [(0, 0.05, "whoosh"), (1, 0.0, "ding"), (2, 0.0, "spot"), (2, 2.6, "pop")],
    "visit": [(0, 0.0, "whoosh")] + [(0, 2.4 + 0.45 * k, "pop") for k in range(5)] + [(1, 0.1, "splash")],
    "nazar": [(0, 0.4, "pop"), (0, 2.0, "ding"), (1, 1.9, "spot")],
    "forward": [(0, 0.05, "pop"), (1, 0.9, "pop"), (1, 1.6, "pop"), (1, 3.4, "whoosh")],
    "verdict": [(0, 2.0, "spot"), (1, 3.4, "ding")],
    "world": [(1, 0.0, "pop"), (2, 0.0, "pop")],
    "brain": [(0, 1.6, "pop"), (0, 4.2, "pop")],
    "shop": [(0, 0.4, "whoosh"), (1, 0.2, "pop"), (1, 2.6, "ding")],
    "end": [(0, 1.5, "spot"), (1, 1.0, "ding"), (1, 2.4, "pop")],
}

# ---------------------------------------------------------------- overlays


def timeline_bar(ctx, t, scene):
    c = script.CHAPTER_OF[scene]
    if c is None:
        return
    x0, x1, y = 260, 1660, 50
    n = len(script.CHAPTERS)
    seg_w = (x1 - x0) / n
    for i, name in enumerate(script.CHAPTERS):
        sx = x0 + i * seg_w + 8
        w = seg_w - 16
        a, b_ = CH_RANGE[i]
        p = 1.0 if i < c else (seg(t, a, b_) if i == c else 0.0)
        ctx.set_source_rgba(1, 1, 1, 0.85)
        ctx.rectangle(sx, y - 16, w, 32)
        ctx.fill()
        if p > 0:
            ctx.set_source_rgba(*(HL if i == c else (0.75, 0.82, 0.95)), 0.9)
            ctx.rectangle(sx, y - 16, w * p, 32)
            ctx.fill()
        ink(ctx, 3)
        ctx.rectangle(sx, y - 16, w, 32)
        ctx.stroke()
        text(ctx, name, sx + w / 2, y + 1, 30, font="Lilita One", fill=BLUE if i == c else (0.45, 0.5, 0.65))


def caption_chunks():
    chunks = []
    for ln in LINES:
        cur = []
        for w in ln["words"]:
            cur.append(w)
            if len(cur) == 5 or w["w"][-1] in ",.?!:":
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
    return chunks


CHUNKS = caption_chunks()


def captions(ctx, t):
    for i, ch in enumerate(CHUNKS):
        nxt = CHUNKS[i + 1][0]["s"] if i + 1 < len(CHUNKS) else 1e9
        end = nxt if nxt - ch[-1]["e"] < 0.35 else ch[-1]["e"] + 0.15
        if ch[0]["s"] - 0.05 <= t < end:
            break
    else:
        return
    size = 56
    words = [w["w"] for w in ch]
    widths = [text_w(ctx, w, size, "Lilita One") for w in words]
    space = size * 0.28
    total = sum(widths) + space * (len(words) - 1)
    ctx.save()
    ctx.set_source_rgba(1, 1, 1, 0.82)
    ctx.rectangle(960 - total / 2 - 26, 1012 - 40, total + 52, 80)
    ctx.fill()
    ctx.restore()
    x = 960 - total / 2
    for w, wd, info in zip(words, widths, ch):
        active = info["s"] <= t < info["e"] + 0.05
        if active:
            highlight(ctx, x - 6, 1014, wd + 12, 52, 1.0, alpha=0.75)
        text(ctx, w, x + wd / 2, 1012, size, font="Lilita One", fill=BLUE)
        x += wd + space


# ---------------------------------------------------------------- frames


def scene_at(t):
    for sc in SCENE_LIST:
        if sc[1] <= t + 1e-9 < sc[2]:
            return sc
    return SCENE_LIST[-1]


def draw_frame(frame):
    t = frame / FPS
    name, s0, s1, starts = scene_at(t)
    b = [st - (starts[0] if s0 > 0 else 0.0) for st in starts]
    if s0 == 0:
        b = [0.0] + [st - 0.0 for st in starts[1:]]
    else:
        b = [st - s0 for st in starts]
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    SCENES[name](ctx, t - s0, s1 - s0, b, frame)
    timeline_bar(ctx, t, name)
    captions(ctx, t)
    surf.flush()
    return surf


def render_chunk(args):
    idx, f0, f1 = args
    path = os.path.join(BUILD, f"chunk{idx:02d}.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr0", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                          "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(bytes(draw_frame(f).get_data()))
    p.stdin.close()
    p.wait()
    return path


def sfx_cues():
    cues = []
    for name, s0, s1, starts in SCENE_LIST:
        b = [st - s0 for st in starts]
        b[0] = 0.0
        for bi, off, kind in SFX.get(name, []):
            if bi < len(b):
                cues.append((s0 + b[bi] + off, kind))
    return cues


def thumbnail():
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1280, 720)
    ctx = cairo.Context(surf)
    ctx.scale(1280 / W, 720 / H)
    notebook(ctx)
    charm(ctx, 1770, 40, 1.6, 0.06)
    S.draw(ctx, 1500, 1120, 640, POSES["shrug"], Face(eyes="wide", mouth="o", brows="worried", look=(1, -0.5)), HOST, 1, 0,
           ident="thumb", boil=False)
    w = text_w(ctx, "+ CHILLIES?", 200, "Lilita One")
    highlight(ctx, 180, 560, w + 40, 170, 1.0, alpha=0.8)
    text(ctx, "WHY LEMON", 200, 340, 200, font="Lilita One", align="l")
    text(ctx, "+ CHILLIES?", 200, 555, 200, font="Lilita One", align="l")
    text(ctx, "the honest answer", 220, 760, 84, fill=RED, align="l", rot=-0.03)
    surf.write_to_png(os.path.join(OUT, "thumbnail.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", type=int, nargs="*")
    ap.add_argument("--thumb", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.thumb:
        thumbnail()
        return
    if a.still:
        for f in a.still:
            draw_frame(f).write_to_png(os.path.join(BUILD, f"still_{f:05d}.png"))
        return
    nframes = int(TOTAL * FPS)
    n = a.workers * 2
    bounds = [(i, nframes * i // n, nframes * (i + 1) // n) for i in range(n)]
    with Pool(a.workers) as pool:
        paths = pool.map(render_chunk, bounds)
    lst = os.path.join(BUILD, "chunks.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in paths)
    mixwav = os.path.join(BUILD, "mix.wav")
    audio.mix(os.path.join(BUILD, "voice.wav"), sfx_cues(), mixwav, music_gain=0.4)
    out = os.path.join(OUT, "ep01-nimbu-mirchi.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", mixwav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out], check=True)
    thumbnail()
    print("wrote", out, f"({nframes} frames)")


if __name__ == "__main__":
    main()
