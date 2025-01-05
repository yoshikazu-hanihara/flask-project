# mitumori.py
from flask import Flask, request, session, render_template_string, url_for, redirect
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

# Flask-Mail の設定例 (Gmail)
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
    factor_min = 1.1
    factor_max = 6.0
    if q < 1: q = 1
    if q > 20000: q = 20000
    exponent = (q - 1) / (20000 - 1)
    return factor_max * ((factor_min / factor_max) ** exponent)

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
GOLD_PLATINUM_FACTOR = 3.0  # 金・プラチナ3倍

GLAZE_UNIT_PRICE = 2.0  # 円/cm²

######################################
# ユーザ関連 (ログイン, 新規登録, etc.)
######################################
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'GET':
        html = '''
        <h2>ログイン</h2>
        <form method="post">
          <label>Email:</label>
          <input type="email" name="email"><br><br>
          <label>パスワード:</label>
          <input type="password" name="password"><br><br>
          <input type="submit" value="ログイン">
        </form>
        <p><a href="/register">新規登録はこちら</a></p>
        <hr>
        <p><a href="/guest_estimate">ログインせずに見積り作成</a><br>
        <small>※ゲストモードでは履歴は保存されません</small></p>
        '''
        return render_template_string(html)
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
            return redirect(url_for('upload_form'))
        else:
            return "ログイン失敗: メールアドレスまたはパスワードが違います。"

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'GET':
        return '''
        <h2>新規登録</h2>
        <form method="post">
          <label>Email:</label>
          <input type="email" name="email" required><br><br>
          <label>パスワード:</label>
          <input type="password" name="password" required><br><br>
          <input type="submit" value="登録">
        </form>
        <p><a href="/login">ログイン画面へ</a></p>
        '''
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
    session.clear()
    session['guest_mode'] = True
    return redirect(url_for('upload_form'))

