import flet as ft
from datetime import datetime, date
import ui
import database
from theme import *


def show(page, user_id, go_home, on_updated=None):
    """on_updated(new_full_name) is called after a successful update so the
    Home screen can show the new name."""
    page.controls.clear()

    session = {"pw": None}    # verified password, kept only while on this page

    content = ft.Column(
        tight=True, spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def info_row(label, value):
        return ft.Container(
            width=320,
            padding=ft.Padding.symmetric(vertical=6),
            border=ft.Border.only(bottom=ft.BorderSide(1, ACCENT_DIM)),
            content=ft.Row(
                [
                    ft.Text(label, size=11, color=TEXT_DIM, font_family=FONT,
                            style=ft.TextStyle(letter_spacing=3)),
                    ft.Text(str(value), size=15, color=TEXT, font_family=FONT,
                            weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

    # ---------- LOCKED ----------
    def show_locked():
        session["pw"] = None
        pw = ui.make_field("ENTER PASSWORD TO VIEW", ft.Icons.LOCK_OUTLINE,
                           is_password=True, on_submit=lambda e: verify(e))
        msg = ft.Text("", color=ERROR, size=13, font_family=FONT,
                      text_align=ft.TextAlign.CENTER)

        def verify(e):
            if not pw.value:
                msg.value = "Please enter your password"
                page.update()
                return
            status, data = database.get_profile(user_id, pw.value)
            if status == "ok":
                session["pw"] = pw.value
                show_details(data)
            elif status == "wrong":
                msg.value = "WRONG PASSWORD"
            else:
                msg.value = "Cannot connect to the database"
            page.update()

        content.controls = [
            ft.Icon(ft.Icons.LOCK_OUTLINE, size=40, color=ACCENT),
            ft.Text("CONFIDENTIAL", size=12, color=TEXT_DIM, font_family=FONT,
                    style=ft.TextStyle(letter_spacing=5)),
            pw,
            msg,
            ui.make_button("SHOW", verify),
        ]

    # ---------- DETAILS ----------
    def show_details(d, notice=""):
        content.controls = [
            ft.Text("RESIDENT INFORMATION", size=12, color=TEXT_DIM,
                    font_family=FONT, style=ft.TextStyle(letter_spacing=5)),
            ui.divider(),
            info_row("ID", d["id"]),
            info_row("FIRST NAME", d["first_name"]),
            info_row("LAST NAME", d["last_name"]),
            info_row("DATE OF BIRTH", d["dob"]),
            info_row("LEVEL", d["level"]),
            info_row("OCCUPATION", d["work"]),
            info_row("SALARY", d["salary"]),
            info_row("MONEY", d["money"]),
            info_row("STATUS", d["status"]),
            info_row("IMPORTANT", d["important"]),
            ft.Text(notice, color=SUCCESS, size=13, font_family=FONT,
                    text_align=ft.TextAlign.CENTER),
            ui.make_button("UPDATE INFO", lambda e: show_edit(d)),
            ui.make_button("HIDE", lambda e: (show_locked(), page.update())),
        ]

    # ---------- EDIT ----------
    # ---------- EDIT ----------
    def show_edit(d):
        first = ui.make_field("FIRST NAME", ft.Icons.BADGE_OUTLINED)
        last = ui.make_field("LAST NAME", ft.Icons.BADGE_OUTLINED)
        dob = ui.make_field("DATE OF BIRTH (DD/MM/YYYY)", ft.Icons.CAKE_OUTLINED)
        pw = ui.make_field("CURRENT PASSWORD (required to save)",
                           ft.Icons.LOCK_OUTLINE, is_password=True,
                           on_submit=lambda e: save(e))

        # prefill (the "—" placeholder means the value was empty)
        first.value = "" if d["first_name"] == "—" else d["first_name"]
        last.value = "" if d["last_name"] == "—" else d["last_name"]
        dob.value = "" if d["dob"] == "—" else d["dob"]

        msg = ft.Text("", color=ERROR, size=13, font_family=FONT,
                      text_align=ft.TextAlign.CENTER)

        def save(e):
            fn = (first.value or "").strip()
            ln = (last.value or "").strip()

            birth = None
            try:
                birth = datetime.strptime((dob.value or "").strip(),
                                          "%d/%m/%Y").date()
            except ValueError:
                pass

            if not fn or not ln or not dob.value:
                msg.value = "First name, last name and date of birth are required"
            elif birth is None:
                msg.value = "Date of birth must look like 25/12/2005"
            elif birth > date.today() or birth.year < 1900:
                msg.value = "Date of birth is not valid"
            elif not pw.value:
                msg.value = "Please enter your password to save"
            else:
                result = database.update_profile(
                    user_id, pw.value, fn, ln, birth)
                if result == "ok":
                    session["pw"] = pw.value
                    if on_updated:
                        on_updated(f"{ln} {fn}")
                    status, fresh = database.get_profile(user_id, pw.value)
                    if status == "ok":
                        show_details(fresh, "Information updated.")
                    else:
                        show_locked()
                    page.update()
                    return
                elif result == "wrong":
                    msg.value = "WRONG PASSWORD"
                else:
                    msg.value = "Cannot connect to the database"
            page.update()

        content.controls = [
            ft.Text("UPDATE INFORMATION", size=12, color=TEXT_DIM,
                    font_family=FONT, style=ft.TextStyle(letter_spacing=5)),
            ui.divider(),
            info_row("ID", d["id"]),
            info_row("LEVEL", d["level"]),
            first, last, dob, pw,
            msg,
            ui.make_button("SAVE", save),
            ui.make_button("CANCEL", lambda e: (show_details(d), page.update())),
        ]
        page.update()

    show_locked()

    body = ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                ft.Container(
                    width=420, padding=40, bgcolor=CARD_BG,
                    border=ft.Border.all(1, ACCENT_DIM), border_radius=4,
                    content=content,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )

    page.add(
        ui.gradient_screen(
            ft.Column(
                [ui.page_header("MY INFO", ft.Icons.BADGE_OUTLINED, go_home),
                 body],
                expand=True, spacing=0,
            )
        )
    )
    page.update()