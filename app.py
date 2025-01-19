# app.py
from flask import Flask, request, session, render_template, url_for, redirect
import os, json
from stl import mesh
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

# マッピングテーブル類
PRINT_SIZE_MAP = {
    'none': 0,
    'S': 3000,
    'M': 9000,
    'L': 15000
}
PRINT_COLOR_MAP = {
    'none': 0,
    '1': 10000,
    '2': 15000,
    '3': 20000
}
SPECIAL_SIZE_MAP = {
    'none': 0,
    'small': 3000,
    'medium': 6000,
    'large': 9000
}
GOLD_PLATINUM_FACTOR = 3.0
GLAZE_UNIT_PRICE = 2.0

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
# (ページ1) STLファイルアップロード
######################################
@app.route('/upload')
def upload_form():
    return render_template('upload.html')

@app.route('/upload_post', methods=['POST'])
def upload_post():
    stl_file = request.files.get('file')
    quantity_str = request.form.get('quantity','1')
    if not stl_file:
        return "STLファイルが選択されていません。"

    try:
        quantity = int(quantity_str)
    except:
        return "生産数が不正です。"

    # 一時保存
    temp_path = os.path.join("temp", stl_file.filename)
    stl_file.save(temp_path)

    # STL解析
    stl_mesh = mesh.Mesh.from_file(temp_path)
    volume = float(stl_mesh.get_mass_properties()[0])
    surface_area = float(stl_mesh.areas.sum())
    weight = volume * CERAMIC_DENSITY
    quantity_factor = calc_quantity_factor(quantity)
    total_ceramic = int(weight * CERAMIC_PRICE_PER_GRAM * quantity_factor * quantity)

    # ログインユーザならDBに登録
    estimate_id = None
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_connection()
        with conn.cursor() as cursor:
            # active が3件あれば最古を削除状態に
            cursor.execute("SELECT COUNT(*) as cnt FROM estimates WHERE user_id=%s AND status='active'", (user_id,))
            active_count = cursor.fetchone()['cnt']
            if active_count >= 3:
                cursor.execute("""
                  SELECT id FROM estimates
                   WHERE user_id=%s AND status='active'
                   ORDER BY created_at ASC LIMIT 1
                """, (user_id,))
                oldest_id = cursor.fetchone()['id']
                cursor.execute("UPDATE estimates SET status='deleted', deleted_at=NOW() WHERE id=%s",(oldest_id,))
                _cleanup_deleted(user_id, cursor)

            # 新規insert
            estimate_data = {
                "filename": stl_file.filename,
                "volume": volume,
                "surface_area": surface_area,
                "weight": weight,
                "quantity": quantity,
                "ceramic_price": total_ceramic
            }
            sql = """
              INSERT INTO estimates (user_id, estimate_data, status, sent_at, deleted_at)
              VALUES (%s, %s, 'active', NULL, NULL)
            """
            cursor.execute(sql, (user_id, json.dumps(estimate_data)))
            estimate_id = cursor.lastrowid
        conn.commit()
        conn.close()

    # セッションにも保存
    session['filename'] = stl_file.filename
    session['temp_path'] = temp_path
    session['estimate_id'] = estimate_id
    session['volume'] = volume
    session['surface_area'] = surface_area
    session['weight'] = weight
    session['quantity'] = quantity
    session['ceramic_price'] = total_ceramic

    # 次画面で表示するために
    return render_template(
        'upload_result.html',
        volume=int(volume),
        weight=int(weight),
        quantity=quantity,
        total_ceramic=total_ceramic
    )

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
# (ページ2) オプション選択
######################################
@app.route('/choose_options', methods=['GET','POST'])
def choose_options():
    if request.method == 'GET':
        return render_template('options.html')
    else:
        glaze_color = request.form.get('glaze_color','none')
        print_size = request.form.get('print_size','none')
        print_color = request.form.get('print_color','none')
        special_size = request.form.get('special_size','none')
        special_gold = request.form.get('special_gold')

        base_ceramic = session.get('ceramic_price', 0)
        quantity_factor = calc_quantity_factor(session.get('quantity',1))
        surface_area = session.get('surface_area', 0.0)

        # 施釉
        if glaze_color == 'none':
            cost_glaze = 0
        else:
            color_count = float(glaze_color)
            base_glaze = surface_area * GLAZE_UNIT_PRICE * color_count
            cost_glaze = int(base_glaze * quantity_factor)

        # プリント
        base_print_size = PRINT_SIZE_MAP.get(print_size, 0)
        base_print_color = PRINT_COLOR_MAP.get(print_color, 0)
        cost_print = int((base_print_size + base_print_color) * quantity_factor)

        # 特殊加工
        base_special = SPECIAL_SIZE_MAP.get(special_size, 0)
        cost_special = base_special * quantity_factor
        if special_gold == 'yes':
            cost_special += base_special * GOLD_PLATINUM_FACTOR * quantity_factor
        cost_special = int(cost_special)

        final_total = base_ceramic + cost_glaze + cost_print + cost_special

        # セッションへ
        session['cost_glaze'] = cost_glaze
        session['cost_print'] = cost_print
        session['cost_special'] = cost_special
        session['final_total'] = final_total

        # DBにも反映
        user_id = session.get('user_id')
        estimate_id = session.get('estimate_id')
        if user_id and estimate_id:
            conn = get_connection()
            with conn.cursor() as cursor:
                # 既存データにオプション計算を追加
                cursor.execute("SELECT estimate_data FROM estimates WHERE id=%s AND user_id=%s",(estimate_id, user_id))
                row = cursor.fetchone()
                if row:
                    old_data = json.loads(row['estimate_data'])
                    old_data['cost_glaze'] = cost_glaze
                    old_data['cost_print'] = cost_print
                    old_data['cost_special'] = cost_special
                    old_data['final_total'] = final_total
                    cursor.execute("""
                      UPDATE estimates SET estimate_data=%s
                        WHERE id=%s AND user_id=%s
                    """,(json.dumps(old_data), estimate_id, user_id))
            conn.commit()
            conn.close()

        return redirect(url_for('final_contact'))

