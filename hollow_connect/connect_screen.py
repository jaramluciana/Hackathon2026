"""HOLLOW-CONNECT Flet screen; call show(page, user_id, level, on_back)."""
import flet as ft
import connect_engine as connect
from theme import BG_TOP, CARD_BG, ACCENT, ACCENT_DIM, TEXT, TEXT_DIM, ERROR, SUCCESS


def show(page, user_id, level, on_back):
    is_admin = str(user_id).lower() == 'admin'
    message = ft.Text('', color=SUCCESS, size=13)
    kind = ft.Dropdown(label='Emergency category', width=290,
                       options=[ft.dropdown.Option(x) for x in connect.TYPES], value='Medical')
    urgency = ft.Dropdown(label='Urgency', width=290,
                          options=[ft.dropdown.Option(x) for x in connect.URGENCIES], value='Urgent')
    location = ft.Dropdown(label='Affected level', width=290,
                           options=[ft.dropdown.Option(str(x)) for x in range(1, 11)], value=str(level))
    description = ft.TextField(label='Describe the situation (at least 10 characters)',
                               multiline=True, min_lines=3, max_lines=5, width=610)
    results = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    def notice(text, error=False):
        message.value = text
        message.color = ERROR if error else SUCCESS
        page.update()

    def action_button(label, handler):
        return ft.OutlinedButton(label, on_click=handler)

    def submit(e):
        try:
            report_id = connect.create_report(user_id, kind.value, location.value,
                                              urgency.value, description.value)
            description.value = ''
            notice(f'Report #{report_id} submitted. This is a simulated request; no team has been dispatched.')
            refresh()
        except Exception as ex:
            notice(str(ex), True)

    def report_card(r, admin=False):
        rid = r['ID']
        lines = [ft.Text(f"#{rid}  |  {r['Category']}  |  Level {r['Level']}  |  {r['Urgency']}",
                         weight=ft.FontWeight.BOLD, color=ACCENT),
                 ft.Text(f"Status: {r['Status']}", color=TEXT),
                 ft.Text(r['Description'], color=TEXT),
                 ft.Text(f"Coordinator note: {r.get('CoordinatorNote') or 'None yet'}", color=TEXT_DIM)]
        if admin:
            lines.append(ft.Text(f"Reporter: {r['ReporterID']}  |  Team: {r.get('TeamName') or 'Unassigned'}", color=TEXT_DIM))
            note = ft.TextField(label='Coordinator note', width=380)
            lines.append(note)
            team_options = []
            if r['Status'] == 'Acknowledged':
                try:
                    team_options = connect.available_teams(r['Category'], r['Level'])
                except Exception as ex:
                    lines.append(ft.Text(f'Team lookup failed: {ex}', color=ERROR))
            team = ft.Dropdown(label='Available compatible team', width=360,
                options=[ft.dropdown.Option(str(t['ID']), f"{t['TeamName']} (Level {t['Level']})")
                         for t in team_options])
            if team_options:
                team.value = str(team_options[0]['ID'])
                lines.append(team)

            def do(action):
                def handler(e):
                    try:
                        connect.update_report(user_id, rid, action, team.value if action == 'Assign' else None, note.value)
                        notice(f'Report #{rid}: {action.lower()} completed.')
                        refresh()
                    except Exception as ex:
                        notice(str(ex), True)
                return handler

            actions = {'Submitted':['Acknowledge','Cancel'],
                       'Acknowledged':['Assign','Cancel'],
                       'Assigned':['Dispatch','Cancel'],
                       'Dispatched':['Resolve']}.get(r['Status'], [])
            if actions:
                lines.append(ft.Row([action_button(a, do(a)) for a in actions], wrap=True))
        return ft.Container(bgcolor=CARD_BG, border=ft.Border.all(1, ACCENT_DIM),
                            border_radius=6, padding=16, content=ft.Column(lines, spacing=8))

    def refresh(e=None):
        try:
            reports = connect.active_reports() if is_admin else connect.my_reports(user_id)
            news = connect.announcements(None if is_admin else int(level))
            results.controls = [ft.Text('ACTIVE EMERGENCIES' if is_admin else 'MY REPORTS',
                                        size=19, weight=ft.FontWeight.BOLD, color=ACCENT)]
            results.controls.extend(report_card(r, is_admin) for r in reports)
            if not reports:
                results.controls.append(ft.Text('No reports to display.', color=TEXT_DIM))
            results.controls.append(ft.Text('ANNOUNCEMENTS', size=19, weight=ft.FontWeight.BOLD, color=ACCENT))
            for a in news:
                results.controls.append(ft.Container(padding=12, bgcolor=CARD_BG,
                    content=ft.Column([ft.Text(a['Title'], color=ACCENT, weight=ft.FontWeight.BOLD),
                                       ft.Text(a['Body'], color=TEXT)])))
            if not news:
                results.controls.append(ft.Text('No announcements yet.', color=TEXT_DIM))
            page.update()
        except Exception as ex:
            notice(f'Database error: {ex}', True)

    intro = [ft.Row([ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=ACCENT,
                                   on_click=lambda e: on_back()),
                     ft.Text('HOLLOW-CONNECT', size=24, color=ACCENT, weight=ft.FontWeight.BOLD)]),
             ft.Text('Emergency communication • fictional simulation only', color=TEXT_DIM),
             message]
    if not is_admin:
        intro += [ft.Text('REPORT AN EMERGENCY', size=18, color=TEXT),
                  ft.Row([kind, urgency, location], wrap=True), description,
                  ft.ElevatedButton('Submit report', on_click=submit)]
    else:
        title = ft.TextField(label='Announcement title', width=320)
        body = ft.TextField(label='Announcement message', width=500, multiline=True)
        target = ft.Dropdown(label='Audience', width=200,
            options=[ft.dropdown.Option('all', 'All levels')] +
                    [ft.dropdown.Option(str(i), f'Level {i}') for i in range(1,11)], value='all')
        def publish(e):
            try:
                connect.post_announcement(user_id, title.value, body.value,
                                          None if target.value == 'all' else int(target.value))
                title.value, body.value = '', ''
                notice('Announcement published.')
                refresh()
            except Exception as ex:
                notice(str(ex), True)
        intro += [ft.Text('COORDINATOR DASHBOARD', size=18, color=TEXT),
                  ft.Row([title, target], wrap=True), body,
                  ft.ElevatedButton('Publish announcement', on_click=publish)]
    intro.append(ft.OutlinedButton('Refresh reports', on_click=refresh))
    page.controls.clear()
    page.bgcolor = BG_TOP
    page.add(ft.Container(expand=True, padding=24, content=ft.Column(
        intro + [ft.Divider(color=ACCENT_DIM), results], expand=True, spacing=12)))
    refresh()
