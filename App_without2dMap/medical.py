import traceback
import flet as ft
import ui
import hollow_med_sql as med
from theme import *


def _friendly(exc):
    """ValueError = message written by us (safe to show). Anything else is
    logged in the terminal only, so server/driver details are not exposed."""
    if isinstance(exc, ValueError):
        return str(exc)
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    return "Something went wrong. Please try again."

HORIZONS = [("300", "5 sim-minutes"), ("1800", "30 sim-minutes"),
            ("3600", "1 sim-hour"), ("21600", "6 sim-hours")]
KINDS = [("medical", "Medical"), ("emergency", "Emergency"),
         ("supplies", "Supplies")]
ITEMS = [("medical_kits", "Medical kits"), ("oxygen_tanks", "Oxygen tanks"),
         ("water_packs", "Water packs")]
LEVELS = [(str(i), f"Level {i}") for i in range(1, 11)]


# ---------- small style helpers ----------
def _color(v):
    if v >= 90:
        return LEVEL_COLORS["Normal"]
    if v >= 60:
        return LEVEL_COLORS["Yellow"]
    if v >= 25:
        return LEVEL_COLORS["Orange"]
    return LEVEL_COLORS["Red"]


def _txt(text, color=TEXT, size=13, **kw):
    return ft.Text(text, color=color, size=size, font_family=FONT, **kw)


def _card(title, controls):
    return ft.Container(
        width=580, padding=20, bgcolor=CARD_BG,
        border=ft.Border.all(1, ACCENT_DIM), border_radius=4,
        content=ft.Column(
            [_txt(title, ACCENT, 12, weight=ft.FontWeight.BOLD,
                  style=ft.TextStyle(letter_spacing=4)),
             ft.Container(height=1, bgcolor=ACCENT_DIM),
             *controls],
            spacing=10),
    )


def _dropdown(label, options, width=320, value=None):
    return ft.Dropdown(
        label=label, width=width, value=value,
        options=[ft.DropdownOption(key=k, text=t) for k, t in options],
        color=TEXT, bgcolor="#0b0e14",
        border_color=ACCENT_DIM, focused_border_color=ACCENT,
        label_style=ft.TextStyle(color=TEXT_DIM, size=12, font_family=FONT),
        text_style=ft.TextStyle(font_family=FONT, size=15),
    )


def _textbox(label, width=320, multiline=False):
    return ft.TextField(
        label=label, width=width, color=TEXT, cursor_color=ACCENT,
        bgcolor="#0b0e14", border_color=ACCENT_DIM,
        focused_border_color=ACCENT, border_radius=2,
        multiline=multiline, min_lines=2 if multiline else 1,
        max_lines=4 if multiline else 1,
        label_style=ft.TextStyle(color=TEXT_DIM, size=12, font_family=FONT),
        text_style=ft.TextStyle(font_family=FONT, size=15),
    )