######################################
# 見積もりメインページ (ページ1)
######################################
@app.route('/upload')
def upload_form():
    html = '''
    <h2>STLファイル アップロード & 生産数入力</h2>
    <p>最新の見積もりから３つまで比較検討できます。<br>
       ※一気に送信された場合のサーバー負荷対策のため</p>
    <form action="/upload_post" method="post" enctype="multipart/form-data">
      <label>STLファイル:</label><br>
      <input type="file" name="file"><br><br>
      <label>生産数 (1~20000):</label><br>
      <input type="number" name="quantity" value="1" min="1" max="20000"><br><br>
      <input type="submit" value="解析する">
    </form>
    <hr>
    '''
    if 'user_id' in session:
        html += "<p><a href='/history'>見積もり一覧</a> | <a href='/logout'>ログアウト</a></p>"
    else:
        html += "<p><a href='/login'>ログイン</a> (ゲストモード)</p>"
    return render_template_string(html)

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

    temp_path = os.path.join("temp", stl_file.filename)
    stl_file.save(temp_path)

    # STL解析
    stl_mesh = mesh.Mesh.from_file(temp_path)
    volume = float(stl_mesh.get_mass_properties()[0])   # 体積
    surface_area = float(stl_mesh.areas.sum())          # 表面積
    weight = volume * CERAMIC_DENSITY                   # g

    # 数量係数
    quantity_factor = calc_quantity_factor(quantity)
    total_ceramic = int(weight * CERAMIC_PRICE_PER_GRAM * quantity_factor * quantity)

    estimate_id = None
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_connection()
        with conn.cursor() as cursor:
            # activeが3件あれば最古をdeletedに
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

            estimate_data = {
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

    session['temp_path'] = temp_path
    session['estimate_id'] = estimate_id
    session['volume'] = volume
    session['surface_area'] = surface_area
    session['weight'] = weight
    session['quantity'] = quantity
    session['ceramic_price'] = total_ceramic

    html = f"""
    <h2>解析結果</h2>
    <p>体積: {int(volume)} cm³<br>
       重量: {int(weight)} g<br>
       生産数: {quantity} 個</p>
    <p>セラミック価格(約): {total_ceramic} 円</p>
    <form action="/choose_options" method="get">
      <input type="submit" value="次へ (オプション選択)">
    </form>
    """
    if 'user_id' in session:
        html += "<hr><a href='/history'>見積もり一覧</a> | <a href='/logout'>ログアウト</a>"
    else:
        html += "<hr><a href='/login'>ログイン</a> (ゲストモード)"
    return render_template_string(html)

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
        html = '''
        <h2>オプション選択</h2>
        <form action="/choose_options" method="post">
          <fieldset>
            <legend>施釉 (釉薬)</legend>
            <label><input type="radio" name="glaze_color" value="none" checked>施釉なし(素地)</label><br>
            <label><input type="radio" name="glaze_color" value="1">1色</label><br>
            <label><input type="radio" name="glaze_color" value="2">2色</label><br>
            <label><input type="radio" name="glaze_color" value="3">3色</label><br>
          </fieldset><br>

          <fieldset>
            <legend>プリント加工</legend>
            <p>サイズ:</p>
            <label><input type="radio" name="print_size" value="none" checked>なし</label><br>
            <label><input type="radio" name="print_size" value="S">S(3000円)</label><br>
            <label><input type="radio" name="print_size" value="M">M(9000円)</label><br>
            <label><input type="radio" name="print_size" value="L">L(15000円)</label><br>

            <p>プリント色数:</p>
            <label><input type="radio" name="print_color" value="none" checked>色なし</label><br>
            <label><input type="radio" name="print_color" value="1">1色(10000円)</label><br>
            <label><input type="radio" name="print_color" value="2">2色(15000円)</label><br>
            <label><input type="radio" name="print_color" value="3">3色(20000円)</label><br>
          </fieldset><br>

          <fieldset>
            <legend>特殊加工 (ばかし / グラデ / 金・プラチナ加飾等)</legend>
            <label><input type="radio" name="special_size" value="none" checked>なし</label><br>
            <label><input type="radio" name="special_size" value="small">小(3000円)</label><br>
            <label><input type="radio" name="special_size" value="medium">中(6000円)</label><br>
            <label><input type="radio" name="special_size" value="large">大(9000円)</label><br><br>
            <label><input type="checkbox" name="special_gold" value="yes">金・プラチナを希望する(+3倍)</label><br>
          </fieldset><br>

          <input type="submit" value="計算して次へ(お問い合わせフォーム)">
        </form>
        '''
        return render_template_string(html)
    else:
        glaze_color = request.form.get('glaze_color', 'none')
        print_size = request.form.get('print_size', 'none')
        print_color = request.form.get('print_color', 'none')
        special_size = request.form.get('special_size', 'none')
        special_gold = request.form.get('special_gold')  # 'yes' or None

        base_ceramic = session.get('ceramic_price', 0)
        quantity_factor = calc_quantity_factor(session.get('quantity',1))
        surface_area = session.get('surface_area', 0.0)

        # 1) 施釉
        if glaze_color == 'none':
            cost_glaze = 0
        else:
            color_count = float(glaze_color)
            base_glaze = surface_area * GLAZE_UNIT_PRICE * color_count
            cost_glaze = int(base_glaze * quantity_factor)

        # 2) プリント
        base_print_size = PRINT_SIZE_MAP.get(print_size, 0)
        base_print_color = PRINT_COLOR_MAP.get(print_color, 0)
        cost_print = int((base_print_size + base_print_color) * quantity_factor)

        # 3) 特殊加工
        base_special = SPECIAL_SIZE_MAP.get(special_size, 0)
        cost_special = base_special * quantity_factor
        if special_gold == 'yes':
            cost_special += base_special * GOLD_PLATINUM_FACTOR * quantity_factor
        cost_special = int(cost_special)

        final_total = base_ceramic + cost_glaze + cost_print + cost_special
        session['cost_glaze'] = cost_glaze
        session['cost_print'] = cost_print
        session['cost_special'] = cost_special
        session['final_total'] = final_total

        # ▼▼▼ ここでDBに反映（最小限の追加） ▼▼▼
        user_id = session.get('user_id')
        estimate_id = session.get('estimate_id')
        if user_id and estimate_id:
            conn = get_connection()
            with conn.cursor() as cursor:
                # 既存の estimate_data を取得
                cursor.execute("""
                  SELECT estimate_data
                    FROM estimates
                   WHERE id=%s AND user_id=%s
                """, (estimate_id, user_id))
                row = cursor.fetchone()
                if row:
                    old_data = json.loads(row['estimate_data'])
                    # 内訳を追加
                    old_data['cost_glaze'] = cost_glaze
                    old_data['cost_print'] = cost_print
                    old_data['cost_special'] = cost_special
                    old_data['final_total'] = final_total

                    # DB更新
                    cursor.execute("""
                      UPDATE estimates
                         SET estimate_data=%s
                       WHERE id=%s AND user_id=%s
                    """, (json.dumps(old_data), estimate_id, user_id))
            conn.commit()
            conn.close()
        # ▲▲▲ DB更新ここまで ▲▲▲

        return redirect(url_for('final_contact'))

######################################
# (ページ3) final_contact
######################################
@app.route('/final_contact', methods=['GET','POST'])
def final_contact():
    if request.method == 'GET':
        final_total = session.get('final_total', 0)
        cost_glaze = session.get('cost_glaze', 0)
        cost_print = session.get('cost_print', 0)
        cost_special = session.get('cost_special', 0)

        html = f"""
        <h2>お問い合わせフォーム</h2>
        <p>以下の内容でよろしければ送信してください。</p>
        <p>施釉: 約 {cost_glaze} 円<br>
           プリント: 約 {cost_print} 円<br>
           特殊加工: 約 {cost_special} 円<br>
           <b>最終合計(約): {final_total} 円</b></p>
        <form method="post">
          <label>お名前:</label><br>
          <input type="text" name="name" required><br><br>
          <label>企業名(任意):</label><br>
          <input type="text" name="company"><br><br>
          <label>メールアドレス:</label><br>
          <input type="email" name="email" required><br><br>
          <input type="submit" value="送信">
        </form>
        <hr>
        <a href="/upload">戻る</a>
        """
        return render_template_string(html)
    else:
        name = request.form.get('name')
        company = request.form.get('company','')
        email = request.form.get('email')
        final_total = session.get('final_total', 0)

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

        temp_path = session.get('temp_path')
        if temp_path and os.path.exists(temp_path):
            with open(temp_path, 'rb') as f:
                msg.attach(
                    filename=os.path.basename(temp_path),
                    content_type="application/sla",
                    data=f.read()
                )

        mail.send(msg)

        # 後処理
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        for key in ['temp_path','estimate_id','volume','surface_area','weight',
                    'quantity','ceramic_price','cost_glaze','cost_print',
                    'cost_special','final_total']:
            session.pop(key, None)

        return """
        <h2>お問い合わせが送信されました。</h2>
        <p><a href="/upload">新しい見積もり</a> |
           <a href="/history">履歴</a> |
           <a href="/logout">ログアウト</a></p>
        """

######################################
# 履歴画面 (ログイン専用)
######################################
@app.route('/history')
def history():
    if 'user_id' not in session:
        return "ログインしていません。<br><a href='/login'>ログイン画面</a>"

    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
          SELECT id, estimate_data, created_at 
            FROM estimates
           WHERE user_id=%s AND status='active'
           ORDER BY created_at DESC
        """, (user_id,))
        active_list = cursor.fetchall()

        cursor.execute("""
          SELECT id, estimate_data, created_at, deleted_at
            FROM estimates
           WHERE user_id=%s AND status='deleted'
           ORDER BY deleted_at DESC
        """, (user_id,))
        deleted_list = cursor.fetchall()

        cursor.execute("""
          SELECT id, estimate_data, created_at, sent_at
            FROM estimates
           WHERE user_id=%s AND status='sent'
           ORDER BY sent_at DESC
        """, (user_id,))
        sent_list = cursor.fetchall()
    conn.close()

    html = "<h2>見積もり一覧</h2>"

    # --- Active ---
    html += "<h3>アクティブ (送信可能) 最大3件</h3>"
    if not active_list:
        html += "<p>アクティブな見積もりはありません。</p>"
    else:
        for row in active_list:
            data = json.loads(row['estimate_data'])
            estid = row['id']
            created_str = row['created_at']

            # ここで内訳を取り出して表示（最小限の修正）
            ceramic_price = data.get('ceramic_price', 0)
            cost_glaze    = data.get('cost_glaze', 0)
            cost_print    = data.get('cost_print', 0)
            cost_special  = data.get('cost_special', 0)
            final_total   = data.get('final_total', 0)

            # カンマ区切りするなら f"{value:,}"
            ceramic_price_str = f"{ceramic_price:,}"
            cost_glaze_str    = f"{cost_glaze:,}"
            cost_print_str    = f"{cost_print:,}"
            cost_special_str  = f"{cost_special:,}"
            final_total_str   = f"{final_total:,}"

            html += f"""
            <div style='border:1px solid #ccc; margin:5px; padding:5px;'>
              <b>ID:</b> {estid}<br>
              作成日時: {created_str}<br><br>

              セラミック価格(約): {ceramic_price_str} 円<br>
              施釉(約): {cost_glaze_str} 円<br>
              プリント(約): {cost_print_str} 円<br>
              特殊加工(約): {cost_special_str} 円<br>
              <b>最終合計(約): {final_total_str} 円</b><br><br>

              <a href='/delete_estimate/{estid}'>この見積もりを削除</a>
            </div>
            """

    # --- Deleted ---
    html += """
    <h3 style="margin-top:30px;">削除済み見積もり (最大30)</h3>
    <p>31件目の削除済みが出ると、最も古い削除済み見積もりは完全に削除されます。</p>
    <button onclick="toggleDeleted()">削除済みを表示/非表示</button>
    <div id="deletedSection" style="display:none; border:1px solid #ccc; margin:5px; padding:5px;">
    """
    if not deleted_list:
        html += "<p>削除済みはありません。</p>"
    else:
        for row in deleted_list:
            data = json.loads(row['estimate_data'])
            estid = row['id']
            price = data.get('ceramic_price',0)
            dtime = row['deleted_at']
            html += f"<div style='border-bottom:1px solid #ddd; margin-bottom:5px;'>"
            html += f"<b>ID:</b> {estid} | <b>合計金額:</b> {price}円 | <b>削除日時:</b> {dtime}<br>"
            html += f"<a href='/pdf_only/{estid}'>PDFで確認</a>"
            html += "</div>"
    html += "</div>"
    html += """
    <script>
    function toggleDeleted(){
      var d = document.getElementById('deletedSection');
      d.style.display = (d.style.display=='none') ? 'block' : 'none';
    }
    </script>
    """

    # --- Sent ---
    html += "<h3 style='margin-top:30px;'>送信済み見積もり (新しい順)</h3>"
    if not sent_list:
        html += "<p>送信済みはありません。</p>"
    else:
        for row in sent_list:
            data = json.loads(row['estimate_data'])
            estid = row['id']
            price = data.get('ceramic_price',0)
            stime = row['sent_at']
            html += f"<div style='border:1px solid #ccc; margin:5px; padding:5px;'>"
            html += f"<b>ID:</b> {estid} | <b>価格:</b> {price}円 | <b>送信日時:</b> {stime}"
            html += "</div>"

    html += "<hr><p><a href='/upload'>新しい見積もり</a> | <a href='/logout'>ログアウト</a></p>"
    return render_template_string(html)

@app.route('/delete_estimate/<int:estid>')
def delete_estimate(estid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
          UPDATE estimates
             SET status='deleted', deleted_at=NOW()
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
        return "該当見積もりが見つかりません。"
    if row['status'] != 'deleted':
        return "これは削除済みではありません。"

    data = json.loads(row['estimate_data'])
    price = data.get('ceramic_price', 0)
    return f"""
    <h2>削除済み見積もり (PDFダミー表示)</h2>
    <p>合計金額: {price} 円</p>
    <p>ここで実際にPDFを返すか、詳細を表示する処理。</p>
    <p><a href="/history">戻る</a></p>
    """

if __name__ == '__main__':
    app.run(debug=True)
