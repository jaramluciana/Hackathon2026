"""HOLLOW-EXPLORE: simulated surface expeditions, SQLite + standard library."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name('hollow_world.sqlite3')
SECTORS = [
 ('A1','North Ridge',18,18,'surveyed',18,'water',0.85,'Water samples reported; verification pending'),
 ('A2','Old Transit Station',43,24,'surveyed',27,'equipment',0.9,'Recoverable transit parts'),
 ('A3','Red Zone',79,20,'hazardous',88,'unknown',0.5,'High hazard readings; no access'),
 ('B1','Hollow Exit',50,78,'base',5,'none',1.0,'Protected access to the Hollow'),
 ('B2','Western Reservoir',20,60,'surveyed',30,'water',0.8,'Potential water supply'),
 ('B3','Abandoned Depot',80,65,'unexplored',53,'equipment',0.35,'Unverified salvage signal'),
 ('C1','Southern Valley',44,49,'unexplored',45,'food',0.2,'Unknown terrain'),
]
MISSIONS = [
 ('Survey Western Reservoir','B2','survey',2,180,35,'scavenger,engineer,technician','Collect water and terrain samples'),
 ('Recover Transit Equipment','A2','recovery',3,260,45,'engineer,technician,scavenger','Catalog and recover reusable components'),
 ('Map Southern Valley','C1','mapping',3,220,55,'scavenger,guard,technician','Document safe paths and unknown terrain'),
]
SCHEMA = '''
CREATE TABLE IF NOT EXISTS surface_sectors (
 code TEXT PRIMARY KEY,name TEXT NOT NULL,x REAL NOT NULL,y REAL NOT NULL,
 status TEXT NOT NULL,hazard INTEGER NOT NULL CHECK(hazard BETWEEN 0 AND 100),
 resource TEXT NOT NULL,confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),notes TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exploration_missions (
 id INTEGER PRIMARY KEY,title TEXT NOT NULL,sector_code TEXT NOT NULL REFERENCES surface_sectors(code),
 kind TEXT NOT NULL,duration_hours REAL NOT NULL,base_reward INTEGER NOT NULL,
 max_hazard INTEGER NOT NULL,preferred_jobs TEXT NOT NULL,objective TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','paused','closed')));
CREATE TABLE IF NOT EXISTS exploration_applications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,mission_id INTEGER NOT NULL REFERENCES exploration_missions(id),
 resident_id INTEGER NOT NULL REFERENCES residents(id),status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','approved','rejected','active','completed','cancelled')),
 applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,completed_at TEXT,
 UNIQUE(mission_id,resident_id));
CREATE TABLE IF NOT EXISTS exploration_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT,application_id INTEGER NOT NULL UNIQUE REFERENCES exploration_applications(id),
 findings TEXT NOT NULL,resource_found TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,
 submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS exploration_rewards (
 id INTEGER PRIMARY KEY AUTOINCREMENT,application_id INTEGER NOT NULL UNIQUE REFERENCES exploration_applications(id),
 resident_id INTEGER NOT NULL REFERENCES residents(id),amount INTEGER NOT NULL CHECK(amount>=0),
 paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS exploration_alerts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,sector_code TEXT NOT NULL REFERENCES surface_sectors(code),
 severity TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
'''

def connect(path=DB_PATH):
    con=sqlite3.connect(str(path),timeout=15)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con

def init(con):
    if not con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='residents'").fetchone():
        raise ValueError('Initialize the Hollow residents database first (see README).')
    con.executescript(SCHEMA)
    with con:
        con.executemany('INSERT OR IGNORE INTO surface_sectors VALUES (?,?,?,?,?,?,?,?,?)',SECTORS)
        con.executemany('''INSERT OR IGNORE INTO exploration_missions
        (id,title,sector_code,kind,duration_hours,base_reward,max_hazard,preferred_jobs,objective)
        VALUES (NULL,?,?,?,?,?,?,?,?)''',MISSIONS)

def rows(con,sql,args=()):
    return [dict(r) for r in con.execute(sql,args)]

def map_data(con):
    return rows(con,'SELECT * FROM surface_sectors ORDER BY code')

def missions(con):
    return rows(con,'''SELECT m.*,s.name AS sector_name,s.hazard,s.status AS sector_status,
      (SELECT COUNT(*) FROM exploration_applications a WHERE a.mission_id=m.id AND a.status IN ('approved','active')) AS team_size
      FROM exploration_missions m JOIN surface_sectors s ON s.code=m.sector_code ORDER BY m.id''')

def resident(con,resident_id):
    r=con.execute('SELECT id,work,health,level,money FROM residents WHERE id=?',(resident_id,)).fetchone()
    if not r: raise ValueError('Resident not found')
    return dict(r)

def equipment(duration_hours,sector_hazard=0):
    if not (0 < duration_hours <= 24): raise ValueError('Duration must be between 0 and 24 hours')
    if not (0 <= sector_hazard <= 100): raise ValueError('Invalid hazard level')
    # All figures are fictional planning assumptions, not real-world safety guidance.
    outbound=duration_hours/2
    oxygen=round(100-duration_hours*(9+sector_hazard*.04),1)
    battery=round(100-duration_hours*(7+sector_hazard*.03),1)
    water=round(100-duration_hours*6,1)
    return {'oxygen':max(0,oxygen),'battery':max(0,battery),'water':max(0,water),
      'return_reserve_ok':oxygen>=25 and battery>=20 and water>=20,
      'estimated_outbound_hours':outbound,'simulation_only':True}

def eligibility(con,resident_id,mission_id):
    r=resident(con,resident_id)
    m=con.execute('''SELECT m.*,s.hazard,s.status AS sector_status FROM exploration_missions m
        JOIN surface_sectors s ON s.code=m.sector_code WHERE m.id=?''',(mission_id,)).fetchone()
    if not m: raise ValueError('Mission not found')
    reasons=[]
    if m['status']!='open': reasons.append('Mission is not open')
    if r['health']<65: reasons.append('Simulated health score below mission minimum (65)')
    if r['work'] not in m['preferred_jobs'].split(','): reasons.append('Additional training required for this role')
    if m['sector_status']=='hazardous' or m['hazard']>m['max_hazard']: reasons.append('Sector hazard exceeds mission authorization')
    if not equipment(m['duration_hours'],m['hazard'])['return_reserve_ok']: reasons.append('Insufficient projected return reserves')
    return {'eligible':not reasons,'reasons':reasons,'resident':r,'mission_id':mission_id}

def apply(con,resident_id,mission_id):
    result=eligibility(con,resident_id,mission_id)
    if not result['eligible']: raise ValueError('; '.join(result['reasons']))
    with con:
        try:
            cur=con.execute('INSERT INTO exploration_applications(mission_id,resident_id) VALUES (?,?)',(mission_id,resident_id))
        except sqlite3.IntegrityError: raise ValueError('You have already applied for this mission') from None
    return {'application_id':cur.lastrowid,'status':'pending','message':'Application submitted for coordinator review'}

def applications(con,resident_id=None):
    q='''SELECT a.*,m.title,m.base_reward,r.work,r.health FROM exploration_applications a
    JOIN exploration_missions m ON m.id=a.mission_id JOIN residents r ON r.id=a.resident_id'''
    if resident_id is not None: q+=' WHERE a.resident_id=?'
    return rows(con,q+' ORDER BY a.id DESC',() if resident_id is None else (resident_id,))

def decide(con,application_id,decision):
    if decision not in ('approved','rejected'): raise ValueError('Invalid decision')
    with con:
        cur=con.execute('UPDATE exploration_applications SET status=? WHERE id=? AND status=?',
                        (decision,application_id,'pending'))
        if not cur.rowcount: raise ValueError('Only pending applications can be reviewed')
    return {'status':decision}

def start(con,application_id):
    with con:
        cur=con.execute("UPDATE exploration_applications SET status='active' WHERE id=? AND status='approved'",(application_id,))
        if not cur.rowcount: raise ValueError('Application must be approved before starting')
    return {'status':'active'}

def submit_report(con,application_id,findings,resource_found):
    if not isinstance(findings,str) or len(findings.strip())<10 or len(findings)>2000: raise ValueError('Report must contain 10–2000 characters')
    if resource_found not in ('none','water','food','equipment','other'): raise ValueError('Invalid resource category')
    with con:
        r=con.execute('SELECT status FROM exploration_applications WHERE id=?',(application_id,)).fetchone()
        if not r or r['status']!='active': raise ValueError('Mission must be active to submit a report')
        con.execute('INSERT INTO exploration_reports(application_id,findings,resource_found) VALUES (?,?,?)',
                    (application_id,findings.strip(),resource_found))
    return {'status':'submitted','message':'Awaiting verification; no payment has been issued'}

def verify_report(con,report_id,approved):
    if type(approved) is not bool: raise ValueError('Approval must be true or false')
    with con:
        report=con.execute('''SELECT p.*,a.resident_id,a.status,m.base_reward,m.sector_code
          FROM exploration_reports p JOIN exploration_applications a ON a.id=p.application_id
          JOIN exploration_missions m ON m.id=a.mission_id WHERE p.id=?''',(report_id,)).fetchone()
        if not report or report['verified']: raise ValueError('Report missing or already reviewed')
        if not approved:
            con.execute('UPDATE exploration_reports SET verified=-1 WHERE id=?',(report_id,))
            return {'status':'rejected','paid':0}
        if report['status']!='active': raise ValueError('Mission is not active')
        # Completion pay is guaranteed for verified participation; small discovery bonus is optional.
        bonus=50 if report['resource_found']!='none' else 0
        pay=report['base_reward']+bonus
        con.execute('UPDATE exploration_reports SET verified=1 WHERE id=?',(report_id,))
        con.execute("UPDATE exploration_applications SET status='completed',completed_at=CURRENT_TIMESTAMP WHERE id=?",(report['application_id'],))
        con.execute('INSERT INTO exploration_rewards(application_id,resident_id,amount) VALUES (?,?,?)',
                    (report['application_id'],report['resident_id'],pay))
        con.execute('UPDATE residents SET money=money+? WHERE id=?',(pay,report['resident_id']))
        # A verified report upgrades confidence, but never automatically declares a dangerous sector safe.
        con.execute('UPDATE surface_sectors SET confidence=MIN(1,confidence+0.1) WHERE code=?',(report['sector_code'],))
    return {'status':'completed','paid':pay}

def reports(con):
    return rows(con,'''SELECT p.*,a.resident_id,m.title FROM exploration_reports p
      JOIN exploration_applications a ON a.id=p.application_id
      JOIN exploration_missions m ON m.id=a.mission_id ORDER BY p.id DESC''')

def summary(con):
    return {'missions':con.execute('SELECT COUNT(*) FROM exploration_missions').fetchone()[0],
      'active_explorers':con.execute("SELECT COUNT(*) FROM exploration_applications WHERE status='active'").fetchone()[0],
      'pending_applications':con.execute("SELECT COUNT(*) FROM exploration_applications WHERE status='pending'").fetchone()[0],
      'reports_to_verify':con.execute('SELECT COUNT(*) FROM exploration_reports WHERE verified=0').fetchone()[0],
      'credits_paid':con.execute('SELECT COALESCE(SUM(amount),0) FROM exploration_rewards').fetchone()[0]}

def bootstrap(path=DB_PATH, demo_residents=1000):
    path=Path(path)
    if not path.exists():
        import hollow_db
        con=hollow_db.build_database(path=str(path),n=demo_residents)
    else: con=connect(path)
    init(con)
    return con
