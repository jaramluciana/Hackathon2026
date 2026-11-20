"""Resident Flet screen. Add as a tile in screens/home.py; see README."""
import flet as ft
import shelter_engine as shelter
from theme import BG_TOP, CARD_BG, ACCENT, TEXT, TEXT_DIM, ERROR, SUCCESS, FONT


def show(page, user_id, on_back):
    def heading(value):
        return ft.Text(value, size=20, color=ACCENT, weight=ft.FontWeight.BOLD, font_family=FONT)

    def line(value, color=TEXT):
        return ft.Text(str(value), size=14, color=color, font_family=FONT)

    def card(children):
        return ft.Container(bgcolor=CARD_BG, padding=18, border_radius=6,
                            content=ft.Column(children, spacing=10))

    content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=16)
    notice = line("")
    party = ft.TextField(label="People needing shelter (including you)", value="1", width=300,
                         keyboard_type=ft.KeyboardType.NUMBER, color=TEXT)

    def refresh():
        content.controls.clear()
        try:
            info = shelter.resident_status(user_id)
            source = info["source"]
            color = ERROR if source["status"] == "unsafe" else ACCENT if source["status"] != "normal" else SUCCESS
            content.controls.extend([
                card([heading("YOUR LEVEL"), line(f"Level {source['level']} — {source['status'].upper()}", color),
                      *[line(reason) for reason in source["reasons"]]]),
                card([heading("OFFICIAL GUIDANCE"), line(shelter.public_instructions(info))]),
            ])
            if info["assignment"]:
                a = info["assignment"]
                content.controls.append(card([heading("YOUR SHELTER ASSIGNMENT"),
                    line(f"Status: {a['status']}"), line(f"Destination: Level {a['destination']}"),
                    line(a["instructions"] if a["status"] in ("Approved", "Arrived") else "Await coordinator approval")]))
            else:
                if info["destinations"]:
                    content.controls.append(card([heading("POTENTIAL DESTINATIONS — NOT APPROVED"),
                        *[line(f"Level {d['level']}: {d['free']} available spaces (simulation)")
                          for d in info["destinations"][:5]]]))
                else:
                    content.controls.append(card([heading("POTENTIAL DESTINATIONS"),
                        line("No verified available shelter space currently configured.")]))
                if source["status"] == "unsafe":
                    content.controls.append(card([heading("REQUEST RELOCATION"), party,
                        ft.Button("SUBMIT REQUEST", on_click=submit)]))
            content.controls.append(ft.Button("REFRESH STATUS", on_click=lambda e: refresh()))
        except Exception as ex:
            content.controls.append(card([heading("SHELTER INFORMATION UNAVAILABLE"), line(str(ex), ERROR)]))
        page.update()

    def submit(e):
        try:
            result = shelter.request_relocation(user_id, int(party.value))
            notice.value = f"Request {result['id']}: {result['status']}. Await staff confirmation."
            notice.color = SUCCESS
        except Exception as ex:
            notice.value = str(ex)
            notice.color = ERROR
        refresh()

    page.controls.clear()
    page.add(ft.Container(expand=True, bgcolor=BG_TOP, padding=25,
                          content=ft.Column([
                              ft.Row([ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=ACCENT,
                                                    on_click=lambda e: on_back()),
                                      heading("HOLLOW-SHELTER")]),
                              notice, content], expand=True)))
    refresh()
