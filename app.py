from flask import Flask, request, session, render_template, url_for, redirect, jsonify
import os
import json
from flask_mail import Mail, Message
from passlib.hash import bcrypt_sha256
from datetime import datetime

# DB接続用 (PyMySQL) ※環境に合わせて実装してください
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
    except Exception:
        return value

# Flask-Mail の設定 (Gmail例)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nworks12345@gmail.com'
app.config['MAIL_PASSWORD'] = 'yspr vktd yrmc wntn'
app.config['MAIL_DEFAULT_SENDER'] = 'nworks12345@gmail.com'
mail = Mail(app)

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
        except Exception:
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
        # 上部の数値入力項目
        sales_price     = float(request.form.get('sales_price'))
        order_quantity  = int(request.form.get('order_quantity'))
        product_weight  = float(request.form.get('product_weight'))
        mold_unit_price = float(request.form.get('mold_unit_price'))
        mold_count      = int(request.form.get('mold_count'))
        glaze_cost      = float(request.form.get('glaze_cost'))
        poly_count      = int(request.form.get('poly_count'))
        kiln_count      = int(request.form.get('kiln_count'))
        gas_unit_price  = float(request.form.get('gas_unit_price'))
        loss_defective  = float(request.form.get('loss_defective'))
    except Exception as e:
        return "入力値が不正です: " + str(e)

    # ダミー計算例：各基本項目の数値を単純に合計して最終合計 (total_cost) とする
    total_cost = (sales_price + order_quantity + product_weight +
                  mold_unit_price + mold_count + kiln_count +
                  gas_unit_price + loss_defective)

    # ----- 材料費原価の on/off 項目処理 -----
    include_dohdai          = request.form.get('include_dohdai')
    include_kata            = request.form.get('include_kata')
    include_drying_fuel     = request.form.get('include_drying_fuel')
    include_bisque_fuel     = request.form.get('include_bisque_fuel')
    include_hassui          = request.form.get('include_hassui')
    include_paint           = request.form.get('include_paint')
    include_logo_copper     = request.form.get('include_logo_copper')
    include_glaze_material  = request.form.get('include_glaze_material')
    include_main_firing_gas = request.form.get('include_main_firing_gas')
    include_transfer_sheet  = request.form.get('include_transfer_sheet')

    raw_material_cost_total = 0

    # 土代
    if include_dohdai:
        raw_material_cost_total += product_weight * 0.042 * order_quantity

    # 型代
    if include_kata:
        if mold_count > 0:
            raw_material_cost_total += (mold_unit_price / mold_count) / 100 * order_quantity
        else:
            return "使用型の数出し数が0です。"

    # 乾燥燃料費
    if include_drying_fuel:
        raw_material_cost_total += product_weight * 0.025 * order_quantity

    # 素焼き燃料費
    if include_bisque_fuel:
        raw_material_cost_total += product_weight * 0.04 * order_quantity

    # 撥水剤
    if include_hassui:
        raw_material_cost_total += product_weight * 0.04 * order_quantity

    # 絵具代
    if include_paint:
        raw_material_cost_total += product_weight * 0.05 * order_quantity

    # ロゴ 銅板代
    if include_logo_copper:
        try:
            copper_unit_price = float(request.form.get('copper_unit_price', '0'))
        except Exception as e:
            return "銅板の単価が不正です: " + str(e)
        raw_material_cost_total += copper_unit_price * order_quantity

    # 釉薬代
    if include_glaze_material:
        if poly_count > 0:
            raw_material_cost_total += (glaze_cost / poly_count) * order_quantity
        else:
            return "ポリ1本で塗れる枚数が0です。"

    # 本焼成 ガス代
    if include_main_firing_gas:
        if kiln_count > 0:
            raw_material_cost_total += (gas_unit_price * 370) / kiln_count * order_quantity
        else:
            return "窯入数が0です。"

    # 転写シート代
    if include_transfer_sheet:
        try:
            transfer_sheet_unit_price = float(request.form.get('transfer_sheet_unit_price', '0'))
        except Exception as e:
            return "転写の単価が不正です: " + str(e)
        raw_material_cost_total += transfer_sheet_unit_price * order_quantity

    raw_material_cost_ratio = (sales_price / raw_material_cost_total) if raw_material_cost_total > 0 else 0

    # ----- 製造販管費の on/off 項目処理 -----
    include_chumikin         = request.form.get('include_chumikin')
    include_shiagechin       = request.form.get('include_shiagechin')
    include_haiimonochin     = request.form.get('include_haiimonochin')
    include_soyakeire_dashi  = request.form.get('include_soyakeire_dashi')
    include_soyakebarimono   = request.form.get('include_soyakebarimono')
    include_doban_hari       = request.form.get('include_doban_hari')
    include_hassui_kakouchin = request.form.get('include_hassui_kakouchin')
    include_etsukechin       = request.form.get('include_etsukechin')
    include_shiyu_hiyou      = request.form.get('include_shiyu_hiyou')
    include_kamairi          = request.form.get('include_kamairi')
    include_kamadashi        = request.form.get('include_kamadashi')
    include_hamasuri         = request.form.get('include_hamasuri')
    include_kenpin           = request.form.get('include_kenpin')
    include_print_kakouchin  = request.form.get('include_print_kakouchin')

    dummy_manufacturing_costs = {
        'chumikin': 120,
        'shiagechin': 150,
        'haiimonochin': 80,
        'soyakeire_dashi': 90,
        'soyakebarimono': 70,
        'doban_hari': 200,
        'hassui_kakouchin': 110,
        'etsukechin': 130,
        'shiyu_hiyou': 140,
        'kamairi': 160,
        'kamadashi': 170,
        'hamasuri': 100,
        'kenpin': 90,
        'print_kakouchin': 180
    }

    manufacturing_cost_total = 0
    if include_chumikin:
        manufacturing_cost_total += dummy_manufacturing_costs['chumikin']
    if include_shiagechin:
        manufacturing_cost_total += dummy_manufacturing_costs['shiagechin']
    if include_haiimonochin:
        manufacturing_cost_total += dummy_manufacturing_costs['haiimonochin']
    if include_soyakeire_dashi:
        manufacturing_cost_total += dummy_manufacturing_costs['soyakeire_dashi']
    if include_soyakebarimono:
        manufacturing_cost_total += dummy_manufacturing_costs['soyakebarimono']
    if include_doban_hari:
        manufacturing_cost_total += dummy_manufacturing_costs['doban_hari']
    if include_hassui_kakouchin:
        manufacturing_cost_total += dummy_manufacturing_costs['hassui_kakouchin']
    if include_etsukechin:
        manufacturing_cost_total += dummy_manufacturing_costs['etsukechin']
    if include_shiyu_hiyou:
        manufacturing_cost_total += dummy_manufacturing_costs['shiyu_hiyou']
    if include_kamairi:
        manufacturing_cost_total += dummy_manufacturing_costs['kamairi']
    if include_kamadashi:
        manufacturing_cost_total += dummy_manufacturing_costs['kamadashi']
    if include_hamasuri:
        manufacturing_cost_total += dummy_manufacturing_costs['hamasuri']
    if include_kenpin:
        manufacturing_cost_total += dummy_manufacturing_costs['kenpin']
    if include_print_kakouchin:
        manufacturing_cost_total += dummy_manufacturing_costs['print_kakouchin']

    yield_coefficient = 0.95
    manufacturing_cost_ratio = (manufacturing_cost_total / total_cost * 100) if total_cost > 0 else 0

    # ----- 販売管理費の on/off 項目処理 -----
    include_nouhin_jinkenhi = request.form.get('include_nouhin_jinkenhi')
    include_gasoline        = request.form.get('include_gasoline')

    dummy_sales_costs = {
        'nouhin_jinkenhi': 500,
        'gasoline': 300
    }

    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += dummy_sales_costs['nouhin_jinkenhi']
    if include_gasoline:
        sales_admin_cost_total += dummy_sales_costs['gasoline']

    sales_admin_cost_ratio = (sales_admin_cost_total / total_cost * 100) if total_cost > 0 else 0

    # ----- 全体出力項目の算出 -----
    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total
    profit_amount = total_cost - production_plus_sales
    profit_ratio  = (profit_amount / total_cost * 100) if total_cost > 0 else 0

    # 入力内容と各計算結果をまとめる
    dashboard_data = {
        "sales_price": sales_price,
        "order_quantity": order_quantity,
        "product_weight": product_weight,
        "mold_unit_price": mold_unit_price,
        "mold_count": mold_count,
        "kiln_count": kiln_count,
        "gas_unit_price": gas_unit_price,
        "loss_defective": loss_defective,
        "poly_count": poly_count,
        "glaze_cost": glaze_cost,
        "total_cost": total_cost,
        # 材料費原価
        "raw_material_cost_total": raw_material_cost_total,
        "raw_material_cost_ratio": raw_material_cost_ratio,
        # 製造販管費
        "manufacturing_cost_total": manufacturing_cost_total,
        "manufacturing_cost_ratio": manufacturing_cost_ratio,
        "yield_coefficient": yield_coefficient,
        # 販売管理費
        "sales_admin_cost_total": sales_admin_cost_total,
        "sales_admin_cost_ratio": sales_admin_cost_ratio,
        # 全体
        "production_cost_total": production_cost_total,
        "production_plus_sales": production_plus_sales,
        "profit_amount": profit_amount,
        "profit_ratio": profit_ratio
    }

    # ログインユーザならDBに登録（active見積もりは最大3件まで）
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

    session['dashboard_data'] = dashboard_data
    session['estimate_id'] = estimate_id

    return render_template('dashboard_result.html', dashboard_data=dashboard_data)

