#!/usr/bin/env python3
"""The Aquabrella -- a catalogue photograph of an impossible gadget.

A small umbrella on a gooseneck arm, clamped to the rim of a glass
goldfish bowl, photographed as a clean studio product shot while rain
falls all around it.  Splashes strike the canopy and shed off its edge;
the bowl alone stays dry.

Pure Python 3 standard library: a small software renderer (framebuffer,
signed-distance shapes, soft shadows) writes one PNG to
$MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).
"""

import math
import os
import random
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------------------
# framebuffer helpers
# ---------------------------------------------------------------------------

FB = bytearray(W * H * 3)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def blend(x, y, r, g, b, a):
    """Alpha-blend one pixel (a in 0..1)."""
    if a <= 0.0 or x < 0 or y < 0 or x >= W or y >= H:
        return
    i = (y * W + x) * 3
    ia = 1.0 - a
    FB[i] = int(FB[i] * ia + r * a + 0.5)
    FB[i + 1] = int(FB[i + 1] * ia + g * a + 0.5)
    FB[i + 2] = int(FB[i + 2] * ia + b * a + 0.5)


def set_px(x, y, r, g, b):
    i = (y * W + x) * 3
    FB[i] = int(clamp(r, 0, 255) + 0.5)
    FB[i + 1] = int(clamp(g, 0, 255) + 0.5)
    FB[i + 2] = int(clamp(b, 0, 255) + 0.5)


def get_px(x, y):
    i = (y * W + x) * 3
    return FB[i], FB[i + 1], FB[i + 2]


# ---------------------------------------------------------------------------
# shape fills.  A colour function takes (x, y) and returns (r, g, b, a).
# ---------------------------------------------------------------------------

def fill_ellipse(cx, cy, rx, ry, colour, soft=1.6):
    x0 = max(0, int(cx - rx - 2))
    x1 = min(W - 1, int(cx + rx + 2))
    y0 = max(0, int(cy - ry - 2))
    y1 = min(H - 1, int(cy + ry + 2))
    edge = min(rx, ry)
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            q = math.sqrt(dx * dx + dy * dy)
            cov = clamp((1.0 - q) * edge / soft + 0.5, 0.0, 1.0)
            if cov > 0.0:
                r, g, b, a = colour(x, y)
                blend(x, y, r, g, b, a * cov)


def _seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else clamp((wx * vx + wy * vy) / L2, 0.0, 1.0)
    dx = wx - t * vx
    dy = wy - t * vy
    return math.sqrt(dx * dx + dy * dy), t


def fill_polygon(points, colour, soft=1.6):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0 = max(0, int(min(xs) - 2))
    x1 = min(W - 1, int(max(xs) + 2))
    y0 = max(0, int(min(ys) - 2))
    y1 = min(H - 1, int(max(ys) + 2))
    n = len(points)
    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            # winding: count crossings of a ray to the right
            inside = False
            dmin = 1e18
            for (ax, ay), (bx, by) in edges:
                if (ay > y) != (by > y):
                    xin = ax + (y - ay) * (bx - ax) / (by - ay)
                    if x < xin:
                        inside = not inside
                d, _t = _seg_dist(x, y, ax, ay, bx, by)
                if d < dmin:
                    dmin = d
            if inside:
                cov = clamp(dmin / soft + 0.5, 0.0, 1.0)
            else:
                cov = clamp(0.5 - dmin / soft, 0.0, 1.0)
            if cov > 0.0:
                r, g, b, a = colour(x, y)
                blend(x, y, r, g, b, a * cov)


