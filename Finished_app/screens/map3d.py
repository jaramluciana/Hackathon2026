"""Surface map: sectors from Explore_Sectors drawn on a grid with hazard zones,
routes from the base, resource icons and a compass."""
import flet as ft
import flet.canvas as cv
import ui
import explore_sql as ex
from theme import *
from screens.medical import _card, _txt, _friendly

W, H, M, PIN = 760, 520, 44, 30          # canvas, inner margin, pin diameter
GW, GH = W - 2 * M, H - 2 * M            # drawable area

ICONS = {"water": ft.Icons.WATER_DROP, "equipment": ft.Icons.BUILD,
         "food": ft.Icons.RESTAURANT, "none": ft.Icons.HOME,
         "unknown": ft.Icons.HELP_OUTLINE}


def _color(s):
    if s["status"] == "base":
        return ACCENT
    h = s["hazard"]
    if h <= 25:
        return LEVEL_COLORS["Normal"]
    if h <= 50:
        return LEVEL_COLORS["Yellow"]
    if h <= 75:
        return LEVEL_COLORS["Orange"]
    return LEVEL_COLORS["Red"]


def _alpha(color, aa):
    """'#rrggbb' -> '#aarrggbb' (Flet uses alpha first)."""
    return f"#{aa}{color[1:]}"


def _px(x):
    return M + x / 100 * GW


def _py(y):
    return M + y / 100 * GH


def _background_shapes(sectors):
    paint = lambda c, w=1, fill=False: ft.Paint(
        color=c, stroke_width=w,
        style=ft.PaintingStyle.FILL if fill else ft.PaintingStyle.STROKE)
    shapes = []

    # soft terrain patches (decorative)
    for fx, fy, r in ((0.15, 0.72, 90), (0.55, 0.30, 110), (0.82, 0.78, 80),
                      (0.30, 0.20, 70), (0.70, 0.55, 60)):
        shapes.append(cv.Circle(M + fx * GW, M + fy * GH, r,
                                paint=paint("#0fc9b37e", fill=True)))

    # grid: a line every 10 units, brighter every 50
    for i in range(11):
        major = i % 5 == 0
        c = _alpha(ACCENT_DIM, "88" if major else "33")
        x, y = M + i * GW / 10, M + i * GH / 10
        shapes.append(cv.Line(x, M, x, M + GH, paint=paint(c)))
        shapes.append(cv.Line(M, y, M + GW, y, paint=paint(c)))

    # hazard zones: radius grows with hazard
    for s in sectors:
        if s["status"] == "base":
            continue
        col = _color(s)
        r = 26 + s["hazard"] * 0.55
        shapes.append(cv.Circle(_px(s["x"]), _py(s["y"]), r,
                                paint=paint(_alpha(col, "1c"), fill=True)))
        shapes.append(cv.Circle(_px(s["x"]), _py(s["y"]), r,
                                paint=paint(_alpha(col, "66"), 1)))

    # routes from the base to every sector that can be reached
    base = next((s for s in sectors if s["status"] == "base"), None)
    if base:
        for s in sectors:
            if s is base:
                continue
            ok = s["status"] != "hazardous"
            shapes.append(cv.Line(
                _px(base["x"]), _py(base["y"]), _px(s["x"]), _py(s["y"]),
                paint=paint(_alpha(ACCENT if ok else LEVEL_COLORS["Red"],
                                   "77" if ok else "33"), 1.5 if ok else 1)))
    return shapes