######################################
# 自動計算用のエンドポイント /calculate
######################################
@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        # 必須項目の取得
        sales_price     = float(request.form.get('sales_price', '').strip())
        order_quantity  = int(request.form.get('order_quantity', '').strip())
        product_weight  = float(request.form.get('product_weight', '').strip())
        mold_unit_price = float(request.form.get('mold_unit_price', '').strip())
        mold_count      = int(request.form.get('mold_count', '').strip())
        glaze_cost      = float(request.form.get('glaze_cost', '').strip())
        poly_count      = int(request.form.get('poly_count', '').strip())
        kiln_count      = int(request.form.get('kiln_count', '').strip())
        gas_unit_price  = float(request.form.get('gas_unit_price', '').strip())
        loss_defective  = float(request.form.get('loss_defective', '').strip())
    except Exception:
        return jsonify({"error": "入力項目が不十分です"}), 400

    # ダミー計算例
    total_cost = (sales_price + order_quantity + product_weight +
                  mold_unit_price + mold_count + kiln_count +
                  gas_unit_price + loss_defective)

    # ----- 材料費原価の on/off 項目処理 -----
    include_dohdai          = request.form.get('include_dohdai')
    include_kata            = request.form.get('include_kata')
    include_drying_fuel     = request.form.get('include_drying_fuel')
    include_bisque_fuel     = request.form.get('include_bisque_fuel')
    include_hassui          = request.form.get('include_hassui')
    include_paint           = request.form.get('include_paint')
    include_logo_copper     = request.form.get('include_logo_copper')
    include_glaze_material  = request.form.get('include_glaze_material')
    include_main_firing_gas = request.form.get('include_main_firing_gas')
    include_transfer_sheet  = request.form.get('include_transfer_sheet')

    raw_material_cost_total = 0

    if include_dohdai:
        raw_material_cost_total += product_weight * 0.042 * order_quantity

    if include_kata:
        if mold_count > 0:
            raw_material_cost_total += (mold_unit_price / mold_count) / 100 * order_quantity
        else:
            return jsonify({"error": "入力項目が不十分です"}), 400

    if include_drying_fuel:
        raw_material_cost_total += product_weight * 0.025 * order_quantity

    if include_bisque_fuel:
        raw_material_cost_total += product_weight * 0.04 * order_quantity

    if include_hassui:
        raw_material_cost_total += product_weight * 0.04 * order_quantity

    if include_paint:
        raw_material_cost_total += product_weight * 0.05 * order_quantity

    if include_logo_copper:
        try:
            copper_unit_price = float(request.form.get('copper_unit_price', '0'))
        except Exception:
            return jsonify({"error": "入力項目が不十分です"}), 400
        raw_material_cost_total += copper_unit_price * order_quantity

    if include_glaze_material:
        if poly_count > 0:
            raw_material_cost_total += (glaze_cost / poly_count) * order_quantity
        else:
            return jsonify({"error": "入力項目が不十分です"}), 400

    if include_main_firing_gas:
        if kiln_count > 0:
            raw_material_cost_total += (gas_unit_price * 370) / kiln_count * order_quantity
        else:
            return jsonify({"error": "入力項目が不十分です"}), 400

    if include_transfer_sheet:
        try:
            transfer_sheet_unit_price = float(request.form.get('transfer_sheet_unit_price', '0'))
        except Exception:
            return jsonify({"error": "入力項目が不十分です"}), 400
        raw_material_cost_total += transfer_sheet_unit_price * order_quantity

    raw_material_cost_ratio = (sales_price / raw_material_cost_total) if raw_material_cost_total > 0 else 0

    # ----- 製造販管費の on/off 項目処理 -----
    include_chumikin         = request.form.get('include_chumikin')
    include_shiagechin       = request.form.get('include_shiagechin')
    include_haiimonochin     = request.form.get('include_haiimonochin')
    include_soyakeire_dashi  = request.form.get('include_soyakeire_dashi')
    include_soyakebarimono   = request.form.get('include_soyakebarimono')
    include_doban_hari       = request.form.get('include_doban_hari')
    include_hassui_kakouchin = request.form.get('include_hassui_kakouchin')
    include_etsukechin       = request.form.get('include_etsukechin')
    include_shiyu_hiyou      = request.form.get('include_shiyu_hiyou')
    include_kamairi          = request.form.get('include_kamairi')
    include_kamadashi        = request.form.get('include_kamadashi')
    include_hamasuri         = request.form.get('include_hamasuri')
    include_kenpin           = request.form.get('include_kenpin')
    include_print_kakouchin  = request.form.get('include_print_kakouchin')

    dummy_manufacturing_costs = {
        'chumikin': 120,
        'shiagechin': 150,
        'haiimonochin': 80,
        'soyakeire_dashi': 90,
        'soyakebarimono': 70,
        'doban_hari': 200,
        'hassui_kakouchin': 110,
        'etsukechin': 130,
        'shiyu_hiyou': 140,
        'kamairi': 160,
        'kamadashi': 170,
        'hamasuri': 100,
        'kenpin': 90,
        'print_kakouchin': 180
    }

    manufacturing_cost_total = 0
    if include_chumikin:
        manufacturing_cost_total += dummy_manufacturing_costs['chumikin']
    if include_shiagechin:
        manufacturing_cost_total += dummy_manufacturing_costs['shiagechin']
    if include_haiimonochin:
        manufacturing_cost_total += dummy_manufacturing_costs['haiimonochin']
    if include_soyakeire_dashi:
        manufacturing_cost_total += dummy_manufacturing_costs['soyakeire_dashi']
    if include_soyakebarimono:
        manufacturing_cost_total += dummy_manufacturing_costs['soyakebarimono']
    if include_doban_hari:
        manufacturing_cost_total += dummy_manufacturing_costs['doban_hari']
    if include_hassui_kakouchin:
        manufacturing_cost_total += dummy_manufacturing_costs['hassui_kakouchin']
    if include_etsukechin:
        manufacturing_cost_total += dummy_manufacturing_costs['etsukechin']
    if include_shiyu_hiyou:
        manufacturing_cost_total += dummy_manufacturing_costs['shiyu_hiyou']
    if include_kamairi:
        manufacturing_cost_total += dummy_manufacturing_costs['kamairi']
    if include_kamadashi:
        manufacturing_cost_total += dummy_manufacturing_costs['kamadashi']
    if include_hamasuri:
        manufacturing_cost_total += dummy_manufacturing_costs['hamasuri']
    if include_kenpin:
        manufacturing_cost_total += dummy_manufacturing_costs['kenpin']
    if include_print_kakouchin:
        manufacturing_cost_total += dummy_manufacturing_costs['print_kakouchin']

    yield_coefficient = 0.95
    manufacturing_cost_ratio = (manufacturing_cost_total / total_cost * 100) if total_cost > 0 else 0

    # ----- 販売管理費の on/off 項目処理 -----
    include_nouhin_jinkenhi = request.form.get('include_nouhin_jinkenhi')
    include_gasoline        = request.form.get('include_gasoline')

    dummy_sales_costs = {
        'nouhin_jinkenhi': 500,
        'gasoline': 300
    }

    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += dummy_sales_costs['nouhin_jinkenhi']
    if include_gasoline:
        sales_admin_cost_total += dummy_sales_costs['gasoline']

    sales_admin_cost_ratio = (sales_admin_cost_total / total_cost * 100) if total_cost > 0 else 0

    # ----- 全体出力項目の算出 -----
    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total
    profit_amount = total_cost - production_plus_sales
    profit_ratio  = (profit_amount / total_cost * 100) if total_cost > 0 else 0

    dashboard_data = {
        "sales_price": sales_price,
        "order_quantity": order_quantity,
        "product_weight": product_weight,
        "mold_unit_price": mold_unit_price,
        "mold_count": mold_count,
        "kiln_count": kiln_count,
        "gas_unit_price": gas_unit_price,
        "loss_defective": loss_defective,
        "poly_count": poly_count,
        "glaze_cost": glaze_cost,
        "total_cost": total_cost,
        "raw_material_cost_total": raw_material_cost_total,
        "raw_material_cost_ratio": raw_material_cost_ratio,
        "manufacturing_cost_total": manufacturing_cost_total,
        "manufacturing_cost_ratio": manufacturing_cost_ratio,
        "yield_coefficient": yield_coefficient,
        "sales_admin_cost_total": sales_admin_cost_total,
        "sales_admin_cost_ratio": sales_admin_cost_ratio,
        "production_cost_total": production_cost_total,
        "production_plus_sales": production_plus_sales,
        "profit_amount": profit_amount,
        "profit_ratio": profit_ratio
    }
    return jsonify(dashboard_data)

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
        
        body_text = f"""
お名前: {name}
企業名: {company}
メールアドレス: {email}

【基本項目】
　売価: {dashboard_data.get('sales_price')}
　発注数: {dashboard_data.get('order_quantity')}
　製品重量: {dashboard_data.get('product_weight')}
　使用型単価: {dashboard_data.get('mold_unit_price')}
　使用型の数出し数: {dashboard_data.get('mold_count')}
  釉薬代: {dashboard_data.get('glaze_cost', 0)}
　ポリ1本で塗れる枚数: {dashboard_data.get('poly_count')}
　窯入数: {dashboard_data.get('kiln_count')}
　ガス単価: {dashboard_data.get('gas_unit_price')}
　ロス 不良: {dashboard_data.get('loss_defective')}
　最終合計: {total_cost}

【原材料費】
　原材料費合計: {dashboard_data.get('raw_material_cost_total')}
　原材料費原価率: {dashboard_data.get('raw_material_cost_ratio'):.2f}%

【製造販管費】
　歩留まり係数: {dashboard_data.get('yield_coefficient'):.2f}
　製造販管費合計: {dashboard_data.get('manufacturing_cost_total')}
　製造販管費原価率: {dashboard_data.get('manufacturing_cost_ratio'):.2f}%

【販売管理費】
　販売管理費合計: {dashboard_data.get('sales_admin_cost_total')}
　販売管理費率: {dashboard_data.get('sales_admin_cost_ratio'):.2f}%

【全体】
　製造原価＋販売管理費: {dashboard_data.get('production_plus_sales')}
　利益額: {dashboard_data.get('profit_amount')}
　利益率: {dashboard_data.get('profit_ratio'):.2f}%
"""
        msg = Message("見積もりお問い合わせ", recipients=["nworks12345@gmail.com"])
        msg.body = body_text
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
        cursor.execute("""
          SELECT id, estimate_data, created_at 
            FROM estimates
           WHERE user_id=%s AND status='active'
           ORDER BY created_at DESC
        """, (user_id,))
        active_list = cursor.fetchall()
        for row in active_list:
            row['estimate_data'] = json.loads(row['estimate_data'])

        cursor.execute("""
          SELECT id, estimate_data, created_at, deleted_at
            FROM estimates
           WHERE user_id=%s AND status='deleted'
           ORDER BY deleted_at DESC
        """, (user_id,))
        deleted_list = cursor.fetchall()
        for row in deleted_list:
            row['estimate_data'] = json.loads(row['estimate_data'])

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

######################################
# 「履歴でアクティブな見積もりを選ぶ」→「send_estimate を経由してセッションに再セット」→「既存の final_contact 画面へ」
######################################
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
