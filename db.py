# db.py
import pymysql
def get_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',  # rootにパスワード設定があれば記入
        database='flaskdb',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
