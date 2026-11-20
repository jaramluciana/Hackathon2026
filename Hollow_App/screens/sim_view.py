import flet as ft
import ui
from theme import *
import hollow_sim as hs
from hollow_sim import (sim, EVENT_TYPES, SYSTEMS, pretty, severity_color,
                        hexc, text_on, AMBER, RED)
class SimView:
    def __init__(self, page):
        self.page = page
        self.selected = None
        self.cards = {}

        # ---------- header / footer ----------
        self.clock = ft.Text("", size=12, color=TEXT, font_family=FONT,
                             weight=ft.FontWeight.BOLD)
        self.alive = ft.Text("", size=12, color=TEXT, font_family=FONT)
        self.header = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            content=ft.Row(
                [ft.Text("THE HOLLOW  |  SIMULATION", size=11, color=TEXT_DIM,
                         font_family=FONT, style=ft.TextStyle(letter_spacing=3)),
                 ft.Row([self.alive, self.clock], spacing=24)],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        self.ticker = ft.Text("Starting simulation...", size=12, color=AMBER,
                              font_family=FONT)
        self.footer = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            content=self.ticker)

        # ---------- level list ----------
        for lvl in range(1, 11):
            self.cards[lvl] = self._make_card(lvl)
        self.left = ft.Container(
            width=300, padding=ft.Padding.only(left=12, top=4, bottom=4),
            content=ft.Column([c["box"] for c in self.cards.values()],
                              scroll=ft.ScrollMode.AUTO, spacing=8,
                              expand=True))

        # ---------- detail panel ----------
        self.p_title = ft.Text("", size=18, color="#ffffff", font_family=FONT,
                               weight=ft.FontWeight.BOLD)
        self.p_pop = ft.Text("", size=12, color=TEXT, font_family=FONT)
        self.p_health = ft.Text("", size=12, color=TEXT, font_family=FONT)

        self.bars = {}
        sys_rows = []
        for name in SYSTEMS:
            bar = ft.ProgressBar(value=1, width=120, bar_height=10,
                                 bgcolor="#2b2f3b")
            val = ft.Text("", size=11, color=TEXT, width=44, font_family=FONT)
            self.bars[name] = (bar, val)
            sys_rows.append(ft.Row(
                [ft.Text(pretty(name), size=11, color=TEXT, width=100,
                         font_family=FONT), bar, val], spacing=6))

        self.p_status = ft.Column(spacing=2)
        self.p_log = ft.Text("", size=10, color=TEXT_DIM, font_family=FONT)

        self.ev_choice = ft.Dropdown(
            width=190, value=EVENT_TYPES[0].name,
            options=[ft.DropdownOption(key=e.name, text=pretty(e.name))
                     for e in EVENT_TYPES],
            color=TEXT, bgcolor="#0b0e14", border_color=ACCENT_DIM,
            text_style=ft.TextStyle(font_family=FONT, size=12))

        def section(text):
            return ft.Text(text, size=10, color=TEXT_DIM, font_family=FONT,
                           weight=ft.FontWeight.BOLD,
                           style=ft.TextStyle(letter_spacing=3))

        self.right = ft.Container(
            width=360, padding=16, bgcolor=CARD_BG, visible=False,
            border=ft.Border.all(1, ACCENT_DIM), border_radius=4,
            margin=ft.Margin.only(right=12, top=4, bottom=4),
            content=ft.Column(
                [
                    ft.Row([self.p_title,
                            ft.IconButton(icon=ft.Icons.CLOSE, icon_size=18,
                                          icon_color=TEXT_DIM,
                                          on_click=lambda e: self.close())],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.p_pop, self.p_health,
                    section("SYSTEMS"), *sys_rows,
                    section("NEGATIVE STATUSES"), self.p_status,
                    section("RECENT LOG"), self.p_log,
                    section("TRIGGER EVENT HERE"),
                    ft.Row([self.ev_choice,
                            ft.Button(content=ft.Text("Trigger"),
                                      on_click=ui.once(lambda e: self.trigger()))],
                           spacing=8),
                ],
                scroll=ft.ScrollMode.AUTO, spacing=6))

    # ---------- building ----------
    def _make_card(self, lvl):
        title = ft.Text(f"LEVEL {lvl}", size=16, font_family=FONT,
                        weight=ft.FontWeight.BOLD)
        badge = ft.Text("", size=11, font_family=FONT,
                        weight=ft.FontWeight.BOLD)
        pop = ft.Text("", size=11, font_family=FONT)
        worst = ft.Text("", size=10, font_family=FONT)
        box = ft.Container(
            width=280, height=86, padding=14, border_radius=12,
            bgcolor="#3484f0", ink=True,
            animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, l=lvl: self.select(l),
            content=ft.Column(
                [ft.Row([title, badge],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                 pop, worst],
                spacing=4, tight=True))
        return dict(box=box, title=title, badge=badge, pop=pop, worst=worst)

    # ---------- life cycle ----------
    def attach(self):
        sim.listener = self.on_snapshot
        if sim.last_snapshot:
            self.paint(sim.last_snapshot)

    def detach(self):
        if sim.listener == self.on_snapshot:
            sim.listener = None

    def on_snapshot(self, snap):
        self.paint(snap)
        try:
            self.page.update()
        except Exception:
            pass

    # ---------- actions ----------
    def select(self, lvl):
        self.selected = lvl
        sim.selected = lvl
        self.right.visible = True
        if sim.last_snapshot:
            self.paint(sim.last_snapshot)
        self.page.update()

    def close(self):
        self.selected = None
        sim.selected = None
        self.right.visible = False
        self.page.update()

    def trigger(self):
        if self.selected and self.ev_choice.value:
            sim.trigger(self.ev_choice.value, self.selected)

    # ---------- painting ----------
    def paint(self, snap):
        self.clock.value = snap["clock"]
        self.alive.value = f"Alive {snap['alive']:,} / {snap['pop']:,}"
        self.ticker.value = f"\u25b8 {snap['ticker']}"

        for lvl, d in snap["levels"].items():
            c = self.cards.get(lvl)
            if not c:
                continue
            rgb = severity_color(d["worst"])
            fg = text_on(rgb)
            c["box"].bgcolor = hexc(rgb)
            for k in ("title", "badge", "pop", "worst"):
                c[k].color = fg
            n = len(d["statuses"])
            c["badge"].value = f"{n} alert{'s' if n != 1 else ''}" if n else ""
            c["pop"].value = f"Alive {d['alive']:,} / {d['pop']:,}"
            c["worst"].value = f"Weakest: {pretty(d['wname'])} {d['worst']:.0f}%"

        sel = self.selected
        if sel and sel in snap["levels"]:
            d = snap["levels"][sel]
            self.p_title.value = f"Level {sel}"
            self.p_pop.value = f"Population  {d['alive']:,} alive / {d['pop']:,}"
            ah = snap["avg_health"]
            self.p_health.value = ("Avg health (living)  "
                                   + (f"{ah:.1f}" if ah is not None else "-"))
            for name, (bar, val) in self.bars.items():
                v = d["systems"].get(name, 0)
                bar.value = max(0.0, min(1.0, v / 100))
                bar.color = hexc(severity_color(v))
                val.value = f"{v:.0f}%"
            if d["statuses"]:
                self.p_status.controls = [
                    ft.Text("\u25cf " + t, size=11, color=col, font_family=FONT)
                    for t, col in d["statuses"]]
            else:
                self.p_status.controls = [
                    ft.Text("None - all clear", size=11, color="#6ee7a0",
                            font_family=FONT)]
            self.p_log.value = "\n".join(snap["log"]) or "No events yet"