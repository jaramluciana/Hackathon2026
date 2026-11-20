import os
import pyodbc
from contextlib import contextmanager

# run.bat sets HOLLOW_DB_SERVER for friends (SQL Express = localhost\SQLEXPRESS)
SERVER = os.environ.get("HOLLOW_DB_SERVER", "localhost")
DATABASE = os.environ.get("HOLLOW_DB_NAME", "ResidentInfors")


def _driver():
    """Newest installed 'ODBC Driver N for SQL Server'."""
    found = [d for d in pyodbc.drivers()
             if d.startswith("ODBC Driver") and d.endswith("for SQL Server")]
    if not found:
        raise RuntimeError("No SQL Server ODBC driver installed")
    return sorted(found, key=lambda d: int(d.split()[2]))[-1]


def get_connection():
    return pyodbc.connect(
        f"DRIVER={{{_driver()}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;",   # needed by Driver 18 on local servers
        timeout=5,
    )

@contextmanager
def connection():
    """Dùng: with connection() as conn: ...  (tự đóng dù có lỗi)"""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def check_login(user_id, password):
    """Returns ("ok", level), ("wrong", None) or ("error", None)."""
    try:
        with connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ISNULL([Level], 1) FROM Account "
                "WHERE UserID = ? AND Password = ?",
                (user_id, password),
            )
            row = cursor.fetchone()
        if row is None:
            return "wrong", None
        return "ok", int(row[0])
    except Exception as ex:
        print("Database error:", ex)
        return "error", None


def create_account(first_name, last_name, dob, password, level, work,
                   important=None):
    """important: True = force important, None = decided by occupation."""
    try:
        with connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SET NOCOUNT ON;"
                "DECLARE @id NVARCHAR(50);"
                "EXEC dbo.usp_CreateAccount ?, ?, ?, ?, ?, ?, "
                "     @Important = ?, @NewUserID = @id OUTPUT;"
                "SELECT @id;",
                (first_name, last_name, dob, level, password, work, important),
            )
            new_id = cursor.fetchone()[0]
            conn.commit()
        return "ok", new_id
    except Exception as ex:
        print("Database error:", ex)
        return "error", None
    
def get_profile(user_id, password):
    """Returns ("ok", dict), ("wrong", None) or ("error", None)."""
    try:
        with connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT a.UserID, a.FirstName, a.LastName, a.DateOfBirth, "
                "       ISNULL(a.[Level], 1), r.Work, r.Salary, r.Money, "
                "       r.LiveStatus, r.Important "
                "FROM Account AS a "
                "LEFT JOIN Residents AS r ON r.ID = a.ResidentID "
                "WHERE a.UserID = ? AND a.Password = ?",
                (user_id, password),
            )
            row = cursor.fetchone()
        if row is None:
            return "wrong", None
        return "ok", {
            "id": row[0],
            "first_name": row[1] or "—",
            "last_name": row[2] or "—",
            "dob": row[3].strftime("%d/%m/%Y") if row[3] else "—",
            "level": int(row[4]),
            "work": row[5].capitalize() if row[5] else "—",
            "salary": f"{row[6]:,}" if row[6] is not None else "—",
            "money": f"{row[7]:,}" if row[7] is not None else "—",
            "status": row[8].upper() if row[8] else "—",
            "important": ("YES" if row[9] else "NO") if row[9] is not None else "—",
        }
    except Exception as ex:
        print("Database error:", ex)
        return "error", None
    

def get_full_name(user_id):
    """Returns 'LastName FirstName'. Falls back to the ID if names are empty."""
    try:
        with connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT LastName, FirstName FROM Account WHERE UserID = ?",
                (user_id,),
            )
            row = cursor.fetchone()
        if row:
            parts = [p.strip() for p in row if p and p.strip()]
            if parts:
                return " ".join(parts)
        return user_id
    except Exception as ex:
        print("Database error:", ex)
        return user_id
    
def update_profile(user_id, password, first_name, last_name, dob):
    """Returns "ok", "wrong" (password not correct) or "error"."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Account SET FirstName = ?, LastName = ?, DateOfBirth = ? "
            "WHERE UserID = ? AND Password = ?",
            (first_name, last_name, dob, user_id, password),
        )
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        return "ok" if updated else "wrong"
    except Exception as ex:
        print("Database error:", ex)
        return "error"
