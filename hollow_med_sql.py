"""HOLLOW-MED integration for teammate's SQL Server + pyodbc app.
Simulation only: scores and forecasts are not clinical guidance.
Run setup_hollow_med.sql once before calling functions.
"""
from datetime import datetime
import math
import database

SYSTEM_WEIGHTS = {"oxygen": 1.0, "electricity": .1, "water": .4,
                  "food": .25, "medicine": .15, "communication": .02, "housing": .05}


def _one(cur, sql, *args):
    return cur.execute(sql, *args).fetchone()


def _resident(cur, user_id):
    # UserID is a string (A0000001); ResidentID is a separate key.
    row = _one(cur, """SELECT a.UserID, a.ResidentID, ISNULL(a.[Level],1),
                      r.Health, r.LiveStatus
                      FROM Account a LEFT JOIN Residents r ON r.ID=a.ResidentID
                      WHERE a.UserID=?""", user_id)
    if not row:
        raise ValueError("Unknown account")
    return dict(user_id=row[0], resident_id=row[1], level=int(row[2]),
                health=row[3], status=row[4])


def level_overview(level):
    """Fast per-level aggregate; avoids fetching all residents."""
    with database.get_connection() as con:
        cur = con.cursor()
        row = _one(cur, """SELECT l.Population,l.Alive,e.Rate_Health,e.Pending_Health
                           FROM Levels l LEFT JOIN Level_Effects e ON e.[Level]=l.[Level]
                           WHERE l.[Level]=?""", level)
        if not row:
            raise ValueError("Unknown level")
        systems = {str(s):float(v) for s,v in cur.execute(
            "SELECT System,[Status] FROM Level_Systems WHERE [Level]=?", level).fetchall()}
        clinics = [dict(id=int(r[0]), name=r[1], capacity=int(r[2]),
                        used=int(r[3]), available=max(0,int(r[2])-int(r[3])))
                   for r in cur.execute("""SELECT ClinicID,Name,SlotsTotal,SlotsUsed
                                          FROM Med_Clinics WHERE [Level]=?""", level).fetchall()]
        return dict(level=int(level), population=int(row[0] or 0), alive=int(row[1] or 0),
                    rate_health=float(row[2] or 0), pending_health=float(row[3] or 0),
                    systems=systems, clinics=clinics)


def forecast(level, sim_seconds=300):
    """Deterministic score-band estimate, not a clinical prediction.
    Includes already-urgent residents, newly urgent, and projected score zero.
    """
    if not (0 <= sim_seconds <= 86400):
        raise ValueError("Forecast must be between 0 and 86400 simulated seconds")
    with database.get_connection() as con:
        cur=con.cursor()
        row=_one(cur, "SELECT Rate_Health,Pending_Health FROM Level_Effects WHERE [Level]=?",level)
        if row is None: raise ValueError("Unknown level")
        loss=max(0.0,float(row[1] or 0)+float(row[0] or 0)*sim_seconds)
        # Aggregate in SQL, no million-row Python iteration.
        result=_one(cur, """SELECT
            COUNT_BIG(*),
            COALESCE(SUM(CASE WHEN Health>0 AND Health<=20 THEN 1 ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN Health>20 AND Health-?<=20 THEN 1 ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN Health>0 AND Health-?<=0 THEN 1 ELSE 0 END),0)
            FROM Residents WHERE [Level]=?""", loss,loss,level)
        return dict(level=int(level), horizon_seconds=sim_seconds,
                    estimated_health_loss=round(loss,2), population=int(result[0]),
                    currently_urgent=int(result[1]), newly_urgent=int(result[2]),
                    projected_zero_health=int(result[3]),
                    disclaimer="Fictional simulation score thresholds, not medical triage")


def resident_dashboard(user_id):
    with database.get_connection() as con:
        cur=con.cursor()
        resident=_resident(cur,user_id)
        requests=[dict(id=int(r[0]), kind=r[1], status=r[2], message=r[3])
                  for r in cur.execute("""SELECT TOP 20 RequestID,Kind,Status,Message
                                          FROM Med_Requests WHERE UserID=? ORDER BY RequestID DESC""",user_id).fetchall()]
        appointments=[dict(id=int(r[0]), clinic_id=int(r[1]), status=r[2], requested_at=str(r[3]))
                      for r in cur.execute("""SELECT TOP 20 AppointmentID,ClinicID,Status,CreatedAt
                                             FROM Med_Appointments WHERE UserID=? ORDER BY AppointmentID DESC""",user_id).fetchall()]
        notices=[dict(id=int(r[0]),message=r[1],level=r[2],created_at=str(r[3]))
                 for r in cur.execute("""SELECT TOP 20 NoticeID,Message,[Level],CreatedAt
                                        FROM Med_Notices WHERE [Level]=? OR [Level] IS NULL
                                        ORDER BY NoticeID DESC""",resident['level']).fetchall()]
    return dict(resident=resident, level=level_overview(resident['level']),
                requests=requests,appointments=appointments,notifications=notices)


