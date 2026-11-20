import flet as ft
import ui
from theme import *
from alert_engine import engine


def show(page, user_id, go_home):
    engine.mark_all_read()

    # ListView only builds the rows that are on screen
    items = ft.ListView(spacing=10, expand=True)
    state = {"empty": False}     # True while the "No notifications" row is shown

    def build_item(n):
        color = LEVEL_COLORS.get(n["level"], ACCENT)
        return ft.Container(
            padding=14, bgcolor=CARD_BG, border_radius=4,
            border=ft.Border.only(left=ft.BorderSide(3, color)),
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(n["level"].upper(), size=11, color=color,
                                    font_family=FONT,
                                    weight=ft.FontWeight.BOLD,
                                    style=ft.TextStyle(letter_spacing=2)),
                            ft.Text(n["time"], size=10, color=TEXT_DIM,
                                    font_family=FONT),
                        ],
                        spacing=2, tight=True, width=80,
                    ),
                    ft.Text(n["text"], size=13, color=TEXT,
                            font_family=FONT, expand=True),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def rebuild():
        items.controls.clear()
        snapshot = list(engine.notifications)   # copy: engine thread may insert
        state["empty"] = not snapshot
        if not snapshot:
            items.controls.append(
                ft.Container(
                    padding=40, alignment=ft.Alignment(0, 0),
                    content=ft.Text("No notifications", color=TEXT_DIM,
                                    font_family=FONT, size=13),
                )
            )
        else:
            for n in snapshot:
                items.controls.append(build_item(n))

    def on_event(kind, data=None):
        if kind == "alert" and data:
            engine.mark_all_read()     # we are looking at the list right now
            if state["empty"]:         # remove the placeholder row first
                items.controls.clear()
                state["empty"] = False
            items.controls.insert(0, build_item(data))   # only add the new one
            del items.controls[200:]   # same cap as MAX_NOTIFICATIONS
            ui.safe_update(page)

    def go_back():
        engine.unsubscribe(on_event)
        go_home()

    def clear_all(e):
        engine.notifications.clear()
        rebuild()
        page.update()

    rebuild()
    engine.subscribe(on_event)

    body = ft.Container(
        expand=True, padding=20,
        content=ft.Column(
            [
                ft.Row([ui.make_link("CLEAR ALL", clear_all)],
                       alignment=ft.MainAxisAlignment.END),
                items,
            ],
            expand=True,
        ),
    )

    ui.set_screen(page, ui.gradient_screen(
        ft.Column(
            [ui.page_header("NOTIFICATIONS",
                            ft.Icons.NOTIFICATIONS_OUTLINED, go_back),
             body],
            expand=True, spacing=0,
        )
    ))