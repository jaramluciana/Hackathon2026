"""Explore screen (HOLLOW-EXPLORE): resident missions + staff review for admin."""
import flet as ft
import ui
import explore_sql as ex
from theme import *
from screens.medical import _card, _txt, _dropdown, _textbox, _friendly

RESOURCE_OPTS = [(r, r.capitalize()) for r in ex.RESOURCES]


def show(page, user_id, go_home):
    is_admin = user_id.lower() == "admin"
    status = _txt("", TEXT, 13, text_align=ft.TextAlign.CENTER)
    content = ft.Column(spacing=16,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def act(fn):
        """Run an action, show its message, then reload the screen."""
        try:
            status.value, status.color = fn(), SUCCESS
        except Exception as exc:
            status.value, status.color = _friendly(exc), ERROR
        refresh()

    # ------------------------------------------------------------ cards
    def mission_cards():
        rows = []
        for m in ex.list_missions(user_id):
            rows.append(_txt(f"{m['title']}  [{m['sector']} {m['sector_name']}]",
                             ACCENT, 13, weight=ft.FontWeight.BOLD))
            rows.append(_txt(f"{m['kind']} | {m['hours']:g}h | hazard {m['hazard']} "
                             f"(max {m['max_hazard']}) | reward {m['reward']}",
                             TEXT_DIM, 12))
            rows.append(_txt(m["objective"], TEXT, 12))
            if m["reasons"]:
                rows += [_txt("- " + r, ERROR, 11) for r in m["reasons"]]
            elif not is_admin:
                rows.append(ui.make_button(
                    "APPLY", lambda e, i=m["id"]: act(lambda: ex.apply(user_id, i))))
            rows.append(ft.Container(height=1, bgcolor=ACCENT_DIM))
        return [_card("SURFACE MISSIONS", rows or [_txt("No missions", TEXT_DIM, 12)])]

    def my_cards():
        rows = []
        try:
            apps = ex.my_applications(user_id)
        except ValueError as exc:            # e.g. no resident linked to the account
            return [_card("MY EXPEDITIONS", [_txt(str(exc), TEXT_DIM, 12)])]
        for a in apps:
            rows.append(_txt(f"#{a['id']}  {a['title']}  -  {a['status']}", TEXT, 12))
            if a["status"] == "approved":
                rows.append(ui.make_button(
                    "START MISSION",
                    lambda e, i=a["id"]: act(lambda: ex.start(user_id, i))))
            elif a["status"] == "active":
                if a["report_state"] == 0:
                    rows.append(_txt("Report submitted - awaiting staff verification.",
                                     TEXT_DIM, 12))
                    continue
                if a["report_state"] == -1:
                    rows.append(_txt("Your last report was rejected. "
                                     "Submit a corrected report.", ERROR, 12))
                res_dd = _dropdown("RESOURCE FOUND", RESOURCE_OPTS, 250, "none")
                text = _textbox("Findings (10-2000 characters)", 520, multiline=True)
                rows += [res_dd, text, ui.make_button(
                    "SUBMIT REPORT",
                    lambda e, i=a["id"], d=res_dd, t=text: act(
                        lambda: ex.submit_report(user_id, i, t.value, d.value)))]
        return [_card("MY EXPEDITIONS", rows or [_txt("No applications yet", TEXT_DIM, 12)])]

    def admin_cards():
        rows = []
        for a in ex.pending_applications(user_id):
            rows.append(_txt(f"#{a['id']}  resident {a['resident_id']} ({a['work']}, "
                             f"health {a['health']})  -  {a['title']}", TEXT, 12))
            rows.append(ft.Row([
                ui.make_button("APPROVE", lambda e, i=a["id"]: act(
                    lambda: ex.decide(user_id, i, "approved"))),
                ui.make_button("REJECT", lambda e, i=a["id"]: act(
                    lambda: ex.decide(user_id, i, "rejected")))], wrap=True, spacing=12))
        cards = [_card("STAFF: PENDING APPLICATIONS",
                       rows or [_txt("None", TEXT_DIM, 12)])]

        rows = []
        for r in ex.pending_reports(user_id):
            rows.append(_txt(f"#{r['id']}  resident {r['resident_id']}  -  {r['title']}"
                             f"  [{r['resource']}]", ACCENT, 12))
            rows.append(_txt(r["findings"], TEXT, 12))
            rows.append(ft.Row([
                ui.make_button("APPROVE & PAY", lambda e, i=r["id"]: act(
                    lambda: ex.verify_report(user_id, i, True))),
                ui.make_button("REJECT", lambda e, i=r["id"]: act(
                    lambda: ex.verify_report(user_id, i, False)))], wrap=True, spacing=12))
        cards.append(_card("STAFF: REPORTS TO VERIFY",
                           rows or [_txt("None", TEXT_DIM, 12)]))
        return cards

    # ------------------------------------------------------------ refresh
    def refresh(first=False):
        content.controls.clear()
        try:
            content.controls.extend(mission_cards())
            if not is_admin:
                content.controls.extend(my_cards())
            if is_admin:
                content.controls.extend(admin_cards())
        except Exception as exc:
            hint = ("Run sql/04_explore.sql in SSMS first."
                    if "Explore_" in str(exc) or "Invalid object" in str(exc) else "")
            content.controls.append(_card("EXPLORE UNAVAILABLE", [
                _txt(_friendly(exc), ERROR, 12), _txt(hint, TEXT_DIM, 12)]))
        if not first:
            ui.safe_update(page)

    refresh(first=True)
    body = ft.Column([ft.Container(height=10), status, content,
                      ft.Container(height=20)],
                     scroll=ft.ScrollMode.AUTO, expand=True, spacing=16,
                     horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    ui.set_screen(page, ui.gradient_screen(
        ft.Column([ui.page_header("EXPLORE", ft.Icons.EXPLORE_OUTLINED, go_home),
                   body], expand=True, spacing=0)))