def fill_tube(points, radius, colour, soft=1.6):
    """A smooth thick line through points (round joints and caps)."""
    for i in range(len(points) - 1):
        ax, ay = points[i]
        bx, by = points[i + 1]
        x0 = max(0, int(min(ax, bx) - radius - 2))
        x1 = min(W - 1, int(max(ax, bx) + radius + 2))
        y0 = max(0, int(min(ay, by) - radius - 2))
        y1 = min(H - 1, int(max(ay, by) + radius + 2))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                d, t = _seg_dist(x, y, ax, ay, bx, by)
                cov = clamp((radius - d) / soft + 0.5, 0.0, 1.0)
                if cov > 0.0:
                    r, g, b, a = colour(x, y, t)
                    blend(x, y, r, g, b, a * cov)
    for px, py in points[1:-1]:
        fill_ellipse(px, py, radius, radius, lambda x, y: colour(x, y, 0.5), soft)


def fill_region(x0, y0, x1, y1, inside, colour):
    """Hard-edged fill of an arbitrary region (used for clipped contents)."""
    for y in range(max(0, y0), min(H - 1, y1) + 1):
        for x in range(max(0, x0), min(W - 1, x1) + 1):
            if inside(x, y):
                r, g, b, a = colour(x, y)
                blend(x, y, r, g, b, a)


# ---------------------------------------------------------------------------
# palette
# ---------------------------------------------------------------------------

def shade(rgb, f):
    return (rgb[0] * f, rgb[1] * f, rgb[2] * f)


CANOPY_RED = (198, 42, 40)
METAL = (66, 70, 75)
WOOD = (158, 111, 66)


# ---------------------------------------------------------------------------
# backdrop: seamless studio sweep with a soft spotlight
# ---------------------------------------------------------------------------

def paint_backdrop():
    for y in range(H):
        if y < 648:
            t = y / 648.0
            top = (226, 231, 234)
            mid = (203, 209, 213)
            r = top[0] + (mid[0] - top[0]) * t
            g = top[1] + (mid[1] - top[1]) * t
            b = top[2] + (mid[2] - top[2]) * t
        else:
            t = (y - 648) / (H - 648.0)
            r = 196 - 26 * t
            g = 198 - 24 * t
            b = 196 - 20 * t
        for x in range(W):
            # soft spotlight pool behind the product
            dx = (x - 512) / 560.0
            dy = (y - 430) / 520.0
            d2 = dx * dx + dy * dy
            glow = 13.0 * max(0.0, 1.0 - d2)
            # gentle corner vignette
            vx = (x - 512) / 724.0
            vy = (y - 512) / 724.0
            vig = 1.0 - 0.10 * max(0.0, vx * vx + vy * vy - 0.35)
            set_px(x, y, (r + glow) * vig, (g + glow) * vig, (b + glow) * vig)


# ---------------------------------------------------------------------------
# soft shadows (mask + separable box blur, then multiply)
# ---------------------------------------------------------------------------

def paint_shadows():
    mask = bytearray(W * H)

    def blob(cx, cy, rx, ry, strength):
        x0 = max(0, int(cx - rx))
        x1 = min(W - 1, int(cx + rx))
        y0 = max(0, int(cy - ry))
        y1 = min(H - 1, int(cy + ry))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                q = dx * dx + dy * dy
                if q < 1.0:
                    v = int(strength * (1.0 - q) * (1.0 - q))
                    i = y * W + x
                    if v > mask[i]:
                        mask[i] = v

    blob(512, 990, 320, 34, 90)     # stand shadow on the floor
    blob(512, 726, 260, 20, 60)     # stand slab shadow

    # separable box blur, radius 9, two passes
    R = 9
    for _ in range(2):
        tmp = bytearray(W * H)
        for y in range(H):
            base = y * W
            acc = 0
            for x in range(-R, R + 1):
                acc += mask[base + clamp(x, 0, W - 1)]
            for x in range(W):
                tmp[base + x] = acc // (2 * R + 1)
                acc -= mask[base + clamp(x - R, 0, W - 1)]
                acc += mask[base + clamp(x + R + 1, 0, W - 1)]
        mask, tmp = tmp, mask
        for x in range(W):
            acc = 0
            for y in range(-R, R + 1):
                acc += mask[clamp(y, 0, H - 1) * W + x]
            for y in range(H):
                tmp[y * W + x] = acc // (2 * R + 1)
                acc -= mask[clamp(y - R, 0, H - 1) * W + x]
                acc += mask[clamp(y + R + 1, 0, H - 1) * W + x]
        mask, tmp = tmp, mask

    for i in range(W * H):
        m = mask[i]
        if m:
            f = 1.0 - m / 255.0 * 0.62
            j = i * 3
            FB[j] = int(FB[j] * f)
            FB[j + 1] = int(FB[j + 1] * f)
            FB[j + 2] = int(FB[j + 2] * f)


