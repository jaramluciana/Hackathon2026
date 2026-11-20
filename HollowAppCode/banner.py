import threading
import flet as ft
from theme import *


class Banner:
    """Alert banner pinned to the top of the window, on every screen."""

    def __init__(self, page):
        self.page = page
        self._timer = None

        self.icon = ft.Icon(ft.Icons.WARNING_AMBER_OUTLINED, size=26)
        self.title = ft.Text("", size=12, font_family=FONT,
                             weight=ft.FontWeight.BOLD,
                             style=ft.TextStyle(letter_spacing=3))
        self.message = ft.Text("", size=13, color=TEXT, font_family=FONT)

        self.card = ft.Container(
            width=480,
            padding=16,
            bgcolor=CARD_BG,
            border=ft.Border.all(1, ACCENT),
            border_radius=4,
            shadow=ft.BoxShadow(blur_radius=40, color="#66000000"),
            content=ft.Row(
                [
                    self.icon,
                    ft.Column([self.title, self.message], spacing=4,
                              tight=True, expand=True),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=18,
                                  icon_color=TEXT_DIM,
                                  on_click=lambda e: self.hide()),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # Added to the page overlay so it floats above every screen
        self.wrapper = ft.Container(
            top=16, left=0, right=0,
            alignment=ft.Alignment(0, -1),
            content=self.card,
            visible=False,
        )
        page.overlay.append(self.wrapper)
        page.update()

    def show(self, level, text):
        color = LEVEL_COLORS.get(level, ACCENT)
        self.icon.color = color
        self.title.color = color
        self.title.value = f"{level.upper()} ALERT"
        self.message.value = text
        self.card.border = ft.Border.all(1, color)
        self.wrapper.visible = True
        self.page.update()

        if self._timer:
            self._timer.cancel()
        if level != "Red":          # Red stays until the user closes it
            self._timer = threading.Timer(6, self.hide)
            self._timer.daemon = True
            self._timer.start()

    def hide(self):
        self.wrapper.visible = False
        try:
            self.page.update()
        except Exception:
            pass