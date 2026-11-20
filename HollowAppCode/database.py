import pyodbc
import os
import pyodbc

SQL_SERVER = os.environ.get("HOLLOW_SQL_SERVER", "localhost")
SQL_DATABASE = os.environ.get("HOLLOW_SQL_DATABASE", "ResidentInfors")


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        "Trusted_Connection=yes;"
    )


def check_login(user_id, password):
    """Returns ("ok", level), ("wrong", None) or ("error", None)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ISNULL([Level], 1) FROM Account "
            "WHERE UserID = ? AND Password = ?",
            (user_id, password),
        )
        row = cursor.fetchone()
        conn.close()
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
        conn = get_connection()
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
        conn.close()
        return "ok", new_id
    except Exception as ex:
        print("Database error:", ex)
        return "error", None
    
def get_profile(user_id, password):
    """Returns ("ok", dict), ("wrong", None) or ("error", None)."""
    try:
        conn = get_connection()
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
        conn.close()
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
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT LastName, FirstName FROM Account WHERE UserID = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
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