# ---------------------------------------------------------------------------
# rain (behind the product, so the product stays clean and dry)
# ---------------------------------------------------------------------------

def paint_rain(rng):
    for _ in range(190):
        x = rng.uniform(8, W - 8)
        y = rng.uniform(-20, H - 60)
        if 296 < x < 736 and 240 < y < 700:
            continue  # no streaks behind the bowl: it stays clean and dry
        ln = rng.uniform(24, 46)
        a = rng.uniform(0.10, 0.30)
        dx = -ln * 0.16
        fill_tube([(x, y), (x + dx, y + ln)], 1.1,
                  lambda px, py, t, a=a: (228, 240, 246, a), soft=1.0)
    # a few nearer streaks near the frame corners for depth
    for _ in range(26):
        x = rng.choice([rng.uniform(0, 130), rng.uniform(W - 130, W)])
        y = rng.uniform(0, H - 80)
        ln = rng.uniform(38, 62)
        a = rng.uniform(0.16, 0.30)
        fill_tube([(x, y), (x - ln * 0.16, y + ln)], 1.5,
                  lambda px, py, t, a=a: (230, 242, 248, a), soft=1.2)


# ---------------------------------------------------------------------------
# the stand: wooden top, dark legs
# ---------------------------------------------------------------------------

def wood_colour(x, y):
    grain = math.sin(y * 0.55 + 2.6 * math.sin(x * 0.013) + math.sin(x * 0.045) * 0.7)
    f = 0.94 + 0.07 * grain
    streak = 0.96 + 0.05 * math.sin(x * 0.11 + y * 1.7)
    r, g, b = shade(WOOD, f * streak)
    return (r, g, b, 1.0)


def paint_stand():
    # legs
    leg = lambda x, y: (74, 54, 36, 1.0)
    fill_polygon([(302, 712), (348, 712), (348, 986), (302, 986)], leg)
    fill_polygon([(676, 712), (722, 712), (722, 986), (676, 986)], leg)
    fill_polygon([(302, 712), (722, 712), (722, 742), (302, 742)],
                 lambda x, y: (52, 38, 25, 0.55))  # under-slab shade
    # tabletop slab: top face and front edge
    fill_polygon([(258, 690), (766, 690), (742, 716), (282, 716)],
                 lambda x, y: shade(wood_colour(x, y)[:3], 1.10) + (1.0,))
    fill_polygon([(282, 716), (742, 716), (742, 736), (282, 736)],
                 lambda x, y: shade(wood_colour(x, y)[:3], 0.78) + (1.0,))
    # a glossy smear of the bowl's reflection on the tabletop
    fill_ellipse(512, 706, 168, 13, lambda x, y: (214, 230, 233, 0.20))
    fill_ellipse(512, 700, 150, 8, lambda x, y: (206, 74, 62, 0.10))
    # the bowl's soft contact shadow, sitting on the tabletop
    def contact(x, y):
        dx = (x - 512) / 208.0
        dy = (y - 699) / 17.0
        q = dx * dx + dy * dy
        return (30, 26, 22, 0.36 * max(0.0, 1.0 - q) ** 1.5)
    fill_ellipse(512, 699, 208, 17, contact)


# ---------------------------------------------------------------------------
# the bowl and its contents
# ---------------------------------------------------------------------------

BCX, BRIM_Y, BRX, BRY = 512, 478, 198, 208  # bowl centre, rim, radii


def bowl_inside(x, y, shrink=0):
    dx = (x - BCX) / (BRX - shrink)
    dy = (y - BRIM_Y) / (BRY - shrink)
    return dx * dx + dy * dy <= 1.0 and y >= BRIM_Y - 14


