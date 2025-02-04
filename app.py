# app.py
from flask import Flask, request, session, render_template, url_for, redirect
import os, json
from flask_mail import Mail, Message
from passlib.hash import bcrypt_sha256
from datetime import datetime

# DB接続用 (PyMySQL)
from db import get_connection

######################################
# Flask基本設定
######################################
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッションキー

# カスタムフィルタの定義
@app.template_filter('format_thousand')
def format_thousand(value):
    try:
        value = int(value)
        return f"{value:,}"
    except:
        return value

# Flask-Mail の設定 (Gmail) - 例
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nworks12345@gmail.com'
app.config['MAIL_PASSWORD'] = 'yspr vktd yrmc wntn'
app.config['MAIL_DEFAULT_SENDER'] = 'nworks12345@gmail.com'

mail = Mail(app)

######################################
# （旧）STL解析用定数・関数（現状は未使用）
######################################
CERAMIC_DENSITY = 0.003
CERAMIC_PRICE_PER_GRAM = 1.2

def calc_quantity_factor(q):
    """
    生産数 q に応じて数量係数を可変にする例。
    q が大きいほど単価が下がる想定で指数関数的に補正。
    """
    factor_min = 1.1
    factor_max = 6.0
    if q < 1: q = 1
    if q > 20000: q = 20000
    exponent = (q - 1) / (20000 - 1)
    return factor_max * ((factor_min / factor_max) ** exponent)

######################################
# ルーティング (ユーザ関連)
######################################
@app.route('/')
def index():
    # 最初はログイン画面へ誘導
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
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

        # パスワードハッシュ照合
        if user and bcrypt_sha256.verify(password, user['password_hash']):
            session.clear()
            session['user_id'] = user['id']
            session['email'] = user['email']
            return redirect(url_for('dashboard'))
        else:
            return "ログイン失敗: メールアドレスまたはパスワードが違います。"

@app.route('/register', methods=['GET','POST'])
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
        except:
            conn.close()
            return "登録に失敗しました。既に使われているメールアドレスかもしれません。"
        conn.close()

        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return "ログアウトしました。<br><a href='/login'>ログイン画面へ</a>"

@app.route('/guest_estimate')
def guest_estimate():
    # ゲストモードフラグを立てる
    session.clear()
    session['guest_mode'] = True
    return redirect(url_for('dashboard'))

######################################
# (ページ1) ダッシュボード入力
######################################
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/dashboard_post', methods=['POST'])
def dashboard_post():
    try:
        sales_price     = float(request.form.get('sales_price'))
        order_quantity  = int(request.form.get('order_quantity'))
        product_weight  = float(request.form.get('product_weight'))
        mold_unit_price = float(request.form.get('mold_unit_price'))
        mold_count      = int(request.form.get('mold_count'))
        glaze_cost      = float(request.form.get('glaze_cost'))
        kiln_count      = int(request.form.get('kiln_count'))
        gas_unit_price  = float(request.form.get('gas_unit_price'))
        loss_defective  = float(request.form.get('loss_defective'))
    except Exception as e:
        return "入力値が不正です: " + str(e)
    
    # ダミー計算例：各項目の数値を合計して最終合計（total_cost）とする
    total_cost = (sales_price + order_quantity + product_weight +
                  mold_unit_price + mold_count + glaze_cost +
                  kiln_count + gas_unit_price + loss_defective)
    
    # 入力内容を辞書にまとめる
    dashboard_data = {
        "sales_price": sales_price,
        "order_quantity": order_quantity,
        "product_weight": product_weight,
        "mold_unit_price": mold_unit_price,
        "mold_count": mold_count,
        "glaze_cost": glaze_cost,
        "kiln_count": kiln_count,
        "gas_unit_price": gas_unit_price,
        "loss_defective": loss_defective,
        "total_cost": total_cost
    }
    
    # ログインユーザならDBに登録（activeな見積もりは最大3件まで）
    estimate_id = None
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM estimates WHERE user_id=%s AND status='active'", (user_id,))
            active_count = cursor.fetchone()['cnt']
            if active_count >= 3:
                cursor.execute("""
                  SELECT id FROM estimates
                   WHERE user_id=%s AND status='active'
                   ORDER BY created_at ASC LIMIT 1
                """, (user_id,))
                oldest_id = cursor.fetchone()['id']
                cursor.execute("UPDATE estimates SET status='deleted', deleted_at=NOW() WHERE id=%s", (oldest_id,))
                _cleanup_deleted(user_id, cursor)
            sql = """
              INSERT INTO estimates (user_id, estimate_data, status, sent_at, deleted_at)
              VALUES (%s, %s, 'active', NULL, NULL)
            """
            cursor.execute(sql, (user_id, json.dumps(dashboard_data)))
            estimate_id = cursor.lastrowid
        conn.commit()
        conn.close()
    
    # セッションに入力内容とDB登録用のIDを保存
    session['dashboard_data'] = dashboard_data
    session['estimate_id'] = estimate_id
    
    return render_template('dashboard_result.html', dashboard_data=dashboard_data)

def _cleanup_deleted(user_id, cursor):
    cursor.execute("SELECT COUNT(*) as cnt FROM estimates WHERE user_id=%s AND status='deleted'", (user_id,))
    del_count = cursor.fetchone()['cnt']
    if del_count > 30:
        cursor.execute("""
          SELECT id FROM estimates
           WHERE user_id=%s AND status='deleted'
           ORDER BY deleted_at ASC LIMIT 1
        """, (user_id,))
        oldest = cursor.fetchone()
        if oldest:
            cursor.execute("DELETE FROM estimates WHERE id=%s", (oldest['id'],))

