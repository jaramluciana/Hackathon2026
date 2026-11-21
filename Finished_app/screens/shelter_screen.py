"""Shelter screen (HOLLOW-SHELTER): resident view + staff panel for admin."""
import traceback
import flet as ft
import ui
import shelter_engine as shelter
from alert_engine import engine
from theme import *

LEVELS = [(str(i), f"Level {i}") for i in range(1, 11)]


def _friendly(exc):
    """ValueError = message written by us (safe to show). Anything else is
    logged in the terminal only, so server/driver details are not exposed."""
    if isinstance(exc, ValueError):
        return str(exc)
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    return "Something went wrong. Please try again."


def _live_readings():
    """Turn the in-memory alert-engine sensors into 0-100 scores.
    Oxygen exists for all 10 levels; the light battery only for the
    logged-in level, and is treated as that level's electricity."""
    live = {}
    for lv in range(1, 11):
        s = engine.sensors[lv]
        live[lv] = {"oxygen": 0.0 if s.depleted else s.remaining_ratio()}
    light = engine.sensors[0]
    live[engine.level]["electricity"] = (
        0.0 if light.depleted else light.remaining_ratio())
    return live


def show(page, user_id, go_home):
    is_admin = user_id.lower() == "admin"

    def heading(value):
        return ft.Text(value, size=12, color=ACCENT, font_family=FONT,
                       weight=ft.FontWeight.BOLD,
                       style=ft.TextStyle(letter_spacing=4))

    def line(value, color=TEXT):
        return ft.Text(str(value), size=13, color=color, font_family=FONT)

    def card(children):
        return ft.Container(
            width=580, padding=20, bgcolor=CARD_BG,
            border=ft.Border.all(1, ACCENT_DIM), border_radius=4,
            content=ft.Column(
                [children[0], ft.Container(height=1, bgcolor=ACCENT_DIM),
                 *children[1:]], spacing=10))

    def dropdown(label, options, width=240, value=None):
        return ft.Dropdown(
            label=label, width=width, value=value,
            options=[ft.DropdownOption(key=k, text=t) for k, t in options],
            color=TEXT, bgcolor="#0b0e14",
            border_color=ACCENT_DIM, focused_border_color=ACCENT,
            label_style=ft.TextStyle(color=TEXT_DIM, size=12, font_family=FONT),
            text_style=ft.TextStyle(font_family=FONT, size=15))

    notice = ft.Text("", size=13, font_family=FONT,
                     text_align=ft.TextAlign.CENTER)
    content = ft.Column(spacing=16,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    party = ui.make_field("PEOPLE NEEDING SHELTER (incl. you)",
                          ft.Icons.GROUP_OUTLINED)
    party.value = "1"
    party.keyboard_type = ft.KeyboardType.NUMBER

    def say(text, color):
        notice.value = text
        notice.color = color

    def act(fn, ok_text):
        """Run a staff action, show the result, then reload the screen."""
        try:
            fn()
            say(ok_text, SUCCESS)
        except ValueError as ex:
            say(str(ex), ERROR)
        except Exception as ex:
            say(_friendly(ex), ERROR)
        refresh()

    # ---------------------------------------------------------- staff panel
    def approve(req_id, dd, note):
        if not dd.value:
            say("Select a destination first", ERROR)
            ui.safe_update(page)
            return
        act(lambda: shelter.approve_request(
                req_id, int(dd.value), note.value or "", user_id,
                live=_live_readings()),
            "Request approved.")

    def set_cap(level_dd, value_tf):
        try:
            value = int((value_tf.value or "").strip())
        except ValueError:
            say("Capacity must be a whole number", ERROR)
            ui.safe_update(page)
            return
        act(lambda: shelter.set_capacity(int(level_dd.value), value, user_id),
            "Capacity updated.")

    def admin_cards():
        report = shelter.level_report(_live_readings())
        cards = []

        # ----- pending requests -----
        rows = []
        for r in shelter.pending_requests(user_id)[:5]:
            rows.append(line(f"#{r['id']}   {r['user']}   Level {r['source']}"
                             f"   {r['party_size']} people", ACCENT))
            options = [c for c in shelter.rank_destinations(
                           r["source"], report, r["party_size"])
                       if c["free"] >= r["party_size"]]
            buttons = []
            if options:
                dd = dropdown("DESTINATION",
                              [(str(c["level"]), f"Level {c['level']}  ({c['free']} free)")
                               for c in options], 300)
                note = ui.make_field("INSTRUCTIONS FOR THE RESIDENT",
                                     ft.Icons.EDIT_OUTLINED)
                note.width = 520
                rows += [dd, note]
                buttons.append(ui.make_button(
                    "APPROVE",
                    lambda e, i=r["id"], d=dd, n=note: approve(i, d, n)))
            else:
                rows.append(line("No safe destination with enough free space.", ERROR))
            buttons.append(ui.make_button(
                "REJECT",
                lambda e, i=r["id"]: act(
                    lambda: shelter.reject_request(i, user_id), "Request rejected.")))
            rows.append(ft.Row(buttons, wrap=True, spacing=12))
            rows.append(ft.Container(height=1, bgcolor=ACCENT_DIM))
        if not rows:
            rows = [line("No pending requests.", TEXT_DIM)]
        cards.append(card([heading("STAFF: PENDING REQUESTS"), *rows]))

        # ----- arrivals -----
        rows = []
        for a in shelter.approved_assignments(user_id)[:8]:
            rows.append(line(f"#{a['id']}   {a['user']}   Level {a['source']} -> "
                             f"Level {a['destination']}   {a['party_size']} people"))
            rows.append(ui.make_button(
                "CONFIRM ARRIVAL",
                lambda e, i=a["id"]: act(
                    lambda: shelter.arrival_confirmed(i, user_id), "Arrival confirmed.")))
        if not rows:
            rows = [line("Nobody is waiting to arrive.", TEXT_DIM)]
        cards.append(card([heading("STAFF: ARRIVALS"), *rows]))

        # ----- capacity -----
        rows = [line(f"Level {r['level']}:  capacity {r['capacity']}  |  "
                     f"occupied {r['occupied']}  |  reserved {r['reserved']}  |  "
                     f"{r['status'].upper()}",
                     ERROR if r["status"] == "unsafe" else TEXT)
                for r in report]
        cap_level = dropdown("LEVEL", LEVELS, 160, "1")
        cap_value = ui.make_field("NEW CAPACITY", ft.Icons.GROUP_OUTLINED)
        cap_value.width = 200
        cap_value.keyboard_type = ft.KeyboardType.NUMBER
        rows += [ft.Container(height=6),
                 ft.Row([cap_level, cap_value], spacing=12, wrap=True),
                 ui.make_button("SET CAPACITY",
                                lambda e: set_cap(cap_level, cap_value))]
        cards.append(card([heading("STAFF: SHELTER CAPACITY"), *rows]))
        return cards

    # ------------------------------------------------------------- refresh
    def refresh(first=False):
        content.controls.clear()

        if is_admin:
            try:
                content.controls.extend(admin_cards())
            except Exception as ex:
                content.controls.append(card([
                    heading("STAFF TOOLS UNAVAILABLE"), line(_friendly(ex), ERROR)]))

        try:
            info = shelter.resident_status(user_id, _live_readings())
            source = info["source"]
            color = (ERROR if source["status"] == "unsafe"
                     else ACCENT if source["status"] != "normal" else SUCCESS)
            content.controls.extend([
                card([heading("YOUR LEVEL"),
                      line(f"Level {source['level']} - {source['status'].upper()}", color),
                      *[line(r) for r in source["reasons"]]]),
                card([heading("OFFICIAL GUIDANCE"),
                      line(shelter.public_instructions(info))]),
            ])
            if info["assignment"]:
                a = info["assignment"]
                content.controls.append(card([
                    heading("YOUR SHELTER ASSIGNMENT"),
                    line(f"Status: {a['status']}"),
                    line(f"Destination: Level {a['destination']}"),
                    line(a["instructions"] if a["status"] in ("Approved", "Arrived")
                         else "Await coordinator approval")]))
            else:
                if info["destinations"]:
                    content.controls.append(card([
                        heading("POTENTIAL DESTINATIONS - NOT APPROVED"),
                        *[line(f"Level {d['level']}: {d['free']} available spaces (simulation)")
                          for d in info["destinations"][:5]]]))
                else:
                    content.controls.append(card([
                        heading("POTENTIAL DESTINATIONS"),
                        line("No verified available shelter space currently configured.",
                             TEXT_DIM)]))
                if source["status"] == "unsafe":
                    content.controls.append(card([
                        heading("REQUEST RELOCATION"), party,
                        ui.make_button("SUBMIT REQUEST", submit)]))
            content.controls.append(ui.make_button("REFRESH STATUS", lambda e: refresh()))
        except Exception as ex:
            content.controls.append(card([
                heading("SHELTER INFORMATION UNAVAILABLE"),
                line(_friendly(ex), ERROR)]))
        if not first:                     # first call happens before the screen exists
            ui.safe_update(page)

    def submit(e):
        try:
            result = shelter.request_relocation(user_id, int(party.value),
                                                live=_live_readings())
            say(f"Request {result['id']}: {result['status']}. Await staff confirmation.",
                SUCCESS)
        except ValueError as ex:          # includes "invalid literal" from int()
            say("Please enter a whole number" if "invalid literal" in str(ex)
                else str(ex), ERROR)
        except Exception as ex:
            say(_friendly(ex), ERROR)
        refresh()

    refresh(first=True)
    body = ft.Column([ft.Container(height=10), notice, content,
                      ft.Container(height=20)],
                     scroll=ft.ScrollMode.AUTO, expand=True, spacing=16,
                     horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    ui.set_screen(page, ui.gradient_screen(
        ft.Column([ui.page_header("SHELTER", ft.Icons.HOME_WORK_OUTLINED, go_home),
                   body], expand=True, spacing=0)))