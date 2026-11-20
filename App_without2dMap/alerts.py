import flet as ft
import ui
from theme import *
from alert_engine import engine, alert_level


def show(page, user_id, go_home):
    refs = []
    # shown[0] = light, shown[1] = oxygen of the logged-in level
    shown = [engine.sensors[0], engine.sensors[engine.level]]

    def paint(ref, s):
        ratio = s.remaining_ratio()
        level = "Red" if s.depleted else alert_level(ratio)
        color = LEVEL_COLORS[level]
        left = s.time_left()

        ref["value"].value = f"{max(0, s.value):.2f}"
        ref["percent"].value = f"{ratio:.1f}%"
        ref["bar"].value = max(0.0, min(1.0, ratio / 100))
        ref["bar"].color = color
        ref["status"].value = "DEPLETED" if s.depleted else level.upper()
        ref["status"].color = color
        ref["left"].value = ("Time left: --" if left is None
                             else f"Time left: {max(0, left):.0f}s")
        ref["card"].border = ft.Border.all(
            1, color if level != "Normal" else ACCENT_DIM)

    def build_card(s):
        """Same card for light and oxygen."""
        title = ft.Text(s.label, size=13, color=TEXT, font_family=FONT,
                        weight=ft.FontWeight.BOLD,
                        style=ft.TextStyle(letter_spacing=3))
        status = ft.Text("", size=11, font_family=FONT,
                         weight=ft.FontWeight.BOLD,
                         style=ft.TextStyle(letter_spacing=2))
        value = ft.Text("", size=32, color=TEXT, font_family=FONT)
        percent = ft.Text("", size=14, color=TEXT_DIM, font_family=FONT)
        bar = ft.ProgressBar(value=1, bgcolor="#1c2230", bar_height=8)
        left = ft.Text("", size=11, color=TEXT_DIM, font_family=FONT)

        card = ft.Container(
            width=440, padding=20, bgcolor=CARD_BG,
            border=ft.Border.all(1, ACCENT_DIM), border_radius=4,
            content=ft.Column(
                [
                    ft.Row([title, status],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([value, percent],
                           vertical_alignment=ft.CrossAxisAlignment.END,
                           spacing=12),
                    bar,
                    left,
                ],
                spacing=10,
            ),
        )
        ref = dict(card=card, value=value, percent=percent, bar=bar,
                   status=status, left=left)
        paint(ref, s)
        return ref

    def on_event(kind, data=None):
        if kind == "tick":
            # engine ticks every 0.5s -> repaint every 2 ticks (1s)
            if engine.t % 2 == 0 or all(s.depleted for s in shown):
                for ref, s in zip(refs, shown):
                    paint(ref, s)
                ui.safe_update(page)

    def go_back():
        engine.unsubscribe(on_event)
        go_home()

    def restart(e):
        engine.restart()
        shown[0] = engine.sensors[0]
        shown[1] = engine.sensors[engine.level]
        for ref, s in zip(refs, shown):
            paint(ref, s)
        page.update()

    refs.append(build_card(shown[0]))   # light
    refs.append(build_card(shown[1]))   # oxygen, same look as light

    body = ft.Column(
        [ft.Container(height=20),
         refs[0]["card"],
         refs[1]["card"],
         ft.Container(height=6),
         ui.make_button("RESTART SIMULATION", restart),
         ft.Container(height=20)],
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=16,
        expand=True,
    )

    ui.set_screen(page, ui.gradient_screen(
        ft.Column(
            [ui.page_header("ALERT SYSTEM",
                            ft.Icons.WARNING_AMBER_OUTLINED, go_back),
             body],
            expand=True, spacing=0,
        )
    ))
    engine.subscribe(on_event)   # subscribe only after the screen is visible