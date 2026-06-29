import math
from PIL import Image, ImageDraw

STATUS_COLORS = {
    'listening':      '#22C55E',
    'paused':         '#B45309',
    'disconnected':   '#6B7280',
    'not_in_channel': '#3B82F6',
}

_ICON_BG = '#1C1C1A'
_ICON_FG = '#FFFFFF'
_CACHE: dict = {}

def clear_cache():
    _CACHE.clear()

_OVERSAMPLE = 4


def make_icon(status: str = 'disconnected', size: int = 64) -> Image.Image:
    key = (status, size)
    if key in _CACHE:
        return _CACHE[key]

    s = size * _OVERSAMPLE
    img  = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def p(frac):
        return frac * s

    # ── background ───────────────────────────────────────────────────────────
    m = p(0.08)
    draw.rounded_rectangle([m, m, s - m, s - m], radius=p(0.20), fill=_ICON_BG)

    # ── headphone band ────────────────────────────────────────────────────────
    # Arc bbox defines an ellipse; we calculate the exact endpoints at 210° and
    # 330° so the ear cups can be positioned to connect flush with the arc ends.
    ax0, ay0, ax1, ay1 = p(0.20), p(0.24), p(0.80), p(0.64)
    arc_cx = (ax0 + ax1) / 2
    arc_cy = (ay0 + ay1) / 2
    arc_rx = (ax1 - ax0) / 2
    arc_ry = (ay1 - ay0) / 2
    start_deg, end_deg = 210, 330

    # PIL arc angles: 0° = 3-o'clock, increases clockwise
    lx = arc_cx + arc_rx * math.cos(math.radians(start_deg))
    ly = arc_cy + arc_ry * math.sin(math.radians(start_deg))
    rx = arc_cx + arc_rx * math.cos(math.radians(end_deg))
    ry = arc_cy + arc_ry * math.sin(math.radians(end_deg))

    band_w = max(3, round(p(0.07)))
    draw.arc([ax0, ay0, ax1, ay1], start=start_deg, end=end_deg,
             fill=_ICON_FG, width=band_w)

    # ── ear cups — centered on arc endpoints, top flush with arc end ──────────
    ecw = p(0.16)
    ech = p(0.30)
    er  = max(3, round(p(0.05)))

    # left ear cup: centered horizontally on arc left endpoint
    lx0 = lx - ecw / 2
    draw.rounded_rectangle([lx0, ly, lx0 + ecw, ly + ech], radius=er, fill=_ICON_FG)

    # right ear cup
    rx0 = rx - ecw / 2
    draw.rounded_rectangle([rx0, ry, rx0 + ecw, ry + ech], radius=er, fill=_ICON_FG)

    # ── pause bars — narrow, centered, same vertical zone as ear cups ─────────
    cx   = s / 2
    pb_w = max(3, round(p(0.058)))
    pb_g = max(3, round(p(0.050)))
    pb_y0 = ly + p(0.03)
    pb_y1 = ly + ech - p(0.03)
    pb_r  = max(2, round(p(0.03)))

    draw.rounded_rectangle([cx - pb_g - pb_w, pb_y0, cx - pb_g, pb_y1], radius=pb_r, fill=_ICON_FG)
    draw.rounded_rectangle([cx + pb_g, pb_y0, cx + pb_g + pb_w, pb_y1],  radius=pb_r, fill=_ICON_FG)

    # ── status dot — small badge overlay, bottom-right ────────────────────────
    color = STATUS_COLORS.get(status, STATUS_COLORS['disconnected'])
    dot_r = max(3, round(p(0.10)))
    dx = s - m - dot_r + round(p(0.02))
    dy = s - m - dot_r + round(p(0.02))
    halo = max(2, round(p(0.04)))
    draw.ellipse([dx - dot_r - halo, dy - dot_r - halo,
                  dx + dot_r + halo, dy + dot_r + halo], fill=_ICON_BG)
    draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=color)

    result = img.resize((size, size), Image.LANCZOS)
    _CACHE[key] = result
    return result
