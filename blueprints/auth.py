# auth.py
from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_connection, get_account_column
from passlib.hash import bcrypt_sha256

# Blueprint の作成（'auth' が Blueprint 名、__name__ はモジュール名）
auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        account_name = request.form.get('account_name')
        password = request.form.get('password')
        if not account_name or not password:
            return "アカウント名 / パスワードを入力してください。"
        conn = get_connection()
        user = None
        with conn.cursor() as cursor:
            sql = f"SELECT * FROM users WHERE {account_col}=%s"
            cursor.execute(sql, (account_name,))
            user = cursor.fetchone()
        conn.close()
        if user and bcrypt_sha256.verify(password, user['password_hash']):
            session.clear()
            session['user_id'] = user['id']
            session['account_name'] = user.get(account_col, account_name)
            return redirect(url_for('dashboard.dashboard'))
        else:
            return "ログイン失敗: アカウント名またはパスワードが違います。"

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    else:
        account_name = request.form.get('account_name')
        password = request.form.get('password')
        if not account_name or not password:
            return "必須項目が未入力です。"
        password_hash = bcrypt_sha256.hash(password)
        account_col = get_account_column()
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # アカウント名の重複を事前にチェック
                cursor.execute(f"SELECT id FROM users WHERE {account_col}=%s", (account_name,))
                if cursor.fetchone():
                    conn.close()
                    return "登録に失敗しました。既に使われているアカウント名です。"

                cursor.execute(
                    f"INSERT INTO users ({account_col}, password_hash) VALUES (%s, %s)",
                    (account_name, password_hash),
                )
            conn.commit()
        except Exception:
            # 例外内容は伏せ、一般的なエラーとして扱う
            conn.close()
            return "登録に失敗しました。管理者にお問い合わせください。"
        conn.close()
        return redirect(url_for('auth.login'))

@auth.route('/logout')
def logout():
    session.clear()
    return "ログアウトしました。<br><a href='/login'>ログイン画面へ</a>"