def fill_bowl_glass(rgb, alpha, soft=1.6):
    """Glass tint clipped at the rim: a real bowl has no glass above it."""
    def colour(x, y):
        dx = (x - BCX) / BRX
        dy = (y - BRIM_Y) / BRY
        q = math.sqrt(dx * dx + dy * dy)
        cov = clamp((1.0 - q) * BRY / soft + 0.5, 0.0, 1.0)
        return (rgb[0], rgb[1], rgb[2], alpha * cov)
    fill_region(BCX - BRX - 2, BRIM_Y - 16, BCX + BRX + 2, BRIM_Y + BRY + 2,
                lambda x, y: y >= BRIM_Y - 16, colour)


def paint_bowl():
    # back glass
    fill_bowl_glass((196, 218, 224), 0.30)
    # water body
    fill_region(BCX - BRX, BRIM_Y - 10, BCX + BRX, BRIM_Y + BRY,
                lambda x, y: bowl_inside(x, y, 10) and y >= 502,
                lambda x, y: (140, 188, 200, 0.42))
    # gravel bed
    rng = random.Random(7101)
    fill_region(BCX - BRX, 596, BCX + BRX, BRIM_Y + BRY,
                lambda x, y: bowl_inside(x, y, 12) and y >= 606 + 26 * math.cos((x - BCX) / 150.0),
                lambda x, y: (188, 168, 132, 0.95))
    for _ in range(110):
        gx = BCX + rng.uniform(-168, 168)
        gy = 622 + rng.uniform(0, 44) + abs(gx - BCX) * 0.05
        if bowl_inside(gx, gy, 14):
            tone = rng.uniform(0.82, 1.12)
            base = shade((196, 176, 142), tone)
            fill_ellipse(gx, gy, rng.uniform(5, 11), rng.uniform(3.5, 6),
                         lambda x, y, c=base: (c[0], c[1], c[2], 0.95), soft=1.0)
    # plant: tapering blades rising from the gravel
    for bx, bend, hgt in [(556, -34, 128), (574, 10, 148), (592, 44, 112),
                          (540, -52, 96), (606, 66, 84)]:
        pts = []
        for i in range(9):
            t = i / 8.0
            pts.append((bx + bend * t * t, 640 - hgt * t))
        for rad, f in [(5.2, 0.85), (3.0, 1.05)]:
            fill_tube(pts, rad,
                      lambda x, y, t, f=f: shade((66, 138, 80), f) + (0.92,),
                      soft=1.2)
    # goldfish, mid-swim, facing right
    tail = [(424, 556), (388, 528), (394, 556), (388, 584)]
    fill_polygon(tail, lambda x, y: (244, 148, 54, 0.78))
    fill_ellipse(466, 556, 52, 23,
                 lambda x, y: (238 - (556 - y) * 1.1 if y < 556 else 226,
                               128 + abs(y - 556) * 0.8, 40, 1.0))
    fill_ellipse(470, 540, 30, 9, lambda x, y: (250, 178, 96, 0.55))  # back sheen
    fill_polygon([(452, 538), (470, 522), (478, 540)],
                 lambda x, y: (240, 140, 48, 0.8))                     # dorsal fin
    fill_ellipse(478, 566, 13, 6, lambda x, y: (242, 150, 56, 0.7))    # pectoral fin
    fill_ellipse(502, 550, 4.6, 4.6, lambda x, y: (24, 20, 18, 1.0))    # eye
    fill_ellipse(503.5, 548.5, 1.6, 1.6, lambda x, y: (255, 255, 255, 0.95))
    # a few rising bubbles
    for bx, by, br in [(596, 520, 4), (610, 486, 3), (588, 556, 2.6), (622, 528, 2.2)]:
        fill_ellipse(bx, by, br, br, lambda x, y: (240, 250, 252, 0.35), soft=0.8)
    # water surface
    fill_ellipse(BCX, 500, 178, 19, lambda x, y: (186, 220, 228, 0.55))
    fill_ellipse(BCX - 30, 498, 96, 8, lambda x, y: (240, 250, 252, 0.5))
    # front glass: faint tint plus a long curved highlight
    fill_bowl_glass((208, 230, 236), 0.13)
    hl = [(386, 520), (372, 580), (380, 636), (398, 660),
          (410, 636), (404, 576), (412, 528)]
    fill_polygon(hl, lambda x, y: (255, 255, 255, 0.30))
    fill_ellipse(648, 560, 12, 44, lambda x, y: (255, 255, 255, 0.16))
    # rim ring
    fill_ellipse(BCX, BRIM_Y, BRX, 25, lambda x, y: (188, 210, 216, 0.85))
    fill_ellipse(BCX, BRIM_Y, BRX - 17, 17, lambda x, y: (172, 205, 216, 0.9))
    fill_ellipse(BCX, BRIM_Y - 2, BRX - 17, 15, lambda x, y: (190, 220, 228, 0.65))


