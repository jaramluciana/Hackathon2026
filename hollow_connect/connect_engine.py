"""HOLLOW-CONNECT: SQL Server emergency reporting and coordinator workflow.
Uses the team's database.get_connection(); never changes existing tables.
This is a fictional hackathon simulation, not real emergency dispatch.
"""
from datetime import datetime
import database

TYPES = ('Medical', 'Fire', 'Housing', 'Security', 'Resources', 'Infrastructure', 'Other')
URGENCIES = ('Standard', 'Urgent', 'Critical')
STATUSES = ('Submitted', 'Acknowledged', 'Assigned', 'Dispatched', 'Resolved', 'Cancelled')
TEAM_TYPES = ('Medical', 'Rescue', 'Engineering', 'Security', 'Resource Support')


def validate_report(kind, level, urgency, description):
    if kind not in TYPES:
        raise ValueError('Select a valid emergency type.')
    try:
        level = int(level)
    except (TypeError, ValueError):
        raise ValueError('Level must be a number from 1 to 10.')
    if not 1 <= level <= 10:
        raise ValueError('Level must be between 1 and 10.')
    if urgency not in URGENCIES:
        raise ValueError('Select a valid urgency.')
    description = (description or '').strip()
    if not 10 <= len(description) <= 1500:
        raise ValueError('Description must contain 10–1500 characters.')
    return kind, level, urgency, description


def recommended_team(kind):
    return {
        'Medical': 'Medical', 'Fire': 'Rescue', 'Housing': 'Rescue',
        'Security': 'Security', 'Resources': 'Resource Support',
        'Infrastructure': 'Engineering', 'Other': 'Rescue',
    }[kind]


