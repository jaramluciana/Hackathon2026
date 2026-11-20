import flet as ft
import threading
import time
from theme import *


def once(fn, cooldown=1.0):
    """Wrap a click handler so it runs only once at a time.
    Extra clicks while it is running, or within `cooldown` seconds after it
    finishes, are ignored (this also swallows clicks that queued up while
    the app was busy)."""
    state = {"busy": False}

    def release():
        state["busy"] = False

    def wrapper(*args, **kwargs):
        if state["busy"]:
            return
        state["busy"] = True
        try:
            return fn(*args, **kwargs)
        finally:
            t = threading.Timer(cooldown, release)
            t.daemon = True
            t.start()

    return wrapper

def abyss_logo(size=72):
    void = ft.Container(
        width=size * 0.36, height=size * 0.36, border_radius=size,
        bgcolor="#000000",
        border=ft.Border.all(1, ACCENT_DIM),
        shadow=ft.BoxShadow(blur_radius=size * 0.35, spread_radius=1,
                            color="#66c9b37e"),
    )
    middle = ft.Container(
        width=size * 0.68, height=size * 0.68, border_radius=size,
        border=ft.Border.all(1, ACCENT),
        alignment=ft.Alignment(0, 0), content=void,
    )
    return ft.Container(
        width=size, height=size, border_radius=size,
        border=ft.Border.all(1, ACCENT_DIM),
        alignment=ft.Alignment(0, 0), content=middle,
    )


def make_field(label, icon, is_password=False, on_submit=None):
    return ft.TextField(
        label=label, prefix_icon=icon,
        password=is_password, can_reveal_password=is_password,
        width=320, color=TEXT, cursor_color=ACCENT, bgcolor="#0b0e14",
        border_color=ACCENT_DIM, focused_border_color=ACCENT, border_radius=2,
        label_style=ft.TextStyle(color=TEXT_DIM, size=12, font_family=FONT),
        text_style=ft.TextStyle(font_family=FONT, size=15),
        on_submit=on_submit,
    )


def make_button(text, on_click):
    return ft.Button(
        content=ft.Text(text, size=14, font_family=FONT,
                        weight=ft.FontWeight.BOLD),
        width=320, height=46, on_click=once(on_click),
        style=ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: ACCENT,
                   ft.ControlState.HOVERED: "#0b0d12"},
            bgcolor={ft.ControlState.DEFAULT: "#00000000",
                     ft.ControlState.HOVERED: ACCENT},
            side=ft.BorderSide(1, ACCENT),
            shape=ft.RoundedRectangleBorder(radius=2),
            animation_duration=250,
        ),
    )


def make_link(text, on_click):
    return ft.TextButton(
        content=ft.Text(text, size=12, color=TEXT_DIM, font_family=FONT),
        on_click=once(on_click),
        )


def divider():
    return ft.Container(width=120, height=1, bgcolor=ACCENT_DIM)


def glow_on_hover(e):
    hovered = str(e.data).lower() == "true"
    e.control.border = ft.Border.all(1, ACCENT if hovered else ACCENT_DIM)
    e.control.shadow = ft.BoxShadow(blur_radius=30 if hovered else 0,
                                    color="#44c9b37e")
    e.control.update()


def make_tile(icon, label, on_click):
    return ft.Container(
        width=130, height=130, bgcolor=CARD_BG,
        border=ft.Border.all(1, ACCENT_DIM), border_radius=4,
        alignment=ft.Alignment(0, 0), ink=True,
        on_click=once(on_click), on_hover=glow_on_hover,
        animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        content=ft.Column(
            [
                ft.Icon(icon, size=40, color=ACCENT),
                ft.Text(label, size=11, color=TEXT, font_family=FONT,
                        style=ft.TextStyle(letter_spacing=2),
                        text_align=ft.TextAlign.CENTER),
            ],
            tight=True, spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def make_bell(on_click):
    return ft.Container(
        width=56, height=56, border_radius=28, bgcolor=CARD_BG,
        border=ft.Border.all(1, ACCENT_DIM),
        alignment=ft.Alignment(0, 0), ink=True,
        on_click=once(on_click), on_hover=glow_on_hover,
        animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        content=ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, size=26, color=ACCENT),
    )


def gradient_screen(content):
    return ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
            colors=[BG_TOP, BG_BOTTOM],
        ),
        content=content,
    )


def wrap_screen(card_content):
    """Centered framed card (login / register)."""
    return ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
            colors=[BG_TOP, BG_BOTTOM],
        ),
        alignment=ft.Alignment(0, 0),
        content=ft.Container(
            width=420, padding=40, bgcolor=CARD_BG,
            border=ft.Border.all(1, ACCENT_DIM), border_radius=4,
            shadow=ft.BoxShadow(blur_radius=60, color="#33c9b37e",
                                spread_radius=1),
            content=card_content,
        ),
    )


def title_block(title, subtitle):
    return [
        abyss_logo(72),
        ft.Text(title, size=30, color=TEXT, font_family=FONT,
                weight=ft.FontWeight.BOLD,
                style=ft.TextStyle(letter_spacing=6)),
        ft.Text(subtitle, size=11, color=TEXT_DIM, font_family=FONT,
                style=ft.TextStyle(letter_spacing=4)),
        divider(),
        ft.Container(height=10),
    ]


def page_header(title, icon, on_back):
    """Top bar with back arrow, icon and title (used by every sub page)."""
    return ft.Column(
        [
            ft.Container(
                padding=10,
                content=ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.ARROW_BACK,
                                      icon_color=ACCENT,
                                      on_click=once(lambda e: on_back())),
                        ft.Icon(icon, size=22, color=ACCENT),
                        ft.Text(title, size=16, color=TEXT, font_family=FONT,
                                weight=ft.FontWeight.BOLD,
                                style=ft.TextStyle(letter_spacing=4)),
                    ],
                    spacing=10,
                ),
            ),
            ft.Container(height=1, bgcolor=ACCENT_DIM),
        ],
        spacing=0,
    )
    
def show_loading(page, text="LOADING"):
    """Full-screen spinner."""
    page.controls.clear()
    page.add(
        gradient_screen(
            ft.Column(
                [
                    abyss_logo(72),
                    ft.Container(height=10),
                    ft.ProgressRing(width=40, height=40, stroke_width=3,
                                    color=ACCENT),
                    ft.Container(height=6),
                    ft.Text(text, size=11, color=TEXT_DIM, font_family=FONT,
                            style=ft.TextStyle(letter_spacing=5)),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                spacing=12,
            )
        )
    )
    page.update()


def run_with_loading(page, work, text="LOADING", min_seconds=0):
    """Show the spinner, run work() in a background thread, and make sure the
    spinner is visible for about min_seconds in total.

    work() is split in two: it may return a function `show_next`. The heavy
    part runs immediately; show_next() (which builds the next screen) runs
    after the minimum time has passed. If work() returns None it is assumed
    to have already shown the next screen itself."""
    show_loading(page, text)

    def job():
        started = time.monotonic()
        try:
            show_next = work()                      # heavy part, runs now
            elapsed = time.monotonic() - started
            if elapsed < min_seconds:
                time.sleep(min_seconds - elapsed)   # wait only the missing part
            if callable(show_next):
                show_next()
        except Exception as ex:
            print("Transition error:", ex)

    threading.Thread(target=job, daemon=True).start()