# ---------------------------------------------------------------------------
# gooseneck arm and clamp
# ---------------------------------------------------------------------------

def paint_arm():
    path = [(700, 492), (738, 442), (750, 372), (724, 292),
            (652, 240), (566, 222), (516, 226)]
    # dark brushed-metal body
    fill_tube(path, 13, lambda x, y, t: METAL + (1.0,))
    # top-left highlight stripe
    off = [(-4, -5)] * len(path)
    hl_path = [(px + ox, py + oy) for (px, py), (ox, oy) in zip(path, off)]
    fill_tube(hl_path, 4.5, lambda x, y, t: (168, 175, 180, 0.55), soft=1.4)
    # clamp gripping the bowl rim, with a screw knob
    fill_polygon([(676, 470), (724, 470), (724, 522), (676, 522)],
                 lambda x, y: shade(METAL, 0.92) + (1.0,))
    fill_polygon([(676, 470), (724, 470), (724, 482), (676, 482)],
                 lambda x, y: shade(METAL, 1.25) + (1.0,))
    fill_ellipse(700, 540, 11, 11, lambda x, y: shade(METAL, 0.8) + (1.0,))
    fill_tube([(700, 520), (700, 532)], 5, lambda x, y, t: shade(METAL, 0.9) + (1.0,))
    fill_ellipse(696, 536, 3.4, 3.4, lambda x, y: (190, 196, 200, 0.8))


# ---------------------------------------------------------------------------
# the canopy
# ---------------------------------------------------------------------------

APEX = (512, 196)
EDGE_Y = 322
TIPS = [(316, 306), (414, 330), (512, 338), (610, 330), (708, 306)]


def canopy_points():
    pts = []
    # dome: ellipse arc from the left tip over the apex to the right tip
    for i in range(41):
        t = i / 40.0
        ang = math.pi * (1.0 - t)
        x = 512 + 202 * math.cos(ang)
        y = 318 - 128 * math.sin(ang) ** 0.92
        pts.append((x, y))
    # scalloped lower edge, right tip back to left tip
    edge = [TIPS[-1]] + list(reversed(TIPS[:-1]))
    for i in range(len(edge) - 1):
        ax, ay = edge[i]
        bx, by = edge[i + 1]
        for j in range(1, 7):
            t = j / 6.0
            x = ax + (bx - ax) * t
            y = ay + (by - ay) * t - math.sin(t * math.pi) * 13
            pts.append((x, y))
    return pts


def canopy_colour(x, y):
    # radial studio light from the upper left, seams of shade between panels
    d = math.hypot(x - 400, y - 150) / 620.0
    f = 1.06 - 0.34 * d
    ang = math.atan2(y - 214, x - 512)
    panel = 0.965 + 0.035 * math.cos(ang * 5.0)
    r, g, b = shade(CANOPY_RED, f * panel)
    return (r, g, b, 1.0)


