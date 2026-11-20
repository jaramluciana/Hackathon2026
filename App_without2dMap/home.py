import flet as ft
import ui
from theme import *
from alert_engine import engine
import tools_launcher
from screens import medical, map3d, alerts, notifications, info, shelter_screen
from screens.sim_view import SimView


def show(page, user_id, level, name, go_login):
    is_admin = user_id.lower() == "admin"
    sv = SimView(page) if is_admin else None

    # ----- bell badge (unread count) -----
    unread = engine.unread_count()
    badge_text = ft.Text(str(unread) if unread < 100 else "99+", size=10, color="#ffffff",
                         font_family=FONT, weight=ft.FontWeight.BOLD)
    badge = ft.Container(
        width=20, height=20, border_radius=10, bgcolor="#c0392b",
        alignment=ft.Alignment(0, 0), content=badge_text,
        top=0, right=0, visible=unread > 0,
    )

    def on_event(kind, data=None):
        if kind == "alert":
            n = engine.unread_count()
            badge_text.value = str(n) if n < 100 else "99+"
            badge.visible = n > 0
            ui.safe_update(page, badge)   # update only the badge, not the page

    engine.subscribe(on_event)

    def leave(action):
        engine.unsubscribe(on_event)
        if sv:
            sv.detach()
        action()

    def back_here():
        show(page, user_id, level, name, go_login)

    def info_updated(new_name):
        nonlocal name
        name = new_name

    def open_tool(tool):
        result = tools_launcher.open_tool(tool)
        text = {"already": "This tool is already open.",
                "missing": "Tool file not found.",
                "error": "Cannot open the tool."}.get(result)
        if text:
            try:
                page.show_dialog(ft.SnackBar(ft.Text(text)))
            except Exception:
                pass

    top_bar = ft.Row(
        [ui.make_link("LEAVE", lambda e: leave(go_login))],
        alignment=ft.MainAxisAlignment.END,
    )

    center = ft.Column(
        [
            ui.abyss_logo(84),
            ft.Text("HOLLOW CITY", size=30, color=TEXT, font_family=FONT,
                    weight=ft.FontWeight.BOLD,
                    style=ft.TextStyle(letter_spacing=6)),
            ft.Text(f"WELCOME, {name.upper()}", size=11, color=TEXT_DIM,
                    font_family=FONT, style=ft.TextStyle(letter_spacing=4)),
            ft.Text(f"LEVEL {level}", size=13, color=ACCENT,
                    font_family=FONT, weight=ft.FontWeight.BOLD,
                    style=ft.TextStyle(letter_spacing=5)),
            ui.divider(),
            ft.Container(height=20),
            ft.Row(
                [
                    ui.make_tile(
                        ft.Icons.MEDICAL_SERVICES_OUTLINED, "MEDICAL",
                        lambda e: leave(lambda: medical.show(page, user_id, back_here))),
                    ui.make_tile(
                        ft.Icons.VIEW_IN_AR_OUTLINED, "3D MAP",
                        lambda e: leave(lambda: map3d.show(page, user_id, back_here))),
                    ui.make_tile(
                        ft.Icons.WARNING_AMBER_OUTLINED, "ALERT SYSTEM",
                        lambda e: leave(lambda: alerts.show(page, user_id, back_here))),
                    ui.make_tile(
                        ft.Icons.HOME_WORK_OUTLINED, "SHELTER",
                        lambda e: leave(lambda: shelter_screen.show(page, user_id, back_here))),
                    ui.make_tile(
                        ft.Icons.MENU_BOOK_OUTLINED, "SURVIVAL GUIDE",
                        lambda e: open_tool("guide")),
                    ui.make_tile(
                        ft.Icons.CALENDAR_MONTH_OUTLINED, "CALENDAR",
                        lambda e: open_tool("calendar")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                wrap=True, spacing=20, run_spacing=20,
            ),
            ft.Container(height=6),
            ui.make_button(
                "SHOW INFO",
                lambda e: leave(lambda: info.show(page, user_id, back_here,
                                                  info_updated))),
        ],
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=14,
    )

    bell = ft.Stack(
        [
            ui.make_bell(
                lambda e: leave(lambda: notifications.show(page, user_id, back_here))
            ),
            badge,
        ],
        width=60, height=60,
    )

    bottom = ft.Container(
        padding=ft.Padding.only(bottom=30),
        alignment=ft.Alignment(0, 0),
        content=bell,
    )

    middle = ft.Column([top_bar, center, bottom], expand=True,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    if is_admin:
        layout = ft.Column(
            [
                sv.header,
                ft.Row([sv.left, middle, sv.right], expand=True,
                       vertical_alignment=ft.CrossAxisAlignment.STRETCH),
                sv.footer,
            ],
            expand=True, spacing=0,
        )
    else:
        layout = middle

    if sv:
        sv.attach()          # paint the last snapshot before the first render
    ui.set_screen(page, ui.gradient_screen(layout))