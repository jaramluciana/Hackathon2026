import flet as ft
import ui


def show(page, user_id, go_home):
    page.controls.clear()

    body = ft.Container(expand=True)   # <- build 3D Map content here later

    page.add(
        ui.gradient_screen(
            ft.Column(
                [ui.page_header("3D MAP", ft.Icons.VIEW_IN_AR_OUTLINED, go_home),
                 body],
                expand=True, spacing=0,
            )
        )
    )
    page.update()