def _rows(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _account(cur, user_id):
    row = cur.execute('SELECT UserID, ISNULL([Level],1) FROM Account WHERE UserID=?', user_id).fetchone()
    if not row:
        raise ValueError('Unknown resident account.')
    return str(row[0]), int(row[1])


def _transaction(work):
    conn = database.get_connection()
    try:
        result = work(conn.cursor())
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_report(user_id, kind, level, urgency, description):
    kind, level, urgency, description = validate_report(kind, level, urgency, description)
    def work(cur):
        _account(cur, user_id)
        row = cur.execute('''INSERT INTO Connect_Reports
            (ReporterID, [Level], Category, Urgency, [Description], [Status])
            OUTPUT INSERTED.ID VALUES (?, ?, ?, ?, ?, 'Submitted')''',
            user_id, level, kind, urgency, description).fetchone()
        return int(row[0])
    return _transaction(work)


def my_reports(user_id):
    def work(cur):
        _account(cur, user_id)
        cur.execute('''SELECT ID, [Level], Category, Urgency, [Description], [Status],
            AssignedTeamID, CoordinatorNote, CreatedAt, UpdatedAt
            FROM Connect_Reports WHERE ReporterID=? ORDER BY ID DESC''', user_id)
        return _rows(cur)
    return _transaction(work)


def active_reports():
    def work(cur):
        cur.execute('''SELECT r.ID, r.ReporterID, r.[Level], r.Category, r.Urgency,
            r.[Description], r.[Status], r.AssignedTeamID, r.CoordinatorNote,
            r.CreatedAt, t.TeamName FROM Connect_Reports r
            LEFT JOIN Connect_Teams t ON t.ID=r.AssignedTeamID
            WHERE r.[Status] NOT IN ('Resolved','Cancelled')
            ORDER BY CASE r.Urgency WHEN 'Critical' THEN 0 WHEN 'Urgent' THEN 1 ELSE 2 END,
            r.CreatedAt''')
        return _rows(cur)
    return _transaction(work)


def available_teams(kind, level):
    if kind not in TYPES:
        raise ValueError('Invalid emergency type.')
    level = int(level)
    if not 1 <= level <= 10:
        raise ValueError('Invalid level.')
    team_type = recommended_team(kind)
    def work(cur):
        cur.execute('''SELECT ID, TeamName, TeamType, [Level], [Status], Capacity
            FROM Connect_Teams WHERE [Status]='Available' AND TeamType=?
            ORDER BY ABS([Level]-?), ID''', team_type, level)
        return _rows(cur)
    return _transaction(work)


def _coordinator(cur, user_id):
    # Demo authorization rule. Replace with a real role table before production.
    if str(user_id).lower() != 'admin':
        raise PermissionError('Only the demo admin may coordinate emergencies.')


def update_report(admin_id, report_id, action, team_id=None, note=''):
    if action not in ('Acknowledge', 'Assign', 'Dispatch', 'Resolve', 'Cancel'):
        raise ValueError('Unknown action.')
    note = (note or '').strip()[:1000]
    def work(cur):
        _coordinator(cur, admin_id)
        report = cur.execute('''SELECT [Status], AssignedTeamID, Category, [Level]
            FROM Connect_Reports WITH (UPDLOCK, ROWLOCK) WHERE ID=?''', int(report_id)).fetchone()
        if not report:
            raise ValueError('Report not found.')
        status, assigned, kind, level = report
        allowed = {
            'Submitted': ('Acknowledge', 'Cancel'),
            'Acknowledged': ('Assign', 'Cancel'),
            'Assigned': ('Dispatch', 'Cancel'),
            'Dispatched': ('Resolve',),
        }
        if action not in allowed.get(status, ()):
            raise ValueError(f'Cannot {action.lower()} a {status.lower()} report.')
        new_status = {'Acknowledge':'Acknowledged','Assign':'Assigned',
                      'Dispatch':'Dispatched','Resolve':'Resolved','Cancel':'Cancelled'}[action]
        if action == 'Assign':
            if team_id is None:
                raise ValueError('Choose an available team.')
            team = cur.execute('''SELECT TeamType, [Status] FROM Connect_Teams
                WITH (UPDLOCK, ROWLOCK) WHERE ID=?''', int(team_id)).fetchone()
            if not team or team[1] != 'Available' or team[0] != recommended_team(kind):
                raise ValueError('Team is unavailable or incompatible with this report.')
            cur.execute("UPDATE Connect_Teams SET [Status]='Busy' WHERE ID=?", int(team_id))
            assigned = int(team_id)
        if action in ('Resolve','Cancel') and assigned is not None:
            cur.execute("UPDATE Connect_Teams SET [Status]='Available' WHERE ID=?", assigned)
        cur.execute('''UPDATE Connect_Reports SET [Status]=?, AssignedTeamID=?,
            CoordinatorNote=?, UpdatedAt=SYSUTCDATETIME() WHERE ID=?''',
            new_status, assigned, note, int(report_id))
        cur.execute('''INSERT INTO Connect_History
            (ReportID, ActorID, Action, Note) VALUES (?, ?, ?, ?)''',
            int(report_id), str(admin_id), action, note)
        return new_status
    return _transaction(work)


def announcements(level=None):
    def work(cur):
        cur.execute('''SELECT TOP 30 ID, [Level], Title, Body, CreatedAt
            FROM Connect_Announcements WHERE [Level] IS NULL OR [Level]=?
            ORDER BY CreatedAt DESC''', level)
        return _rows(cur)
    return _transaction(work)


def post_announcement(admin_id, title, body, level=None):
    title, body = (title or '').strip(), (body or '').strip()
    if not (3 <= len(title) <= 120 and 5 <= len(body) <= 2000):
        raise ValueError('Provide a title (3–120) and message (5–2000 characters).')
    if level is not None and not 1 <= int(level) <= 10:
        raise ValueError('Invalid level.')
    def work(cur):
        _coordinator(cur, admin_id)
        cur.execute('''INSERT INTO Connect_Announcements
            ([Level], Title, Body, AuthorID) VALUES (?, ?, ?, ?)''',
            level, title, body, str(admin_id))
    _transaction(work)