def _bar_row(label, value):
    v = max(0.0, min(100.0, float(value)))
    return ft.Row(
        [_txt(label, TEXT, 12, width=120),
         ft.ProgressBar(value=v / 100, width=250, bar_height=8,
                        bgcolor="#1c2230", color=_color(v)),
         _txt(f"{v:.0f}%", TEXT_DIM, 12, width=48)],
        spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def _sub(text):
    return _txt(text, TEXT_DIM, 11, weight=ft.FontWeight.BOLD,
                style=ft.TextStyle(letter_spacing=3))


# ---------- screen ----------
def show(page, user_id, go_home):
    is_admin = user_id.lower() == "admin"

    def load():
        data = med.resident_dashboard(user_id)   # one connection for everything
        return data, data["all_clinics"]

    def open_screen():
        def work():                      # runs in the loading thread
            try:
                payload = load()
                return lambda: render(payload, None)
            except Exception as exc:
                error_text = str(exc)    # copy it: `exc` is deleted after this block
                return lambda: render(None, (error_text, ERROR))
        ui.run_with_loading(page, work, "OPENING MEDICAL", min_seconds=0)

    def refresh(notice=None):            # reload data after an action
        try:
            render(load(), notice)
        except Exception as exc:
            render(None, (str(exc), ERROR))

    def render(payload, notice):

        # ----- error screen (e.g. 03_medical.sql not run yet) -----
        if payload is None:
            msg = notice[0] if notice else "Unknown error"
            hint = ("Run sql/03_medical.sql in SSMS first."
                    if "Med_" in msg or "Invalid object" in msg else "")
            cards = [_card("HEALTHCARE UNAVAILABLE",
                           [_txt(msg, ERROR, 12), _txt(hint, TEXT_DIM, 12)])]
            body = ft.Column([ft.Container(height=20), *cards],
                             horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                             expand=True)
            finish(body)
            return

        data, clinic_list = payload
        res = data["resident"]
        own_level = res["level"]

        status = _txt(notice[0] if notice else "",
                      notice[1] if notice else SUCCESS, 13,
                      text_align=ft.TextAlign.CENTER)

        def fail(msg):
            text = _friendly(msg) if isinstance(msg, Exception) else str(msg)
            status.value = text
            status.color = ERROR
            try:
                # visible even when the user is scrolled down to a lower card
                page.show_dialog(ft.SnackBar(ft.Text(text), bgcolor=ERROR))
            except Exception:
                page.update()

        clinic_names = {c["id"]: f"L{c['level']} {c['name']}"
                        for c in clinic_list}
        ordered = sorted(clinic_list,
                         key=lambda c: (c["level"] != own_level, c["level"]))
        clinic_opts = [
            (str(c["id"]),
             f"L{c['level']}  {c['name']}  "
             f"({c['available']} slots)" if c["available"]
             else f"L{c['level']}  {c['name']}  (full)")
            for c in ordered]

        # ===== YOUR HEALTH =====
        health = res["health"]
        if health is None:
            health_rows = [_txt("No resident record linked to this account.",
                                TEXT_DIM, 12)]
        else:
            health_rows = [
                _bar_row("Health", health),
                _txt(f"Status: {str(res['status']).upper()}", TEXT_DIM, 12)]
        card_health = _card("YOUR HEALTH", health_rows)


        # ===== APPOINTMENTS =====
        clinic_dd = _dropdown("CLINIC", clinic_opts, 520)

        def do_book(e):
            if not clinic_dd.value:
                fail("Select a clinic first")
                return
            try:
                refresh((med.book_appointment(user_id, int(clinic_dd.value)),
                         SUCCESS))
            except Exception as exc:
                fail(exc)

        def do_cancel(appt_id):
            try:
                ok = med.cancel_appointment(user_id, appt_id)
                refresh(("Appointment cancelled." if ok
                         else "Could not cancel this appointment.",
                         SUCCESS if ok else ERROR))
            except Exception as exc:
                fail(exc)

        appt_rows = []
        for a in data["appointments"][:8]:
            row = [_txt(
                f"#{a['id']}  "
                f"{clinic_names.get(a['clinic_id'], 'Clinic ' + str(a['clinic_id']))}"
                f"  —  {a['status']}", TEXT, 12, expand=True)]
            if a["status"] == "requested":
                row.append(ui.make_link(
                    "CANCEL", lambda e, i=a["id"]: do_cancel(i)))
            appt_rows.append(ft.Row(
                row, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        if not appt_rows:
            appt_rows = [_txt("No appointments yet", TEXT_DIM, 12)]

        card_appt = _card("REQUEST AN APPOINTMENT", [
            clinic_dd, ui.make_button("REQUEST APPOINTMENT", do_book),
            *appt_rows])

        # ===== MEDICAL ASSISTANCE =====
        kind_dd = _dropdown("REQUEST TYPE", KINDS, 250, "medical")
        message = _textbox("Describe what you need", 520, multiline=True)

        def do_request(e):
            try:
                refresh((med.submit_request(user_id, kind_dd.value,
                                            message.value or ""), SUCCESS))
            except Exception as exc:
                fail(exc)

        req_rows = [_txt(f"#{r['id']}  {r['kind']}  —  {r['status']}: "
                         f"{r['message']}", TEXT, 12)
                    for r in data["requests"][:8]]
        if not req_rows:
            req_rows = [_txt("No requests yet", TEXT_DIM, 12)]

        card_request = _card("MEDICAL ASSISTANCE", [
            kind_dd, message, ui.make_button("SUBMIT REQUEST", do_request),
            *req_rows])

        # ===== FORECAST =====
        hz_dd = _dropdown("HORIZON", HORIZONS, 200, "300")
        fc_level_dd = _dropdown("LEVEL", LEVELS, 140, str(own_level))
        fc_out = ft.Column(spacing=4)

        def do_forecast(e):
            try:
                lv = int(fc_level_dd.value) if is_admin else own_level
                fc = med.forecast(lv, int(hz_dd.value))
                fc_out.controls = [
                    _txt(f"Level {fc['level']}, next "
                         f"{fc['horizon_seconds'] // 60} sim-minutes",
                         TEXT_DIM, 12),
                    _txt("Estimated health loss per resident: "
                         f"{fc['estimated_health_loss']}"),
                    _txt(f"Already urgent (score 1-20): "
                         f"{fc['currently_urgent']:,}"),
                    _txt(f"Newly urgent: {fc['newly_urgent']:,}",
                         LEVEL_COLORS["Orange"]),
                    _txt(f"Projected score zero: "
                         f"{fc['projected_zero_health']:,}",
                         LEVEL_COLORS["Red"]),
                    _txt(fc["disclaimer"], TEXT_DIM, 11),
                ]
                page.update()
            except Exception as exc:
                fail(exc)

        fc_controls = [ft.Row([hz_dd] + ([fc_level_dd] if is_admin else []),
                              spacing=12)]
        card_forecast = _card("FORECAST", [
            *fc_controls, ui.make_button("RUN FORECAST", do_forecast), fc_out])

        # ===== ANNOUNCEMENTS =====
        notice_rows = [_txt(n["message"], TEXT, 12)
                       for n in data["notifications"][:8]]
        if not notice_rows:
            notice_rows = [_txt("No current announcements", TEXT_DIM, 12)]
        card_notices = _card("ANNOUNCEMENTS", notice_rows)

        cards = [card_health, card_appt, card_request,
                 card_forecast, card_notices]

        # ===== ADMIN TOOLS =====
        if is_admin:
            nt_level = _dropdown("PUBLISH TO", [("all", "All levels")] + LEVELS,
                                 200, "all")
            nt_msg = _textbox("Announcement", 520, multiline=True)

            def do_publish(e):
                try:
                    lv = None if nt_level.value == "all" else int(nt_level.value)
                    med.publish_notice(lv, nt_msg.value or "")
                    refresh(("Announcement published.", SUCCESS))
                except Exception as exc:
                    fail(exc)

            sp_level = _dropdown("TARGET LEVEL", LEVELS, 160, str(own_level))
            sp_item = _dropdown("ITEM", ITEMS, 200, "medical_kits")
            sp_qty = _textbox("Quantity", 120)
            sp_qty.value = "10"
            sp_out = ft.Column(spacing=4)

            def do_suggest(e):
                try:
                    qty = int((sp_qty.value or "").strip())
                except ValueError:
                    fail("Quantity must be a whole number")
                    return
                try:
                    r = med.suggest_support(int(sp_level.value),
                                            sp_item.value, qty)
                    lines = [_txt(f"Requested {r['requested']}, allocated "
                                  f"{r['allocated']}, unmet {r['unmet']}")]
                    lines += [_txt(f"{p['name']} (L{p['level']}): "
                                   f"{p['quantity']}", TEXT_DIM, 12)
                              for p in r["proposals"]]
                    lines.append(_txt(r["note"], TEXT_DIM, 11))
                    sp_out.controls = lines
                    page.update()
                except Exception as exc:
                    fail(exc)

            inv_dd = _dropdown("CLINIC", clinic_opts, 520)
            inv_out = ft.Column(spacing=4)

            def do_inventory(e):
                if not inv_dd.value:
                    fail("Select a clinic first")
                    return
                try:
                    items = med.clinic_inventory(int(inv_dd.value))
                    inv_out.controls = [
                        _txt(f"{i['item']}: {i['quantity']} "
                             f"(reserve {i['reserve']})", TEXT, 12)
                        for i in items] or [_txt("No inventory", TEXT_DIM, 12)]
                    page.update()
                except Exception as exc:
                    fail(exc)

            cards.append(_card("ADMIN TOOLS", [
                _sub("PUBLISH ANNOUNCEMENT"), nt_level, nt_msg,
                ui.make_button("PUBLISH", do_publish),
                ft.Container(height=6),
                _sub("SUGGEST SUPPORT (READ-ONLY)"),
                ft.Row([sp_level, sp_item, sp_qty], spacing=12, wrap=True),
                ui.make_button("SUGGEST", do_suggest), sp_out,
                ft.Container(height=6),
                _sub("CLINIC INVENTORY"), inv_dd,
                ui.make_button("VIEW INVENTORY", do_inventory), inv_out,
            ]))

        body = ft.Column(
            [ft.Container(height=10), status, *cards, ft.Container(height=20)],
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16, expand=True)
        finish(body)

    def finish(body):
        ui.set_screen(page, ui.gradient_screen(
            ft.Column(
                [ui.page_header("MEDICAL",
                                ft.Icons.MEDICAL_SERVICES_OUTLINED,
                                go_home),
                 body],
                expand=True, spacing=0)))

    open_screen()