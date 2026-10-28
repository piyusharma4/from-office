"""Render the demo short: build/timeline.json + build/voice.wav -> out/spotlight-effect.mp4

Every frame is draw(frame_number): no clocks, no randomness, so the video can be
rendered in parallel chunks and any frame can be re-rendered on its own.

    python render.py              # full render (parallel)
    python render.py --still 120  # write one PNG for checking a frame
"""
import argparse
import json
import math
import os
import subprocess
from multiprocessing import Pool

import cairo
import numpy as np

import audio
import stickman as S
from stickman import Face, Look, POSES, ease, ease_out_back, mix, walk

W, H = 1080, 1920
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "out")

INK = S.INK
PAPER = S.PAPER
DARK = (0.075, 0.075, 0.095)
YELLOW = (1.0, 0.82, 0.25)
RED = (0.88, 0.27, 0.27)
PINK = (0.86, 0.32, 0.56)
GROUND = 1180

TL = json.load(open(os.path.join(BUILD, "timeline.json")))
LINES = TL["lines"]
TOTAL = TL["duration"] + 0.6
STARTS = [0.0] + [l["start"] for l in LINES[1:]]

# ---------------------------------------------------------------- helpers

_grain = None


def grain():
    """Paper grain texture, generated once per process from a fixed seed."""
    global _grain
    if _grain is None:
        rng = np.random.default_rng(3)
        a = (rng.random((H // 2, W // 2)) * 14).astype(np.uint8)
        buf = np.zeros((H // 2, W // 2, 4), dtype=np.uint8)
        buf[..., 3] = a  # black specks at low alpha (premultiplied: rgb stays 0)
        surf = cairo.ImageSurface.create_for_data(memoryview(buf), cairo.FORMAT_ARGB32, W // 2, H // 2)
        _grain = (surf, buf)
    return _grain[0]


def paper(ctx):
    ctx.set_source_rgb(*PAPER)
    ctx.paint()
    ctx.save()
    ctx.scale(2, 2)
    ctx.set_source_surface(grain(), 0, 0)
    ctx.paint()
    ctx.restore()


def dark(ctx):
    ctx.set_source_rgb(*DARK)
    ctx.paint()


def camera(ctx, zoom, cx=W / 2, cy=H / 2):
    ctx.translate(W / 2, H / 2)
    ctx.scale(zoom, zoom)
    ctx.translate(-cx, -cy)


def seg(t, a, b):
    """0..1 progress of t through [a, b]."""
    return min(1.0, max(0.0, (t - a) / (b - a))) if b > a else float(t >= a)


def wobbly_line(ctx, x0, y, x1, frame, width=7, color=INK, ident="floor"):
    ctx.save()
    ctx.set_source_rgb(*color)
    ctx.set_line_width(width)
    ctx.set_line_cap(1)
    b = frame // 4
    ctx.move_to(x0, y + 2 * S.noise(ident, 0, b))
    n = 12
    for k in range(1, n + 1):
        ctx.line_to(x0 + (x1 - x0) * k / n, y + 2.5 * S.noise(ident, k, b))
    ctx.stroke()
    ctx.restore()


def text(ctx, s, x, y, size, font="Lilita One", fill=(1, 1, 1), stroke=INK, sw=0, scale=1.0, alpha=1.0, align="c", rot=0.0):
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
        ctx.set_source_rgba(*stroke, alpha)
        ctx.set_line_width(sw)
        ctx.set_line_join(1)
        ctx.stroke_preserve()
    ctx.set_source_rgba(*fill, alpha)
    ctx.fill()
    ctx.restore()
    return ext.x_advance * scale


def spotlight(ctx, x, ground, width, alpha=1.0, darkness=0.0):
    """Cone of light from above, with optional darkening of everything outside it."""
    if alpha <= 0:
        return
    top_w = width * 0.18
    ctx.save()
    if darkness > 0:
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.rectangle(-2000, -2000, W + 4000, H + 4000)
        ctx.move_to(x - top_w / 2, -50)
        ctx.line_to(x + top_w / 2, -50)
        ctx.line_to(x + width / 2, ground)
        ctx.line_to(x - width / 2, ground)
        ctx.close_path()
        ctx.set_source_rgba(0.05, 0.05, 0.07, darkness * alpha)
        ctx.fill()
        ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    g = cairo.LinearGradient(0, -50, 0, ground)
    g.add_color_stop_rgba(0, 1, 0.95, 0.7, 0.10 * alpha)
    g.add_color_stop_rgba(1, 1, 0.88, 0.45, 0.42 * alpha)
    ctx.move_to(x - top_w / 2, -50)
    ctx.line_to(x + top_w / 2, -50)
    ctx.line_to(x + width / 2, ground)
    ctx.line_to(x - width / 2, ground)
    ctx.close_path()
    ctx.set_source(g)
    ctx.fill()
    ctx.save()
    ctx.translate(x, ground)
    ctx.scale(width / 2, 34)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(1, 0.9, 0.5, 0.55 * alpha)
    ctx.fill()
    ctx.restore()


def bubble(ctx, cx, cy, w, h, lines_, tail, k=1.0, size=40):
    """Thought bubble with text; k is the pop-in scale (0..1+)."""
    if k <= 0.01:
        return
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(k, k)
    ctx.set_line_width(5)
    for i, (dx, dy, r) in enumerate(((tail[0] - cx) * f, (tail[1] - cy) * f, rr) for f, rr in ((0.92, 9), (0.72, 15))):
        ctx.arc(dx, dy, r, 0, 2 * math.pi)
        ctx.set_source_rgb(1, 1, 1)
        ctx.fill_preserve()
        ctx.set_source_rgb(*INK)
        ctx.stroke()
    ctx.save()
    ctx.scale(w / 2, h / 2)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill_preserve()
    ctx.set_source_rgb(*INK)
    ctx.stroke()
    n = len(lines_)
    for i, ln in enumerate(lines_):
        text(ctx, ln, 0, (i - (n - 1) / 2) * size * 1.1, size, font="Patrick Hand", fill=INK)
    ctx.restore()


def cup(ctx, x, y, rot=0.0, full=True):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.move_to(-26, -34)
    ctx.line_to(26, -34)
    ctx.line_to(20, 30)
    ctx.line_to(-20, 30)
    ctx.close_path()
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill_preserve()
    ctx.set_source_rgb(*INK)
    ctx.set_line_width(5)
    ctx.stroke()
    ctx.set_source_rgb(*RED)
    ctx.rectangle(-22, -8, 44, 14)
    ctx.fill()
    if full:
        ctx.set_source_rgb(0.42, 0.25, 0.12)
        ctx.rectangle(-22, -32, 44, 8)
        ctx.fill()
    ctx.restore()


def exclaim(ctx, x, y, k):
    if k <= 0.01:
        return
    text(ctx, "!", x, y, 96, fill=RED, sw=10, scale=k)


def room(ctx, frame):
    """Wall details + floor for the office scenes."""
    ctx.save()
    ctx.set_source_rgb(*INK)
    ctx.set_line_width(6)
    ctx.rectangle(700, 330, 260, 300)  # window
    ctx.move_to(830, 330)
    ctx.line_to(830, 630)
    ctx.move_to(700, 480)
    ctx.line_to(960, 480)
    ctx.stroke()
    ctx.arc(250, 420, 80, 0, 2 * math.pi)  # clock
    ctx.stroke()
    ctx.move_to(250, 420)
    ctx.line_to(250, 370)
    ctx.move_to(250, 420)
    ctx.line_to(290, 440)
    ctx.stroke()
    ctx.restore()
    wobbly_line(ctx, -200, GROUND, W + 200, frame)


CROWD = [  # x, height, look, facing
    (120, 340, Look(hair="bun"), 1),
    (290, 320, Look(hair="cap", accent=(0.25, 0.55, 0.9)), -1),
    (800, 330, Look(hair="bow", accent=PINK), 1),
    (965, 345, Look(glasses=True, hair="tuft"), -1),
]
HERO = Look(hair="tuft")


def crowd(ctx, frame, mode, t, hero_x=540):
    """mode: chat | stare | ignore"""
    for i, (x, h, look, facing) in enumerate(CROWD):
        talk = math.sin(t * 5 + i * 2)
        if mode == "chat":
            pose = mix(POSES["stand"], POSES["shrug"] if i % 2 else POSES["wave"], 0.5 + 0.5 * talk)
            face = Face(mouth="grin" if talk > 0.3 else "smile", look=(facing, 0))
            S.draw(ctx, x, GROUND, h, pose, face, look, facing, frame, ident=i)
        elif mode == "stare":
            to = 1 if hero_x > x else -1
            face = Face(eyes="wide", mouth="o", look=(to, 0))
            S.draw(ctx, x, GROUND, h, mix(POSES["stand"], POSES["point"], 0.25), face, look, to, frame, ident=i)
        else:  # ignore: everyone back to their own thing
            kind = ["phone", "chat", "chat", "yawn"][i]
            if kind == "phone":
                S.draw(ctx, x, GROUND, h, POSES["phone"], Face(look=(0, 1)), look, facing, frame, ident=i)
                hand = ((x - 10), GROUND - h * 0.62)
                ctx.set_source_rgb(*INK)
                ctx.rectangle(hand[0] - 14, hand[1] - 24, 28, 44)
                ctx.fill()
            elif kind == "yawn":
                S.draw(ctx, x, GROUND, h, POSES["stand"], Face(eyes="closed", mouth="o"), look, facing, frame, ident=i)
            else:
                pose = mix(POSES["stand"], POSES["shrug"] if i % 2 else POSES["wave"], 0.5 + 0.5 * talk)
                S.draw(ctx, x, GROUND, h, pose, Face(mouth="grin" if talk > 0.3 else "smile", look=(facing, 0)),
                       look, facing, frame, ident=i)


# ---------------------------------------------------------------- scenes
# Each scene: draw(ctx, lt, d, frame) with lt = seconds since scene start.

def s_spill(ctx, lt, d, frame):
    paper(ctx)
    z = 1 + 0.08 * ease(seg(lt, 0.6, d))
    ctx.save()
    camera(ctx, z, 540, 900)
    room(ctx, frame)
    crowd(ctx, frame, "chat", lt)
    arrive = 1.0
    if lt < arrive:
        x = -160 + 700 * ease(lt / arrive) if lt > 0 else -160
        x = -160 + 700 * (lt / arrive)
        pose = walk(lt * 11, POSES["cup"])
        j = S.draw(ctx, x, GROUND, 440, pose, Face(mouth="smile"), HERO, 1, frame, ident=9)
        cup(ctx, j["rhand"][0] + 4, j["rhand"][1] - 30)
    else:
        u = lt - arrive
        pose = mix(POSES["cup"], POSES["flail"], seg(u, 0, 0.15))
        look = Look(hair="tuft", stain=ease(seg(u, 0.1, 0.35)))
        j = S.draw(ctx, 540, GROUND, 440, pose, Face(eyes="wide", mouth="o", brows="up"), look, 1, frame, ident=9)
        cx = 540 + 160 + 420 * u
        cy = GROUND - 440 * 0.62 - 900 * u + 1500 * u * u
        cup(ctx, cx, cy, rot=7 * u, full=False)
        ctx.set_source_rgb(0.42, 0.25, 0.12)
        for k in range(7):  # coffee droplets
            dx = (k - 3) * 38 * u * 3
            dy = -500 * u + 1900 * u * u + 14 * k
            r = 12 - k
            if dy < 300:
                ctx.arc(640 + dx, GROUND - 330 + dy, max(3, r), 0, 2 * math.pi)
                ctx.fill()
    ctx.restore()


def s_stare(ctx, lt, d, frame):
    paper(ctx)
    ctx.save()
    camera(ctx, 1.08 + 0.06 * ease(seg(lt, 0, d)), 540, 900)
    room(ctx, frame)
    crowd(ctx, frame, "stare", lt)
    slam = ease_out_back(seg(lt, 0, 0.18))
    spotlight(ctx, 540, GROUND, 520 * slam, alpha=1, darkness=0.55)
    pose = mix(POSES["flail"], POSES["shrug"], seg(lt, 0.05, 0.35))
    S.draw(ctx, 540, GROUND, 440, pose, Face(eyes="wide", mouth="wobble", brows="worried", blush=True),
           Look(hair="tuft", stain=1), 1, frame, ident=9)
    for i, (x, h, _, _) in enumerate(CROWD):
        exclaim(ctx, x, GROUND - h - 70, ease_out_back(seg(lt, 0.3 + 0.12 * i, 0.5 + 0.12 * i)))
    ctx.restore()


def s_nobody(ctx, lt, d, frame):
    paper(ctx)
    ctx.save()
    camera(ctx, 1.14 - 0.14 * ease(seg(lt, 0.4, d)), 540, 900)
    room(ctx, frame)
    flick = 1.0 if lt < 0.35 else (0.0 if lt > 0.75 else (1.0 if (frame // 2) % 2 else 0.3) * (1 - seg(lt, 0.35, 0.75)))
    crowd(ctx, frame, "stare" if lt < 0.45 else "ignore", lt)
    spotlight(ctx, 540, GROUND, 520, alpha=flick, darkness=0.55)
    pose = mix(POSES["shrug"], POSES["think"], seg(lt, 0.6, 0.85))
    pose = mix(pose, POSES["proud"], seg(lt, 1.5, 1.8))
    face = Face(eyes="dot", mouth="o" if lt < 1.5 else "grin", look=(-1 if (lt // 0.5) % 2 else 1, 0), blush=lt < 1.5)
    S.draw(ctx, 540, GROUND, 440, pose, face, Look(hair="tuft", stain=1), 1, frame, ident=9)
    k = ease_out_back(seg(lt, 0.9, 1.15))
    text(ctx, "?", 540, GROUND - 560, 110, fill=YELLOW, sw=10, scale=k)
    ctx.restore()


def s_title(ctx, lt, d, frame):
    dark(ctx)
    ctx.save()
    camera(ctx, 1.0 + 0.04 * seg(lt, 0, d))
    on = ease_out_back(seg(lt, 0, 0.2))
    spotlight(ctx, 540, 1250, 640 * on)
    wobbly_line(ctx, -200, 1250, W + 200, frame, color=(0.25, 0.25, 0.3))
    S.draw(ctx, 540, 1250, 330, POSES["wave"], Face(mouth="grin", eyes="happy"), HERO, 1, frame, ident=9)
    text(ctx, "THE", 540, 470, 90, fill=(1, 1, 1), sw=0, scale=ease_out_back(seg(lt, 0.1, 0.3)))
    text(ctx, "SPOTLIGHT", 540, 610, 170, fill=YELLOW, sw=12, scale=ease_out_back(seg(lt, 0.3, 0.55)))
    text(ctx, "EFFECT", 540, 770, 150, fill=YELLOW, sw=12, scale=ease_out_back(seg(lt, 0.55, 0.8)))
    ctx.restore()


STUDENT = Look(hair="spiky", shirt=PINK, shirt_text="MANILOW")


def sticky(ctx, x, y, lines_, k, rot=-0.05):
    if k <= 0.01:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(k, k)
    ctx.set_source_rgba(0, 0, 0, 0.12)
    ctx.rectangle(-232, -82, 480, 180)
    ctx.fill()
    ctx.set_source_rgb(1.0, 0.88, 0.4)
    ctx.rectangle(-240, -90, 480, 180)
    ctx.fill()
    for i, ln in enumerate(lines_):
        text(ctx, ln, 0, -30 + i * 64, 54 if i == 0 else 44, font="Patrick Hand", fill=INK)
    ctx.restore()


def s_shirt(ctx, lt, d, frame):
    paper(ctx)
    zt = ease(seg(lt, d - 1.5, d - 0.5))
    walk_end = 2.6
    x = 210 + 280 * ease(seg(lt, 0.4, walk_end))
    ctx.save()
    camera(ctx, 1 + 0.75 * zt, 540 + (x - 540) * zt, 900 + (GROUND - 330 - 900) * zt)
    ctx.set_source_rgb(*INK)
    ctx.set_line_width(8)
    ctx.rectangle(90, GROUND - 560, 240, 560)  # door
    ctx.stroke()
    ctx.arc(295, GROUND - 280, 9, 0, 2 * math.pi)
    ctx.fill()
    wobbly_line(ctx, -200, GROUND, W + 200, frame)
    for i, (cx, h, look, facing) in enumerate([(760, 320, Look(hair="bun"), -1), (900, 335, Look(hair="cap", accent=(0.25, 0.55, 0.9)), -1),
                                               (1030, 310, Look(hair="bow", accent=PINK), -1)]):
        S.draw(ctx, cx, GROUND, h, mix(POSES["stand"], POSES["phone"], 0.6), Face(look=(-1, 0.6)), look, facing, frame, ident=20 + i)
    walking = 0.4 < lt < walk_end
    pose = walk(lt * 9) if walking else POSES["slump"]
    S.draw(ctx, x, GROUND, 450, pose, Face(mouth="wobble", blush=True, brows="worried"), STUDENT, 1, frame, ident=12)
    k = ease_out_back(seg(lt, d - 1.2, d - 0.95))
    if k > 0.01:
        ctx.save()
        ctx.set_source_rgb(*RED)
        ctx.set_line_width(6 / (1 + 0.75 * zt))
        ctx.move_to(x + 210, GROUND - 470)
        ctx.curve_to(x + 190, GROUND - 400, x + 160, GROUND - 360, x + 95, GROUND - 330)
        ctx.stroke()
        ctx.restore()
        text(ctx, "cringe level", x + 185, GROUND - 535, 38, font="Patrick Hand", fill=RED, stroke=PAPER, sw=0, scale=k, rot=0.08)
        text(ctx, "MAX", x + 195, GROUND - 492, 44, fill=RED, scale=k, rot=0.08)
    ctx.restore()
    sticky(ctx, 540, 260, ["Cornell University, 2000", "the T-shirt experiment"], ease_out_back(seg(lt, 0.0, 0.3)))


def pie(ctx, x, y, r, frac, color):
    ctx.save()
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill_preserve()
    ctx.set_source_rgb(*INK)
    ctx.set_line_width(5)
    ctx.stroke()
    if frac > 0:
        ctx.move_to(x, y)
        ctx.arc(x, y, r - 4, -math.pi / 2, -math.pi / 2 + 2 * math.pi * frac)
        ctx.close_path()
        ctx.set_source_rgb(*color)
        ctx.fill()
    ctx.restore()


def s_guess(ctx, lt, d, frame):
    paper(ctx)
    ctx.save()
    camera(ctx, 1.0 + 0.04 * seg(lt, 0, d))
    wobbly_line(ctx, -200, GROUND, W + 200, frame)
    S.draw(ctx, 330, GROUND, 520, POSES["think"], Face(brows="worried", mouth="wobble", look=(1, -1), blush=True),
           STUDENT, 1, frame, ident=12)
    k = ease_out_back(seg(lt, 0.0, 0.25))
    ctx.save()
    ctx.translate(690, 560)
    ctx.scale(k, k)
    ctx.translate(-690, -560)
    bubble(ctx, 690, 560, 640, 560, [], (460, 760), 1)
    pie(ctx, 690, 490, 140, 0.5 * ease(seg(lt, 0.3, 0.9)), RED)
    text(ctx, "HALF the room", 690, 690, 50, font="Patrick Hand", fill=INK)
    text(ctx, "will notice!", 690, 742, 50, font="Patrick Hand", fill=INK)
    ctx.restore()
    ctx.restore()


def s_actual(ctx, lt, d, frame):
    paper(ctx)
    # one-in-four row
    for i in range(4):
        x = 255 + i * 190
        hi = i == 1
        on = seg(lt, 0.9 + 0.1 * i, 1.1 + 0.1 * i)
        if hi and on > 0:
            ctx.save()
            ctx.arc(x, 360, 120 * ease_out_back(on), 0, 2 * math.pi)
            ctx.set_source_rgba(*YELLOW, 0.75)
            ctx.fill()
            ctx.restore()
        face = Face(eyes="wide", look=(0, 0), mouth="o") if hi and on > 0.5 else Face(look=(0, 1))
        S.draw(ctx, x, 470, 200, POSES["stand"] if hi else POSES["phone"], face,
               CROWD[i % 4][2], 1, frame, ident=30 + i, boil=True)
    base = 1180
    full = 760  # px for 100%
    bars = [("THEY GUESSED", 0.50, ease(seg(lt, 0.0, 0.35)), (0.82, 0.8, 0.78)),
            ("REALITY", 0.23, ease(seg(lt, 0.45, 1.3)), YELLOW)]
    for i, (label, val, p, color) in enumerate(bars):
        x = 330 + i * 420
        h = full * val * p
        ctx.set_source_rgb(*color)
        ctx.rectangle(x - 130, base - h, 260, h)
        ctx.fill_preserve()
        ctx.set_source_rgb(*INK)
        ctx.set_line_width(6)
        ctx.stroke()
        if p > 0:
            text(ctx, f"{round(val * 100 * p)}%", x, base - h - 70, 100, fill=(1, 1, 1) if i == 0 else YELLOW, sw=12)
        text(ctx, label, x, base + 60, 50, font="Patrick Hand", fill=INK)
    wobbly_line(ctx, 120, base, 960, frame, width=8)


def s_truth(ctx, lt, d, frame):
    paper(ctx)
    ctx.save()
    ctx.translate(540, 980)
    ctx.rotate(lt * 0.25)
    ctx.set_source_rgba(*YELLOW, 0.35)
    for k in range(16):
        a = k / 16 * 2 * math.pi
        ctx.move_to(0, 0)
        ctx.arc(0, 0, 1600, a, a + math.pi / 16)
        ctx.close_path()
        ctx.fill()
    ctx.restore()
    z = 1.15 - 0.15 * ease_out_back(seg(lt, 0, 0.35))
    ctx.save()
    camera(ctx, z)
    S.draw(ctx, 540, 1900, 1150, POSES["wave"], Face(mouth="flat", brows="up"), HERO, 1, frame, ident=9)
    ctx.restore()
    text(ctx, "THE HONEST", 540, 300, 120, fill=(1, 1, 1), sw=12, scale=ease_out_back(seg(lt, 0.05, 0.3)))
    text(ctx, "TRUTH", 540, 430, 150, fill=YELLOW, sw=12, scale=ease_out_back(seg(lt, 0.2, 0.45)))


STAGE = [  # x, height, look, pose, worry
    (130, 330, Look(hair="bun"), "think", ["is my hair", "weird?"]),
    (335, 320, Look(hair="cap", accent=(0.25, 0.55, 0.9)), "slump", ["ugh, my", "voice..."]),
    (540, 350, HERO, "stand", ["did they see", "the coffee?"]),
    (745, 325, Look(hair="bow", accent=PINK), "peek", ["is my fly", "open??"]),
    (950, 340, Look(glasses=True), "cover", ["they all", "hate me"]),
]
SPOT_ORDER = [2, 1, 3, 0, 4]


def stage(ctx, lt, frame, spot_t0, bubbles_t0=None):
    wobbly_line(ctx, -400, GROUND, W + 400, frame, color=(0.25, 0.25, 0.3))
    for rank, i in enumerate(SPOT_ORDER):
        x, h, look, pose, worry = STAGE[i]
        on = seg(lt, spot_t0 + 0.22 * rank, spot_t0 + 0.22 * rank + 0.15)
        spotlight(ctx, x, GROUND, 230 * ease_out_back(on), alpha=on)
    for i, (x, h, look, pose, worry) in enumerate(STAGE):
        face = Face(brows="worried", mouth="wobble", look=(0, 0.3))
        if look.stain == 0 and i == 2:
            look = Look(hair="tuft", stain=1)
        S.draw(ctx, x, GROUND, h, POSES[pose], face, look, 1 if i < 2 else -1, frame, ident=40 + i)
    if bubbles_t0 is not None:
        for rank, i in enumerate(SPOT_ORDER):
            x, h, look, pose, worry = STAGE[i]
            k = ease_out_back(seg(lt, bubbles_t0 + 0.28 * rank, bubbles_t0 + 0.28 * rank + 0.25))
            by = 520 if i % 2 == 0 else 760
            bx = min(max(x, 175), W - 175)
            bubble(ctx, bx, by, 330, 190, worry, (x, GROUND - h - 30), k, size=40)


def s_spots(ctx, lt, d, frame):
    dark(ctx)
    ctx.save()
    zt = ease(seg(lt, 0.0, 1.4))
    camera(ctx, 1.8 - 0.8 * zt, 540, 1000 - 40 * zt)
    stage(ctx, lt, frame, 0.0)
    ctx.restore()


def s_worries(ctx, lt, d, frame):
    dark(ctx)
    ctx.save()
    camera(ctx, 1.0, 540, 960)
    stage(ctx, lt + 5, frame, -5, bubbles_t0=5.05)
    ctx.restore()


def film(ctx, x0, y0, w, h, frame):
    ctx.save()
    ctx.set_source_rgb(*INK)
    b = 46
    ctx.rectangle(x0 - b, y0 - b, w + 2 * b, h + 2 * b)
    ctx.rectangle(x0, y0, w, h)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    ctx.fill()
    ctx.set_source_rgb(*PAPER)
    n = 9
    for k in range(n):
        xx = x0 + (k + 0.5) * w / n - 12
        ctx.rectangle(xx, y0 - b + 12, 24, 22)
        ctx.rectangle(xx, y0 + h + 12, 24, 22)
    ctx.fill()
    ctx.restore()


CAST = [
    (Look(hair="bun"), "celebrate"), (Look(hair="cap", accent=(0.25, 0.55, 0.9)), "wave"), (Look(hair="bow", accent=PINK), "proud"),
    (Look(glasses=True), "shrug"), None, (Look(hair="spiky"), "celebrate"),
    (Look(hair="tuft", accent=RED), "proud"), (Look(hair="cap", accent=(0.3, 0.7, 0.4)), "wave"), (Look(glasses=True, hair="bun"), "shrug"),
]


def movie_cell(ctx, ox, oy, frame, who, label, t, ident):
    film(ctx, ox + 160, oy + 430, 760, 780, frame)
    spotlight(ctx, ox + 540, oy + 1100, 420, alpha=0.9)
    look, pose = who
    S.draw(ctx, ox + 540, oy + 1100, 560, POSES[pose], Face(eyes="happy", mouth="grin"), look, 1, frame, ident=ident)
    text(ctx, "STARRING:", ox + 540, oy + 250, 64, font="Patrick Hand", fill=INK)
    text(ctx, label, ox + 540, oy + 345, 130, fill=YELLOW, sw=12)


def s_movie(ctx, lt, d, frame):
    paper(ctx)
    ctx.save()
    camera(ctx, 1.0 + 0.05 * seg(lt, 0, d))
    pose = mix(POSES["slump"], POSES["proud"], seg(lt, 0.0, 0.4))
    film(ctx, 160, 430, 760, 780, frame)
    spotlight(ctx, 540, 1100, 420, alpha=ease(seg(lt, 0, 0.3)) * 0.9)
    S.draw(ctx, 540, 1100, 560, pose, Face(eyes="happy" if lt > 0.4 else "dot", mouth="grin" if lt > 0.4 else "flat"),
           Look(hair="tuft", stain=1), 1, frame, ident=9)
    text(ctx, "STARRING:", 540, 250, 64, font="Patrick Hand", fill=INK, scale=ease_out_back(seg(lt, 0.1, 0.35)))
    text(ctx, "YOU", 540, 345, 130, fill=YELLOW, sw=12, scale=ease_out_back(seg(lt, 0.3, 0.55)))
    ctx.restore()


def s_everyone(ctx, lt, d, frame):
    paper(ctx)
    zt = ease(seg(lt, 0.0, 1.3))
    z = 1.0 - 0.67 * zt
    ctx.save()
    camera(ctx, z, 540, 720 + 120 * zt)
    for i in range(9):
        gx, gy = (i % 3 - 1) * 1000, (i // 3 - 1) * 1150
        if i == 4:
            film(ctx, 160, 430, 760, 780, frame)
            spotlight(ctx, 540, 1100, 420, alpha=0.9)
            S.draw(ctx, 540, 1100, 560, POSES["proud"], Face(eyes="happy", mouth="grin"), Look(hair="tuft", stain=1), 1, frame, ident=9)
            text(ctx, "STARRING:", 540, 250, 64, font="Patrick Hand", fill=INK)
            text(ctx, "YOU", 540, 345, 130, fill=YELLOW, sw=12)
        else:
            movie_cell(ctx, gx, gy, frame, CAST[i], "THEM", lt, 50 + i)
    ctx.restore()
    fade = seg(lt, d - 0.45, d)
    if fade > 0:
        ctx.set_source_rgba(*PAPER, fade)
        ctx.paint()


SCENES = {
    "spill": s_spill, "stare": s_stare, "nobody": s_nobody, "title": s_title, "shirt": s_shirt, "guess": s_guess,
    "actual": s_actual, "truth": s_truth, "spots": s_spots, "worries": s_worries, "movie": s_movie, "everyone": s_everyone,
}

SFX = {  # scene -> [(offset_seconds, kind)]
    "spill": [(0.05, "whoosh"), (1.02, "splash")],
    "stare": [(0.0, "spot")] + [(0.3 + 0.12 * i, "pop") for i in range(4)],
    "nobody": [(0.4, "tick"), (0.55, "tick"), (0.7, "tick"), (0.95, "pop")],
    "title": [(0.0, "spot"), (0.3, "pop"), (0.55, "pop")],
    "shirt": [(0.0, "pop"), ("end-1.2", "pop")],
    "guess": [(0.0, "pop")],
    "actual": [(0.0, "whoosh")] + [(0.5 + 0.08 * k, "tick") for k in range(10)] + [(1.3, "ding")],
    "truth": [(0.0, "whoosh")],
    "spots": [(0.22 * r + 0.05, "spot") for r in range(5)],
    "worries": [(0.05 + 0.28 * r, "pop") for r in range(5)],
    "movie": [(0.0, "whoosh"), (0.3, "pop")],
    "everyone": [(0.0, "whoosh"), (1.3, "ding")],
}

# ---------------------------------------------------------------- captions


def caption_chunks():
    chunks = []
    for ln in LINES:
        cur = []
        for w in ln["words"]:
            cur.append(w)
            if len(cur) == 3 or w["w"][-1] in ",.?!":
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
    return chunks


CHUNKS = caption_chunks()


def captions(ctx, t):
    for i, ch in enumerate(CHUNKS):
        end = CHUNKS[i + 1][0]["s"] if i + 1 < len(CHUNKS) and CHUNKS[i + 1][0]["s"] - ch[-1]["e"] < 0.35 else ch[-1]["e"] + 0.15
        if ch[0]["s"] - 0.05 <= t < end:
            break
    else:
        return
    size = 88
    ctx.save()
    ctx.select_font_face("Lilita One")
    ctx.set_font_size(size)
    words = [w["w"].upper() for w in ch]
    space = size * 0.3
    widths = [ctx.text_extents(w).x_advance for w in words]
    total = sum(widths) + space * (len(words) - 1)
    k = 0.85 + 0.15 * ease_out_back(seg(t, ch[0]["s"] - 0.05, ch[0]["s"] + 0.08))
    if total * k > W - 120:
        k *= (W - 120) / (total * k)
    x = 540 - total * k / 2
    y = 1480
    for w, wd, info in zip(words, widths, ch):
        active = info["s"] <= t < info["e"] + 0.05
        text(ctx, w, x + wd * k / 2, y, size, fill=YELLOW if active else (1, 1, 1), sw=16, scale=k * (1.07 if active else 1))
        x += (wd + space) * k
    ctx.restore()


# ---------------------------------------------------------------- frames


def draw_frame(frame):
    t = frame / FPS
    i = max(k for k, s in enumerate(STARTS) if s <= t + 1e-9)
    start = STARTS[i]
    end = STARTS[i + 1] if i + 1 < len(STARTS) else TOTAL
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    SCENES[LINES[i]["scene"]](ctx, t - start, end - start, frame)
    captions(ctx, t)
    surf.flush()
    return surf


def render_chunk(args):
    idx, f0, f1 = args
    path = os.path.join(BUILD, f"chunk{idx:02d}.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr0", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                          "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(bytes(draw_frame(f).get_data()))
    p.stdin.close()
    p.wait()
    return path


def sfx_cues():
    cues = []
    for i, ln in enumerate(LINES):
        start = STARTS[i]
        end = STARTS[i + 1] if i + 1 < len(STARTS) else TOTAL
        for off, kind in SFX.get(ln["scene"], []):
            if isinstance(off, str):
                off = (end - start) - float(off.split("-")[1])
            cues.append((start + off, kind))
    return cues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", type=int, nargs="*")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.still:
        for f in a.still:
            draw_frame(f).write_to_png(os.path.join(BUILD, f"still_{f:04d}.png"))
        return
    nframes = int(TOTAL * FPS)
    n = a.workers
    bounds = [(i, nframes * i // n, nframes * (i + 1) // n) for i in range(n)]
    with Pool(n) as pool:
        paths = pool.map(render_chunk, bounds)
    lst = os.path.join(BUILD, "chunks.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in paths)
    mixwav = os.path.join(BUILD, "mix.wav")
    audio.mix(sfx_cues(), mixwav)
    out = os.path.join(OUT, "spotlight-effect.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", mixwav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out], check=True)
    print("wrote", out, f"({nframes} frames)")


if __name__ == "__main__":
    main()
