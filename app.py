from flask import Flask, request, session, render_template, url_for, redirect
import os, json
#from stl import mesh  # STL解析は今回使用しないのでコメントアウト
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
# 見積もりロジックの定数・関数
######################################
# ※従来の陶磁器用のSTL解析用定数は今回使用しないためコメントアウトまたは削除
# CERAMIC_DENSITY = 0.003
# CERAMIC_PRICE_PER_GRAM = 1.2

# Excelで示された各商品タイプ毎の定義
PRODUCTS = {
    'plate': {
        'name': 'φ240㎜プレート',
        'cost_items': {
            '坂岡 素地代': 300,
            '型代': 57,
            '窯値': 1300,
            '緩衝材': 15,
            '個装箱': 72,
            'アウターカートン': 130,
            'パッキングチャージ': 38,
            '運賃': 560,
            '楽天フィー': 1020,
            'HARUさんフィー': 265,
            '不良　発送手間賃・その他': 390,
        },
        'selling_price_per_unit': 5300,  # 単位あたりの販売価格
    },
    'plate_bowl': {
        'name': 'φ240㎜プレート+φ110㎜ボウル',
        'cost_items': {
            '坂岡 素地代': 440,
            '型代': 89,
            '窯値': 1800,
            '緩衝材': 20,
            '個装箱': 90,
            'アウターカートン': 140,
            'パッキングチャージ': 50,
            '運賃': 560,
            '楽天フィー': 1035,
            'HARUさんフィー': 345,
            '不良　発送手間賃・その他': 420,
        },
        'selling_price_per_unit': 6900,
    },
    'bowl': {
        'name': 'φ110㎜ボウル',
        'cost_items': {
            '坂岡 素地代': 140,
            '型代': 32,
            '窯値': 500,
            '緩衝材': 10,
            '個装箱': 35,
            'アウターカートン': 100,
            'パッキングチャージ': 25,
            '運賃': 560,
            '楽天フィー': 544,
            'HARUさんフィー': 150,
            '不良　発送手間賃・その他': 254,
        },
        'selling_price_per_unit': 3000,
    }
}

# ※従来の数量に応じた補正関数は不要なため削除

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
            return redirect(url_for('upload_form'))
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
    return redirect(url_for('upload_form'))

######################################
# (ページ1) 商品選択・数量入力
######################################
@app.route('/upload')
def upload_form():
    """
    ここでは STL ファイルアップロードではなく、Excel見積もりに沿った
    商品タイプ（例：plate, plate_bowl, bowl）と生産数（数量）を入力するフォームを表示する。
    """
    return render_template('upload.html')  # upload.html 側でドロップダウン等を用意すること

@app.route('/upload_post', methods=['POST'])
def upload_post():
    # STLファイルアップロード関連は削除し、商品タイプと数量で見積もりを計算する
    product_type = request.form.get('product_type')
    quantity_str = request.form.get('quantity', '200')  # デフォルトは200個
    if not product_type:
        return "商品タイプが選択されていません。"
    try:
        quantity = int(quantity_str)
    except:
        return "生産数が不正です。"

    if product_type not in PRODUCTS:
        return "無効な商品タイプです。"

    product = PRODUCTS[product_type]
    product_name = product['name']
    cost_items = product['cost_items']
    raw_unit_cost = sum(cost_items.values())
    total_raw_cost = raw_unit_cost * quantity
    selling_price_per_unit = product['selling_price_per_unit']
    final_total = selling_price_per_unit * quantity
    gross_profit_per_unit = selling_price_per_unit - raw_unit_cost
    total_gross_profit = gross_profit_per_unit * quantity
    gross_margin = round((gross_profit_per_unit / selling_price_per_unit) * 100, 1)

    # 見積もり情報を辞書にまとめる
    estimate_data = {
        "product_type": product_type,
        "product_name": product_name,
        "quantity": quantity,
        "cost_items": cost_items,
        "raw_unit_cost": raw_unit_cost,
        "total_raw_cost": total_raw_cost,
        "selling_price_per_unit": selling_price_per_unit,
        "final_total": final_total,
        "gross_profit_per_unit": gross_profit_per_unit,
        "total_gross_profit": total_gross_profit,
        "gross_margin": gross_margin,
        "calculation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # ログインユーザなら DB に登録
    estimate_id = None
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_connection()
        with conn.cursor() as cursor:
            # active が3件あれば最古を削除状態にする
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
            # 新規insert
            sql = """
              INSERT INTO estimates (user_id, estimate_data, status, sent_at, deleted_at)
              VALUES (%s, %s, 'active', NULL, NULL)
            """
            cursor.execute(sql, (user_id, json.dumps(estimate_data)))
            estimate_id = cursor.lastrowid
        conn.commit()
        conn.close()

    # セッションへ保存
    session['estimate_id'] = estimate_id
    session['estimate_data'] = estimate_data

    # 次画面へ（最終確認・連絡先入力）
    return redirect(url_for('final_contact'))

######################################
# (ページ3) 最終確認・連絡先入力
######################################
@app.route('/final_contact', methods=['GET','POST'])
def final_contact():
    if request.method == 'GET':
        # セッションに保存した見積もり情報をテンプレートへ渡す
        return render_template('final_contact.html', estimate_data=session.get('estimate_data'))
    else:
        name = request.form.get('name')
        company = request.form.get('company','')
        email = request.form.get('email')
        if not name or not email:
            return "必須項目（お名前、メールアドレス）を入力してください。"

        estimate_data = session.get('estimate_data', {})
        product_name = estimate_data.get('product_name', '')
        quantity = estimate_data.get('quantity', 0)
        final_total = estimate_data.get('final_total', 0)
        total_raw_cost = estimate_data.get('total_raw_cost', 0)
        gross_margin = estimate_data.get('gross_margin', 0)

        # DB更新：見積もりを「送信済み」に更新
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

        # メール送信（管理者宛）
        body_text = f"""
お名前: {name}
企業名: {company}
メールアドレス: {email}

【見積もり内容】
商品: {product_name}
生産数: {quantity} 個

【内訳】
原価合計: {total_raw_cost} 円
販売単価: {estimate_data.get('selling_price_per_unit')} 円
最終合計金額: {final_total} 円
粗利率: {gross_margin} ％

計算日時: {estimate_data.get('calculation_date')}
"""
        msg = Message("見積もりお問い合わせ", recipients=["nworks12345@gmail.com"])
        msg.body = body_text

        # ここでは STL ファイルの添付は行わない

        mail.send(msg)

        # 後始末：見積もり情報をセッションから削除
        for key in ['estimate_id', 'estimate_data']:
            session.pop(key, None)

        return "<h2>お問い合わせが送信されました。</h2><p><a href='/upload'>新しい見積もり</a> | <a href='/history'>履歴</a> | <a href='/logout'>ログアウト</a></p>"

######################################
# 履歴画面 (JSONをPython側であらかじめパース)
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

    return render_template(
        'history.html',
        active_list=active_list,
        deleted_list=deleted_list,
        sent_list=sent_list
    )

##########################################
# 「履歴から見積もりを再利用」関連のルーティング
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
    session['estimate_data'] = data

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
    price = data.get('final_total', 0)
    return f"<h2>削除済み見積もり (PDFダミー)</h2><p>合計金額: {price} 円</p><p><a href='/history'>戻る</a></p>"

######################################
# 補助関数：削除済みデータのクリーンアップ
######################################
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
# メイン
######################################
if __name__ == '__main__':
    app.run(debug=True)
