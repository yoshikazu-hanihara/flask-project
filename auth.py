# auth.py
from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_connection
from passlib.hash import bcrypt_sha256

# Blueprint の作成（'auth' が Blueprint 名、__name__ はモジュール名）
auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            return "メールアドレス / パスワードを入力してください。"
        conn = get_connection()
        user = None
        with conn.cursor() as cursor:
            sql = "SELECT * FROM users WHERE email=%s"
            cursor.execute(sql, (email,))
            user = cursor.fetchone()
        conn.close()
        if user and bcrypt_sha256.verify(password, user['password_hash']):
            session.clear()
            session['user_id'] = user['id']
            session['email'] = user['email']
            return redirect(url_for('dashboard'))
        else:
            return "ログイン失敗: メールアドレスまたはパスワードが違います。"

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            return "必須項目が未入力です。"
        password_hash = bcrypt_sha256.hash(password)
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)", (email, password_hash))
            conn.commit()
        except Exception:
            conn.close()
            return "登録に失敗しました。既に使われているメールアドレスかもしれません。"
        conn.close()
        return redirect(url_for('auth.login'))

@auth.route('/logout')
def logout():
    session.clear()
    return "ログアウトしました。<br><a href='/login'>ログイン画面へ</a>"
