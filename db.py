import pymysql
from pymysql.cursors import DictCursor

def get_connection():
    return pymysql.connect(
        host='localhost',
        user='flaskuser',
        password='Flask2025#0722Password!',
        db='flaskdb',
        charset='utf8mb4',
        cursorclass=DictCursor
    )
