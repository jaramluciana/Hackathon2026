import flet as ft
import ui
import database
from datetime import datetime, date
from theme import *


def show_login(page, on_success, notice="", prefill=""):
    """on_success(user_id, level) is called after a correct login."""

    user = ui.make_field("USER ID (e.g. A0000001)", ft.Icons.PERSON_OUTLINE,
                         on_submit=lambda e: handle_login(e))
    pw = ui.make_field("PASSWORD", ft.Icons.LOCK_OUTLINE, is_password=True,
                       on_submit=lambda e: handle_login(e))
    user.value = prefill
    msg = ft.Text(notice, color=SUCCESS if notice else ERROR, size=13,
                  font_family=FONT, text_align=ft.TextAlign.CENTER)

    def handle_login(e):
        if not user.value or not pw.value:
            msg.color = ERROR
            msg.value = "Please enter both ID and password"
            page.update()
            return

        uid = user.value.strip()
        status, level = database.check_login(uid, pw.value)


        if status == "error":
            msg.color = ERROR
            msg.value = "Cannot connect to the database"
        elif status == "ok":
            on_success(uid, level)
            return
        else:
            msg.color = ERROR
            msg.value = "WRONG PASSWORD OR INVALID ID"
        page.update()

    page.controls.clear()
    page.add(
        ui.wrap_screen(
            ft.Column(
                ui.title_block("HOLLOW CITY", "RESIDENT ACCESS") + [
                    user, pw, msg,
                    ft.Container(height=4),
                    ui.make_button("ENTER", handle_login),
                    ui.make_link("No account? Create one",
                                 lambda e: show_register(page, on_success)),
                ],
                tight=True, spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
    )
    page.update()


def show_register(page, on_success):
    first_name = ui.make_field("FIRST NAME", ft.Icons.BADGE_OUTLINED)
    last_name = ui.make_field("LAST NAME", ft.Icons.BADGE_OUTLINED)
    dob = ui.make_field("DATE OF BIRTH (DD/MM/YYYY)", ft.Icons.CAKE_OUTLINED)

    def make_dropdown(label, options):
        return ft.Dropdown(
            label=label, width=320, options=options,
            color=TEXT, bgcolor="#0b0e14",
            border_color=ACCENT_DIM, focused_border_color=ACCENT,
            label_style=ft.TextStyle(color=TEXT_DIM, size=12, font_family=FONT),
            text_style=ft.TextStyle(font_family=FONT, size=15),
        )

    level = make_dropdown(
        "FLOOR LEVEL (decides your ID letter)",
        [ft.DropdownOption(key=str(i),
                           text=f"Level {i}  ({chr(ord('A') + i - 1)})")
         for i in range(1, 11)])

    work = make_dropdown(
        "OCCUPATION",
        [ft.DropdownOption(key=w, text=w.capitalize())
         for w in ("engineer", "farmer", "medic", "miner",
                   "technician", "teacher", "guard", "scavenger")])

    important = ft.Switch(
        label="Mark as IMPORTANT (otherwise decided by occupation)",
        value=False, active_color=ACCENT,
        label_text_style=ft.TextStyle(color=TEXT_DIM, size=12,
                                      font_family=FONT),
    )

    pw = ui.make_field("PASSWORD", ft.Icons.LOCK_OUTLINE, is_password=True)
    confirm = ui.make_field("CONFIRM PASSWORD", ft.Icons.LOCK_OUTLINE,
                            is_password=True,
                            on_submit=lambda e: handle_register(e))
    msg = ft.Text("", color=ERROR, size=13, font_family=FONT,
                  text_align=ft.TextAlign.CENTER)

    def handle_register(e):
        fn = (first_name.value or "").strip()
        ln = (last_name.value or "").strip()

        birth = None
        try:
            birth = datetime.strptime((dob.value or "").strip(),
                                      "%d/%m/%Y").date()
        except ValueError:
            pass

        if not fn or not ln or not dob.value or not level.value \
                or not work.value or not pw.value or not confirm.value:
            msg.value = "Please fill in all fields"
        elif birth is None:
            msg.value = "Date of birth must look like 25/12/2005"
        elif birth > date.today() or birth.year < 1900:
            msg.value = "Date of birth is not valid"
        elif len(pw.value) < 6:
            msg.value = "Password must be at least 6 characters"
        elif pw.value != confirm.value:
            msg.value = "Passwords do not match"
        else:
            status, new_id = database.create_account(
                fn, ln, birth, pw.value, int(level.value), work.value,
                True if important.value else None)
            if status == "ok":
                show_login(page, on_success,
                           notice=f"Account created. Your ID is {new_id}",
                           prefill=new_id)
                return
            msg.value = "Cannot create account (database error)"
        page.update()

    page.controls.clear()
    page.add(
        ui.wrap_screen(
            ft.Column(
                ui.title_block("NEW RESIDENT", "CREATE ACCOUNT") + [
                    ft.Text("Your ID will be assigned from your level.",
                            size=12, color=TEXT_DIM, font_family=FONT,
                            text_align=ft.TextAlign.CENTER),
                    first_name, last_name, dob, level, work, important,
                    pw, confirm, msg,
                    ft.Container(height=4),
                    ui.make_button("REGISTER", handle_register),
                    ui.make_link("Already have an account? Back to login",
                                 lambda e: show_login(page, on_success)),
                ],
                tight=True, spacing=10, scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
    )
    page.update()