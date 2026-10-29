"""A small stickman rig drawn with cairo.

Limb angles are absolute screen angles in degrees, measured from straight down,
positive toward +x. Each limb is (upper_angle, bend) where the lower segment
points at upper_angle + bend. `facing=-1` mirrors the pose.

Everything is a pure function of its inputs (including the line-boil jitter,
which is seeded by a frame bucket), so any frame renders identically every time.
"""
import math
import zlib
from dataclasses import dataclass, field, replace

INK = (0.09, 0.09, 0.11)
PAPER = (0.97, 0.955, 0.93)


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ease_out_back(x, s=1.7):
    x = min(1.0, max(0.0, x)) - 1
    return x * x * ((s + 1) * x + s) + 1


def noise(*key):
    """Deterministic pseudo-random in [-1, 1]."""
    h = 2166136261
    for k in key:
        h = ((h ^ zlib.crc32(str(k).encode())) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    h ^= h >> 15
    return (h / 0xFFFFFFFF) * 2 - 1


@dataclass(frozen=True)
class Pose:
    lean: float = 0.0          # torso tilt, + toward +x
    head: float = 0.0          # head tilt
    la: tuple = (-14, 0)       # left arm (screen left)
    ra: tuple = (14, 0)
    ll: tuple = (-9, 0)
    rl: tuple = (9, 0)
    hip_drop: float = 0.0      # crouch, in units of H


def mix(a: Pose, b: Pose, t: float) -> Pose:
    t = ease(t)
    l = lambda x, y: x + (y - x) * t
    lt = lambda p, q: (l(p[0], q[0]), l(p[1], q[1]))
    return Pose(l(a.lean, b.lean), l(a.head, b.head), lt(a.la, b.la), lt(a.ra, b.ra),
                lt(a.ll, b.ll), lt(a.rl, b.rl), l(a.hip_drop, b.hip_drop))


POSES = {
    "stand":     Pose(),
    "wave":      Pose(head=6, ra=(140, 35)),
    "shrug":     Pose(head=-10, la=(-55, -95), ra=(55, 95)),
    "cover":     Pose(head=8, lean=4, la=(-140, 205), ra=(140, -205), hip_drop=0.02),
    "peek":      Pose(head=-6, la=(-150, 235), ra=(30, 10)),
    "point":     Pose(head=4, ra=(95, -5)),
    "think":     Pose(head=-8, ra=(50, -215), la=(-18, 0)),
    "phone":     Pose(head=12, la=(-22, 150), ra=(22, -150)),
    "celebrate": Pose(head=-4, la=(-150, -15), ra=(150, 15), ll=(-16, 0), rl=(16, 0)),
    "cup":       Pose(ra=(45, 45), la=(-14, 0)),
    "flail":     Pose(lean=8, head=10, la=(-130, -40), ra=(120, 50), ll=(-20, 10), rl=(14, 0)),
    "proud":     Pose(head=-6, la=(-62, 98), ra=(62, -98), ll=(-14, 0), rl=(14, 0)),
    "slump":     Pose(lean=6, head=18, la=(-6, 0), ra=(6, 0), hip_drop=0.015),
}


def walk(phase: float, base: Pose = POSES["stand"]) -> Pose:
    s = math.sin(phase)
    return replace(base, ll=(-4 + 24 * s, max(0, -18 * s)), rl=(4 - 24 * s, max(0, 18 * s) * -1),
                   la=(-14 - 16 * s, 0), ra=(14 - 16 * s, 0), hip_drop=0.01 * abs(math.cos(phase)))


@dataclass
class Face:
    eyes: str = "dot"        # dot | wide | closed | happy
    look: tuple = (0.0, 0.0)  # -1..1 pupils offset
    mouth: str = "smile"     # smile | flat | o | frown | grin | wobble
    brows: str = ""          # "" | worried | up
    blush: bool = False


@dataclass
class Look:
    """Per-character styling."""
    color: tuple = INK
    hair: str = ""           # "" | tuft | bun | spiky | cap | bow
    accent: tuple = (0.95, 0.45, 0.3)
    shirt: tuple | None = None
    shirt_text: str = ""
    stain: float = 0.0       # 0..1 coffee stain size
    glasses: bool = False
    mustache: bool = False
    shirt_len: float = 0.0   # extra length below the hip (kurta), in units of H
    extras: dict = field(default_factory=dict)


def _dir(a):
    r = math.radians(a)
    return math.sin(r), math.cos(r)


def draw(ctx, x, ground, H, pose: Pose, face: Face, look: Look = Look(), facing=1, frame=0, ident=0, boil=True):
    """Draw a stickman whose feet rest near `ground`, total height ~H. Returns joint dict."""
    f = facing
    bucket = frame // 4 if boil else 0
    amp = H * 0.006 if boil else 0

    def j(px, py, name):
        return (px + amp * noise(ident, name, bucket, 1), py + amp * noise(ident, name, bucket, 2))

    lw = H * 0.045
    hip = (x, ground - H * (0.43 - pose.hip_drop))
    lean = pose.lean * f
    dx, dy = _dir(180 + lean)  # pointing up
    neck = (hip[0] + dx * H * 0.30, hip[1] + dy * H * 0.30)
    hdx, hdy = _dir(180 + lean + pose.head * f)
    head_c = (neck[0] + hdx * H * 0.13, neck[1] + hdy * H * 0.13)
    hr = H * 0.115
    shoulder = (neck[0] - dx * H * 0.035, neck[1] - dy * H * 0.035)

    def limb(origin, spec, l1, l2, name):
        a1, b = spec[0] * f, spec[1] * f
        ux, uy = _dir(a1)
        mid = (origin[0] + ux * l1, origin[1] + uy * l1)
        vx, vy = _dir(a1 + b)
        end = (mid[0] + vx * l2, mid[1] + vy * l2)
        return j(*mid, name + "m"), j(*end, name + "e")

    if f < 0:  # mirrored: screen-left limb uses the right-limb spec so silhouettes flip cleanly
        la_spec, ra_spec, ll_spec, rl_spec = pose.ra, pose.la, pose.rl, pose.ll
    else:
        la_spec, ra_spec, ll_spec, rl_spec = pose.la, pose.ra, pose.ll, pose.rl
    L_arm = limb(shoulder, la_spec, H * 0.17, H * 0.165, "la")
    R_arm = limb(shoulder, ra_spec, H * 0.17, H * 0.165, "ra")
    L_leg = limb(hip, ll_spec, H * 0.225, H * 0.215, "ll")
    R_leg = limb(hip, rl_spec, H * 0.225, H * 0.215, "rl")
    hipj, neckj = j(*hip, "hip"), j(*neck, "neck")
    shj = j(*shoulder, "sh")

    ctx.save()
    ctx.set_line_cap(1)  # round
    ctx.set_line_join(1)
    ctx.set_source_rgb(*look.color)
    ctx.set_line_width(lw)

    def poly(*pts):
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.stroke()

    poly(hipj, *L_leg)
    poly(hipj, *R_leg)

    if look.shirt:  # T-shirt drawn as a rounded trapezoid around the torso
        ctx.save()
        w = H * 0.15
        ctx.set_source_rgb(*look.shirt)
        top_l = (shj[0] - w, shj[1] + H * 0.01)
        top_r = (shj[0] + w, shj[1] + H * 0.01)
        bot_l = (hipj[0] - w * (0.82 + look.shirt_len * 2), hipj[1] + H * (0.02 + look.shirt_len))
        bot_r = (hipj[0] + w * (0.82 + look.shirt_len * 2), hipj[1] + H * (0.02 + look.shirt_len))
        ctx.move_to(*top_l)
        ctx.line_to(*top_r)
        ctx.line_to(*bot_r)
        ctx.line_to(*bot_l)
        ctx.close_path()
        ctx.fill_preserve()
        ctx.set_source_rgb(*look.color)
        ctx.set_line_width(lw * 0.55)
        ctx.stroke()
        if look.shirt_text:
            ctx.select_font_face("Lilita One")
            ctx.set_font_size(H * 0.055)
            ext = ctx.text_extents(look.shirt_text)
            cx, cy = (shj[0] + hipj[0]) / 2, (shj[1] + hipj[1]) / 2 + H * 0.02
            ctx.move_to(cx - ext.width / 2 - ext.x_bearing, cy + ext.height / 2)
            ctx.set_source_rgb(1, 1, 1)
            ctx.show_text(look.shirt_text)
        ctx.restore()
    else:
        poly(hipj, neckj)

    if look.stain > 0:
        ctx.save()
        ctx.set_source_rgba(0.45, 0.26, 0.12, 0.92)
        cx, cy = (shj[0] + hipj[0]) / 2 + H * 0.01, (shj[1] + hipj[1]) / 2
        r = H * 0.075 * look.stain
        ctx.move_to(cx + r, cy)
        for k in range(1, 15):
            a = k / 14 * 2 * math.pi
            rr = r * (1 + 0.28 * noise("stain", k))
            ctx.line_to(cx + math.cos(a) * rr, cy + math.sin(a) * rr)
        ctx.close_path()
        ctx.fill()
        for k in range(3):
            ctx.arc(cx + r * (0.4 + 0.5 * k) * (1 if k % 2 else -1) * 0.8, cy + r * (1.25 + 0.35 * k), r * 0.16, 0, 2 * math.pi)
            ctx.fill()
        ctx.restore()

    hc = j(*head_c, "head")

    def arms():
        ctx.set_source_rgb(*look.color)
        ctx.set_line_width(lw)
        poly(shj, *L_arm)
        poly(shj, *R_arm)

    near_face = any(math.dist(h, hc) < hr * 1.4 for h in (L_arm[1], R_arm[1]))
    if not near_face:
        arms()

    # head
    ctx.arc(hc[0], hc[1], hr, 0, 2 * math.pi)
    ctx.set_source_rgb(*PAPER)
    ctx.fill_preserve()
    ctx.set_source_rgb(*look.color)
    ctx.set_line_width(lw * 0.9)
    ctx.stroke()
    _hair(ctx, hc, hr, look, lw, f)
    _face(ctx, hc, hr, face, look, lw, f, frame, ident)
    if near_face:
        arms()
    ctx.restore()
    return {"hip": hipj, "neck": neckj, "head": hc, "hr": hr, "lhand": L_arm[1], "rhand": R_arm[1],
            "lfoot": L_leg[1], "rfoot": R_leg[1], "shoulder": shj}


def _hair(ctx, c, r, look, lw, f):
    x, y = c
    ctx.save()
    ctx.set_line_width(lw * 0.8)
    if look.hair == "tuft":
        ctx.move_to(x - r * 0.2, y - r * 0.95)
        ctx.curve_to(x - r * 0.1, y - r * 1.5, x + r * 0.3, y - r * 1.4, x + r * 0.15 * f, y - r * 1.05)
        ctx.stroke()
    elif look.hair == "spiky":
        for k in (-0.55, -0.15, 0.25, 0.6):
            ctx.move_to(x + r * k, y - r * 0.85)
            ctx.line_to(x + r * (k + 0.12), y - r * 1.45)
            ctx.line_to(x + r * (k + 0.3), y - r * 0.85)
        ctx.stroke()
    elif look.hair == "bun":
        ctx.arc(x - r * 0.15 * f, y - r * 1.25, r * 0.38, 0, 2 * math.pi)
        ctx.fill()
    elif look.hair == "cap":
        ctx.set_source_rgb(*look.accent)
        ctx.arc(x, y - r * 0.15, r * 1.03, math.pi, 2 * math.pi)
        ctx.close_path()
        ctx.fill_preserve()
        ctx.set_source_rgb(*look.color)
        ctx.set_line_width(lw * 0.6)
        ctx.stroke()
        ctx.set_source_rgb(*look.accent)
        ctx.rectangle(x + (r * 0.2 if f > 0 else -r * 1.6), y - r * 0.28, r * 1.4, r * 0.2)
        ctx.fill()
    elif look.hair == "bow":
        ctx.set_source_rgb(*look.accent)
        bx, by = x + r * 0.55 * f, y - r * 0.9
        for s in (-1, 1):
            ctx.move_to(bx, by)
            ctx.line_to(bx + s * r * 0.45, by - r * 0.25)
            ctx.line_to(bx + s * r * 0.45, by + r * 0.25)
            ctx.close_path()
            ctx.fill()
    ctx.restore()


def _face(ctx, c, r, face: Face, look, lw, f, frame, ident):
    x, y = c
    ox = r * 0.18 * face.look[0] + r * 0.12 * f
    oy = r * 0.18 * face.look[1]
    ex = r * 0.32
    ey = y - r * 0.12 + oy
    blink = (frame + zlib.crc32(str(ident).encode()) % 97) % 97 < 4  # deterministic blinks
    eyes = "closed" if (blink and face.eyes in ("dot", "wide")) else face.eyes
    ctx.save()
    ctx.set_source_rgb(*look.color)
    for s in (-1, 1):
        cx = x + ox + s * ex
        if eyes == "dot":
            ctx.arc(cx, ey, r * 0.11, 0, 2 * math.pi)
            ctx.fill()
        elif eyes == "wide":
            ctx.set_source_rgb(1, 1, 1)
            ctx.arc(cx, ey, r * 0.24, 0, 2 * math.pi)
            ctx.fill_preserve()
            ctx.set_source_rgb(*look.color)
            ctx.set_line_width(lw * 0.35)
            ctx.stroke()
            ctx.arc(cx + r * 0.08 * face.look[0], ey + r * 0.08 * face.look[1], r * 0.1, 0, 2 * math.pi)
            ctx.fill()
        elif eyes == "closed":
            ctx.set_line_width(lw * 0.4)
            ctx.move_to(cx - r * 0.12, ey)
            ctx.line_to(cx + r * 0.12, ey)
            ctx.stroke()
        elif eyes == "happy":
            ctx.set_line_width(lw * 0.4)
            ctx.arc(cx, ey + r * 0.05, r * 0.13, math.pi * 1.1, math.pi * 1.9)
            ctx.stroke()
    if look.glasses:
        ctx.set_line_width(lw * 0.3)
        for s in (-1, 1):
            ctx.arc(x + ox + s * ex, ey, r * 0.26, 0, 2 * math.pi)
            ctx.stroke()
    if face.brows:
        ctx.set_line_width(lw * 0.35)
        for s in (-1, 1):
            bx = x + ox + s * ex
            by = ey - r * 0.38
            if face.brows == "worried":
                ctx.move_to(bx - r * 0.15 * s, by - r * 0.08)
                ctx.line_to(bx + r * 0.15 * s, by + r * 0.06)
            else:
                ctx.move_to(bx - r * 0.15, by - r * 0.04)
                ctx.line_to(bx + r * 0.15, by - r * 0.1)
            ctx.stroke()
    mx, my = x + ox, y + r * 0.38 + oy * 0.5
    ctx.set_line_width(lw * 0.4)
    if face.mouth == "smile":
        ctx.arc(mx, my - r * 0.18, r * 0.28, math.pi * 0.2, math.pi * 0.8)
        ctx.stroke()
    elif face.mouth == "grin":
        ctx.arc(mx, my - r * 0.12, r * 0.32, 0, math.pi)
        ctx.close_path()
        ctx.fill()
    elif face.mouth == "flat":
        ctx.move_to(mx - r * 0.18, my)
        ctx.line_to(mx + r * 0.18, my)
        ctx.stroke()
    elif face.mouth == "o":
        ctx.arc(mx, my, r * 0.13, 0, 2 * math.pi)
        ctx.fill()
    elif face.mouth == "frown":
        ctx.arc(mx, my + r * 0.2, r * 0.25, math.pi * 1.2, math.pi * 1.8)
        ctx.stroke()
    elif face.mouth == "wobble":
        ctx.move_to(mx - r * 0.25, my)
        for k in range(1, 7):
            ctx.line_to(mx - r * 0.25 + k * r * 0.5 / 6, my + (r * 0.06 if k % 2 else -r * 0.06))
        ctx.stroke()
    if look.mustache:
        ctx.set_source_rgb(*look.color)
        for s_ in (-1, 1):
            ctx.save()
            ctx.translate(mx + s_ * r * 0.17, my - r * 0.13)
            ctx.scale(r * 0.2, r * 0.08)
            ctx.arc(0, 0, 1, 0, 2 * math.pi)
            ctx.restore()
            ctx.fill()
    if face.blush:
        ctx.set_source_rgba(0.95, 0.35, 0.35, 0.45)
        for s in (-1, 1):
            ctx.arc(x + ox + s * r * 0.55, y + r * 0.22, r * 0.15, 0, 2 * math.pi)
            ctx.fill()
    ctx.restore()
