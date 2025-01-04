# db.py
import pymysql
def get_connection():
    return pymysql.connect(
    host='localhost',
    user='flaskuser',
    password='FlaskPassword0722',
    db='flaskdb',
    charset='utf8mb4'
)
