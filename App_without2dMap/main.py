import flet as ft
import ui
import database
from theme import BG_TOP
from screens import login, home
from alert_engine import engine
from banner import Banner
from hollow_sim import sim


def main(page: ft.Page):
    page.title = "Hollow City"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_TOP
    page.window.width = 1300
    page.window.height = 780

    banner = Banner(page)

    def on_alert(kind, data=None):
        if kind == "alert" and data["popup"]:
            banner.show(data["level"], data["text"])

    engine.subscribe(on_alert)      # engine starts after login (go_home)

    def back_to_login():
        login.show_login(page, on_success=go_home)

    def go_login(text="LEAVING"):
        def work():
            banner.hide()                                # tắt banner (kể cả Red)
            engine.shutdown()                            # forget the old user
            sim.stop()                                   # heavy part                                 # heavy part
            return lambda: login.show_login(page, on_success=go_home)
        ui.run_with_loading(page, work, text, on_error=back_to_login)

    def go_home(user_id, level):
        def work():
            engine.set_level(level)                      # heavy part
            engine.start()                               # no-op if already running
            if user_id.lower() == "admin":
                sim.start()
            name = database.get_full_name(user_id)
            return lambda: home.show(page, user_id, level, name, go_login)
        ui.run_with_loading(page, work, "ENTERING THE HOLLOW",
                            on_error=back_to_login)

    go_login("OPENING APP")      # first screen when the app starts


ft.run(main)
