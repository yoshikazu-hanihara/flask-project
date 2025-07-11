import pymysql
from pymysql.cursors import DictCursor

# Cache of the column name used for the account identifier
ACCOUNT_COLUMN = None

def get_connection():
    return pymysql.connect(
        host='localhost',
        user='flaskuser',
        password='Flask2025#0722Password!',
        db='flaskdb',
        charset='utf8mb4',
        cursorclass=DictCursor
    )


def get_account_column() -> str:
    """Return the column name used to identify accounts in the users table."""
    global ACCOUNT_COLUMN
    if ACCOUNT_COLUMN:
        return ACCOUNT_COLUMN

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for candidate in ('account_name', 'username', 'email'):
                cursor.execute("SHOW COLUMNS FROM users LIKE %s", (candidate,))
                if cursor.fetchone():


                    
                    ACCOUNT_COLUMN = candidate
                    break
            if not ACCOUNT_COLUMN:
                cursor.execute("SHOW COLUMNS FROM users")
                cols = [row['Field'] for row in cursor.fetchall()]
                raise RuntimeError(
                    'users table must contain account_name, username or email column. '
                    f"Available columns: {', '.join(cols)}"
                )
    finally:
        conn.close()

    return ACCOUNT_COLUMN