######################################
# (ページ3) final_contact
######################################
@app.route('/final_contact', methods=['GET','POST'])
def final_contact():
    if request.method == 'GET':
        return render_template(
            'final_contact.html',
            final_total=session.get('final_total', 0),
            cost_glaze=session.get('cost_glaze', 0),
            cost_print=session.get('cost_print', 0),
            cost_special=session.get('cost_special', 0)
        )
    else:
        name = request.form.get('name')
        company = request.form.get('company','')
        email = request.form.get('email')
        final_total = session.get('final_total', 0)

        # DB更新
        user_id = session.get('user_id')
        estimate_id = session.get('estimate_id')
        if user_id and estimate_id:
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                  UPDATE estimates
                     SET status='sent', sent_at=NOW()
                   WHERE id=%s AND user_id=%s
                """,(estimate_id, user_id))
            conn.commit()
            conn.close()

        # メール送信
        cost_glaze = session.get('cost_glaze', 0)
        cost_print = session.get('cost_print', 0)
        cost_special = session.get('cost_special', 0)

        body_text = f"""
お名前: {name}
企業名: {company}
メールアドレス: {email}

施釉(約): {cost_glaze} 円
プリント(約): {cost_print} 円
特殊加工(約): {cost_special} 円
最終合計(約): {final_total} 円
"""
        msg = Message("見積もりお問い合わせ", recipients=["nworks12345@gmail.com"])
        msg.body = body_text

        # STLファイル添付
        temp_path = session.get('temp_path')
        if temp_path and os.path.exists(temp_path):
            with open(temp_path, 'rb') as f:
                msg.attach(
                    filename=os.path.basename(temp_path),
                    content_type="application/sla",
                    data=f.read()
                )
        mail.send(msg)

        # 後始末
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        for key in [
            'temp_path','estimate_id','volume','surface_area',
            'weight','quantity','ceramic_price','cost_glaze',
            'cost_print','cost_special','final_total'
        ]:
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
        """,(user_id,))
        active_list = cursor.fetchall()
        for row in active_list:
            row['estimate_data'] = json.loads(row['estimate_data'])

        # deleted
        cursor.execute("""
          SELECT id, estimate_data, created_at, deleted_at
            FROM estimates
           WHERE user_id=%s AND status='deleted'
           ORDER BY deleted_at DESC
        """,(user_id,))
        deleted_list = cursor.fetchall()
        for row in deleted_list:
            row['estimate_data'] = json.loads(row['estimate_data'])

        # sent
        cursor.execute("""
          SELECT id, estimate_data, created_at, sent_at
            FROM estimates
           WHERE user_id=%s AND status='sent'
           ORDER BY sent_at DESC
        """,(user_id,))
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
#「履歴でアクティブな見積もりを選ぶ」→「send_estimate を経由してセッションに再セット」→「既存の final_contact 画面へ」
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
    session['ceramic_price'] = data.get('ceramic_price', 0)
    session['cost_glaze']   = data.get('cost_glaze', 0)
    session['cost_print']   = data.get('cost_print', 0)
    session['cost_special'] = data.get('cost_special', 0)
    session['final_total']  = data.get('final_total', 0)

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
        """,(estid, user_id))
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
        """,(estid, user_id))
        row = cursor.fetchone()
    conn.close()

    if not row:
        return "見積もりが見つかりません。"
    if row['status'] != 'deleted':
        return "これは削除済みではありません。"

    data = json.loads(row['estimate_data'])
    price = data.get('ceramic_price', 0)
    return f"<h2>削除済み見積もり (PDFダミー)</h2><p>合計金額: {price} 円</p><p><a href='/history'>戻る</a></p>"

######################################
# メイン
######################################
if __name__ == '__main__':
    app.run(debug=True)