def show(page, user_id, go_home):
    detail = ft.Column(spacing=6)
    detail.controls = [_txt("Click a sector on the map.", TEXT_DIM, 12)]
    holder = ft.Column(spacing=16,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    pin_refs = {}
    chosen = {"code": None}

    try:
        sectors = ex.list_sectors()
        missions = ex.list_missions(user_id)
    except Exception as exc:
        hint = ("Run sql/04_explore.sql in SSMS first."
                if "Explore_" in str(exc) or "Invalid object" in str(exc) else "")
        sectors, missions = [], []
        holder.controls.append(_card("MAP UNAVAILABLE", [
            _txt(_friendly(exc), ERROR, 12), _txt(hint, TEXT_DIM, 12)]))

    def select(s):
        old = pin_refs.get(chosen["code"])
        if old:
            old.border = ft.Border.all(2, TEXT)
        chosen["code"] = s["code"]
        pin_refs[s["code"]].border = ft.Border.all(3, "#ffffff")

        rows = [
            _txt(f"{s['code']}  {s['name']}", ACCENT, 14,
                 weight=ft.FontWeight.BOLD),
            _txt(f"Status: {s['status']}   |   Hazard: {s['hazard']}   |   "
                 f"Resource: {s['resource']}", TEXT, 12),
            _txt(f"Survey confidence: {s['confidence'] * 100:.0f}%", TEXT_DIM, 12),
            _txt(s["notes"], TEXT, 12),
        ]
        rows += [_txt(f"Mission: {m['title']} ({m['status']}, reward {m['reward']})",
                      LEVEL_COLORS["Normal"], 12)
                 for m in missions if m["sector"] == s["code"]]
        if s["status"] == "hazardous":
            rows.append(_txt("NO ACCESS: hazard too high.", ERROR, 12))
        detail.controls = rows
        ui.safe_update(page)

    if sectors:
        layers = [cv.Canvas(shapes=_background_shapes(sectors), width=W, height=H)]

        # axis numbers
        for i in range(0, 101, 20):
            layers.append(ft.Text(str(i), size=9, color=TEXT_DIM, font_family=FONT,
                                  left=M + i / 100 * GW - 8, top=M - 18))
            layers.append(ft.Text(str(i), size=9, color=TEXT_DIM, font_family=FONT,
                                  left=M - 28, top=M + i / 100 * GH - 6))

        # pins + labels
        for s in sectors:
            col = _color(s)
            px, py = _px(s["x"]), _py(s["y"])
            icon = ICONS.get(s["resource"], ft.Icons.HELP_OUTLINE)
            if s["status"] == "hazardous":
                icon = ft.Icons.WARNING_AMBER_OUTLINED
            pin = ft.Container(
                left=px - PIN / 2, top=py - PIN / 2, width=PIN, height=PIN,
                border_radius=PIN, bgcolor=col, ink=True,
                border=ft.Border.all(2, TEXT), alignment=ft.Alignment(0, 0),
                opacity=0.6 if s["status"] == "unexplored" else 1,
                tooltip=f"{s['code']} {s['name']}",
                on_click=lambda e, s=s: select(s),
                content=ft.Icon(icon, size=16, color="#0b0d12"))
            pin_refs[s["code"]] = pin
            layers.append(pin)
            layers.append(ft.Container(
                left=px - 60, top=py + PIN / 2 + 2, width=120,
                alignment=ft.Alignment(0, 0),
                content=ft.Text(f"{s['code']} {s['name']}", size=10, color=TEXT,
                                font_family=FONT, text_align=ft.TextAlign.CENTER)))

        # compass (top right) and scale bar (bottom left)
        layers.append(ft.Container(
            right=12, top=8,
            content=ft.Column([ft.Text("N", size=11, color=ACCENT, font_family=FONT,
                                       weight=ft.FontWeight.BOLD),
                               ft.Icon(ft.Icons.NAVIGATION, size=22, color=ACCENT)],
                              spacing=0, tight=True,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER)))
        layers.append(ft.Row(
            [ft.Container(width=GW / 10, height=3, bgcolor=ACCENT),
             ft.Text("1 km (sim)", size=9, color=TEXT_DIM, font_family=FONT)],
            left=M, bottom=10, spacing=8))
        layers.append(ft.Text("SURFACE MAP", size=10, color=TEXT_DIM,
                              font_family=FONT, left=14, top=8,
                              style=ft.TextStyle(letter_spacing=4)))

        canvas = ft.Container(
            width=W, height=H, border_radius=4,
            border=ft.Border.all(1, ACCENT_DIM),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                colors=["#10171c", "#0a0d11"]),
            content=ft.Stack(layers))

        legend = ft.Row(
            [_txt("Hazard:", TEXT_DIM, 11),
             _txt("low", LEVEL_COLORS["Normal"], 11),
             _txt("medium", LEVEL_COLORS["Yellow"], 11),
             _txt("high", LEVEL_COLORS["Orange"], 11),
             _txt("extreme", LEVEL_COLORS["Red"], 11),
             _txt("base", ACCENT, 11),
             _txt("|  faded = unexplored  |  line = route from base", TEXT_DIM, 11)],
            spacing=14, wrap=True, alignment=ft.MainAxisAlignment.CENTER)
        holder.controls += [canvas, legend, _card("SECTOR DETAILS", [detail])]

    body = ft.Column([ft.Container(height=10), holder, ft.Container(height=20)],
                     scroll=ft.ScrollMode.AUTO, expand=True, spacing=16,
                     horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    ui.set_screen(page, ui.gradient_screen(
        ft.Column([ui.page_header("MAP", ft.Icons.VIEW_IN_AR_OUTLINED, go_home),
                   body], expand=True, spacing=0)))