import flet as ft
import ui


def show(page, user_id, go_home):
    page.controls.clear()

    body = ft.Container(expand=True)   # <- build Medical content here later

    page.add(
        ui.gradient_screen(
            ft.Column(
                [ui.page_header("MEDICAL", ft.Icons.MEDICAL_SERVICES_OUTLINED, go_home),
                 body],
                expand=True, spacing=0,
            )
        )
    )
    page.update()