def clinics(level=None):
    with database.get_connection() as con:
        cur=con.cursor()
        if level is None:
            rows=cur.execute("SELECT ClinicID,[Level],Name,SlotsTotal,SlotsUsed FROM Med_Clinics ORDER BY [Level]").fetchall()
        else:
            rows=cur.execute("SELECT ClinicID,[Level],Name,SlotsTotal,SlotsUsed FROM Med_Clinics WHERE [Level]=?",level).fetchall()
        return [dict(id=int(r[0]),level=int(r[1]),name=r[2],capacity=int(r[3]),
                     used=int(r[4]),available=max(0,int(r[3])-int(r[4]))) for r in rows]


def submit_request(user_id, kind, message):
    if kind not in ('medical','emergency','supplies'): raise ValueError('Invalid request type')
    message=message.strip()
    if not (1<=len(message)<=1000): raise ValueError('Message must be 1–1000 characters')
    with database.get_connection() as con:
        cur=con.cursor(); r=_resident(cur,user_id)
        cur.execute("""INSERT INTO Med_Requests(UserID,[Level],Kind,Message,Status)
                       VALUES (?,?,?,?, 'pending')""",user_id,r['level'],kind,message)
        con.commit()
    return 'Request submitted; awaiting staff acknowledgment. No team has been dispatched yet.'


def book_appointment(user_id,clinic_id):
    """Request a booking; not a confirmed timeslot until staff approves."""
    with database.get_connection() as con:
        cur=con.cursor(); r=_resident(cur,user_id)
        c=_one(cur,"SELECT ClinicID,SlotsTotal,SlotsUsed FROM Med_Clinics WHERE ClinicID=?",clinic_id)
        if not c: raise ValueError('Clinic not found')
        if int(c[2])>=int(c[1]): raise ValueError('Clinic currently at capacity')
        cur.execute("""INSERT INTO Med_Appointments(UserID,ClinicID,Status)
                       VALUES (?,?,'requested')""",user_id,clinic_id)
        con.commit()
    return 'Appointment requested; clinic confirmation is pending.'


def cancel_appointment(user_id,appointment_id):
    with database.get_connection() as con:
        cur=con.cursor()
        cur.execute("""UPDATE Med_Appointments SET Status='cancelled'
                       WHERE AppointmentID=? AND UserID=? AND Status='requested'""",appointment_id,user_id)
        changed=cur.rowcount; con.commit()
    return bool(changed)


def clinic_inventory(clinic_id):
    with database.get_connection() as con:
        return [dict(item=r[0],quantity=int(r[1]),reserve=int(r[2])) for r in con.cursor().execute(
            'SELECT Item,Quantity,Reserve FROM Med_Inventory WHERE ClinicID=?',clinic_id).fetchall()]


def suggest_support(target_level,item,quantity):
    """Read-only heuristic; does not reserve or transfer inventory."""
    if not isinstance(quantity,int) or quantity<=0: raise ValueError('Quantity must be positive integer')
    with database.get_connection() as con:
        cur=con.cursor()
        candidates=cur.execute("""SELECT c.ClinicID,c.[Level],c.Name,i.Quantity,i.Reserve
            FROM Med_Clinics c JOIN Med_Inventory i ON c.ClinicID=i.ClinicID
            WHERE i.Item=? ORDER BY ABS(c.[Level]-?),c.ClinicID""",item,target_level).fetchall()
        outstanding=cur.execute("""SELECT SourceClinicID,COALESCE(SUM(Quantity),0)
            FROM Med_Transfers WHERE Item=? AND Status IN ('proposed','approved','in_transit')
            GROUP BY SourceClinicID""",item).fetchall()
        reserved={int(r[0]):int(r[1]) for r in outstanding}
        remaining=quantity; plan=[]
        for cid,lvl,name,stock,reserve in candidates:
            if int(lvl)==int(target_level): continue
            available=max(0,int(stock)-int(reserve)-reserved.get(int(cid),0))
            take=min(remaining,available)
            if take:
                plan.append(dict(clinic_id=int(cid),level=int(lvl),name=name,quantity=take))
                remaining-=take
            if remaining==0:break
        return dict(requested=quantity,allocated=quantity-remaining,unmet=remaining,
                    item=item,target_level=target_level,proposals=plan,
                    note='Suggestions only; nothing has been dispatched or transferred.')


def publish_notice(level,message):
    if not message.strip(): raise ValueError('Empty notice')
    with database.get_connection() as con:
        con.cursor().execute('INSERT INTO Med_Notices([Level],Message) VALUES (?,?)',level,message.strip())
        con.commit()