def paint_canopy():
    # short shaft and hub where the arm meets the canopy
    fill_tube([(514, 232), (512, 204)], 8, lambda x, y, t: METAL + (1.0,))
    fill_polygon(canopy_points(), canopy_colour)
    # ribs: soft darker seams from the hub to each tip
    for tx, ty in TIPS:
        fill_tube([(512, 210), ((512 + tx) / 2, (216 + ty) / 2 - 8), (tx, ty)],
                  2.2, lambda x, y, t: (150, 26, 26, 0.35), soft=1.6)
    # edge piping
    pts = canopy_points()
    fill_tube(pts[-24:] + pts[:2], 2.4, lambda x, y, t: (168, 32, 32, 0.5), soft=1.2)
    # finial knob on top
    fill_ellipse(512, 192, 9, 9, lambda x, y: shade(METAL, 1.05) + (1.0,))
    fill_ellipse(509, 189, 3, 3, lambda x, y: (200, 206, 210, 0.9))
    # wet sheen: a soft light pool on the upper-left of the dome
    fill_ellipse(448, 240, 62, 20, lambda x, y: (255, 216, 204, 0.11))


# ---------------------------------------------------------------------------
# splashes on the canopy and drips shedding off its edge
# ---------------------------------------------------------------------------

def paint_splashes(rng):
    # droplets bursting where rain strikes the dome
    for i in range(15):
        t = (i + rng.uniform(0.15, 0.85)) / 15.0
        ang = math.pi * (1.0 - t)
        cx = 512 + 196 * math.cos(ang)
        cy = 318 - 128 * math.sin(ang) ** 0.92
        cy -= 4
        for k in range(3):
            a = -math.pi / 2 + (k - 1) * 0.62 + rng.uniform(-0.1, 0.1)
            ln = rng.uniform(5, 10)
            fill_tube([(cx, cy), (cx + math.cos(a) * ln, cy + math.sin(a) * ln)],
                      1.15, lambda x, y, tt: (248, 252, 253, 0.85), soft=0.9)
        fill_ellipse(cx, cy, 2.0, 1.5, lambda x, y: (250, 253, 254, 0.9), soft=0.8)
    # beads sitting on the fabric
    for _ in range(26):
        t = rng.uniform(0.06, 0.94)
        ang = math.pi * (1.0 - t)
        cx = 512 + rng.uniform(150, 196) * math.cos(ang)
        cy = 318 - 122 * math.sin(ang) ** 0.92 + rng.uniform(2, 16)
        fill_ellipse(cx, cy, rng.uniform(1.4, 2.6), rng.uniform(1.0, 1.8),
                     lambda x, y: (252, 240, 238, 0.55), soft=0.8)
    # drips shedding from the scallop tips
    for tx, ty in TIPS:
        fill_tube([(tx, ty + 2), (tx, ty + 12)], 1.3,
                  lambda x, y, t: (232, 244, 248, 0.65), soft=0.9)
        fill_ellipse(tx, ty + 18, 3.0, 4.6, lambda x, y: (226, 240, 246, 0.8), soft=0.9)
        fill_ellipse(tx - 1, ty + 16, 1.1, 1.6, lambda x, y: (255, 255, 255, 0.9), soft=0.7)
    # one drip caught mid-fall
    fill_ellipse(610, 372, 2.8, 4.4, lambda x, y: (226, 240, 246, 0.75), soft=0.9)
    fill_tube([(610, 344), (610, 364)], 1.2, lambda x, y, t: (232, 244, 248, 0.5), soft=0.9)


# ---------------------------------------------------------------------------
# PNG writer
# ---------------------------------------------------------------------------

def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += FB[y * W * 3:(y + 1) * W * 3]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


def main():
    rng = random.Random(20261121)
    paint_backdrop()
    paint_rain(rng)
    paint_stand()
    paint_shadows()
    paint_bowl()
    paint_arm()
    paint_canopy()
    paint_splashes(rng)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    size = write_png(os.path.join(out_dir, "entry.png"))
    print("entry.png: %d bytes, %dx%d" % (size, W, H))


if __name__ == "__main__":
    main()