######################################
# (ページ2) 問い合わせ（最終確認）画面
######################################
@app.route('/final_contact', methods=['GET','POST'])
def final_contact():
    if request.method == 'GET':
        dashboard_data = session.get('dashboard_data', {})
        return render_template('final_contact.html', dashboard_data=dashboard_data)
    else:
        name = request.form.get('name')
        company = request.form.get('company','')
        email = request.form.get('email')
        dashboard_data = session.get('dashboard_data', {})
        total_cost = dashboard_data.get('total_cost', 0)
        
        # DB更新：ログインユーザの場合、見積もりの状態を「sent」に更新
        user_id = session.get('user_id')
        estimate_id = session.get('estimate_id')
        if user_id and estimate_id:
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                  UPDATE estimates
                     SET status='sent', sent_at=NOW()
                   WHERE id=%s AND user_id=%s
                """, (estimate_id, user_id))
            conn.commit()
            conn.close()
        
        # メール送信用内容（ダッシュボード入力項目を記載）
        body_text = f"""
お名前: {name}
企業名: {company}
メールアドレス: {email}
売価: {dashboard_data.get('sales_price')}
発注数: {dashboard_data.get('order_quantity')}
製品重量: {dashboard_data.get('product_weight')}
使用型単価: {dashboard_data.get('mold_unit_price')}
使用型の数出し数: {dashboard_data.get('mold_count')}
釉薬代: {dashboard_data.get('glaze_cost')}
窯入数: {dashboard_data.get('kiln_count')}
ガス単価: {dashboard_data.get('gas_unit_price')}
ロス 不良: {dashboard_data.get('loss_defective')}
最終合計: {total_cost}
"""
        msg = Message("見積もりお問い合わせ", recipients=["nworks12345@gmail.com"])
        msg.body = body_text

        # ※現状、ファイル添付は不要のため実施せず
        mail.send(msg)

        # セッションのダッシュボード関連データをクリア
        for key in ['dashboard_data', 'estimate_id']:
            session.pop(key, None)

        return "<h2>お問い合わせが送信されました。</h2><p><a href='/dashboard'>新しい見積もり</a> | <a href='/history'>履歴</a> | <a href='/logout'>ログアウト</a></p>"

######################################
# (ページ3) 履歴画面 (JSONをPython側であらかじめパース)
######################################
@app.route('/history')
def history():
    if 'user_id' not in session:
        return "ログインしていません。<br><a href='/login'>ログイン</a>"

    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        # active
        cursor.execute("""
          SELECT id, estimate_data, created_at 
            FROM estimates
           WHERE user_id=%s AND status='active'
           ORDER BY created_at DESC
        """, (user_id,))
        active_list = cursor.fetchall()
        for row in active_list:
            row['estimate_data'] = json.loads(row['estimate_data'])
        # deleted
        cursor.execute("""
          SELECT id, estimate_data, created_at, deleted_at
            FROM estimates
           WHERE user_id=%s AND status='deleted'
           ORDER BY deleted_at DESC
        """, (user_id,))
        deleted_list = cursor.fetchall()
        for row in deleted_list:
            row['estimate_data'] = json.loads(row['estimate_data'])
        # sent
        cursor.execute("""
          SELECT id, estimate_data, created_at, sent_at
            FROM estimates
           WHERE user_id=%s AND status='sent'
           ORDER BY sent_at DESC
        """, (user_id,))
        sent_list = cursor.fetchall()
        for row in sent_list:
            row['estimate_data'] = json.loads(row['estimate_data'])
    conn.close()

    return render_template('history.html',
                           active_list=active_list,
                           deleted_list=deleted_list,
                           sent_list=sent_list)

##########################################
# 「履歴でアクティブな見積もりを選ぶ」→「send_estimate を経由してセッションに再セット」→「既存の final_contact 画面へ」
##########################################
@app.route('/send_estimate/<int:estid>')
def send_estimate(estid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
          SELECT estimate_data 
            FROM estimates
           WHERE id=%s AND user_id=%s AND status='active'
        """, (estid, user_id))
        row = cursor.fetchone()
    conn.close()

    if not row:
        return "この見積もりは存在しないか、既に削除または送信済みです。"

    data = json.loads(row['estimate_data'])
    session['estimate_id']  = estid
    session['dashboard_data'] = data
    return redirect(url_for('final_contact'))

@app.route('/delete_estimate/<int:estid>')
def delete_estimate(estid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
          UPDATE estimates SET status='deleted', deleted_at=NOW()
           WHERE id=%s AND user_id=%s
        """, (estid, user_id))
        _cleanup_deleted(user_id, cursor)
    conn.commit()
    conn.close()
    return redirect(url_for('history'))

@app.route('/pdf_only/<int:estid>')
def pdf_only(estid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
          SELECT estimate_data, status FROM estimates
           WHERE id=%s AND user_id=%s
        """, (estid, user_id))
        row = cursor.fetchone()
    conn.close()

    if not row:
        return "見積もりが見つかりません。"
    if row['status'] != 'deleted':
        return "これは削除済みではありません。"

    data = json.loads(row['estimate_data'])
    price = data.get('total_cost', 0)
    return f"<h2>削除済み見積もり (PDFダミー)</h2><p>合計金額: {price} 円</p><p><a href='/history'>戻る</a></p>"

######################################
# メイン
######################################
if __name__ == '__main__':
    app.run(debug=True)
