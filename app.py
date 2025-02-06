from flask import Flask, request, session, render_template, url_for, redirect, jsonify
import os
import json
from flask_mail import Mail, Message
from passlib.hash import bcrypt_sha256
from datetime import datetime
from auth import auth as auth_blueprint
from estimate import estimate_blueprint

# DB接続用 (PyMySQL) ※環境に合わせて実装してください
from db import get_connection

######################################
# 定数・係数一覧（一括管理）
######################################

# 原材料関連
DOHDAI_COEFFICIENT = 0.042          # 土代係数
DRYING_FUEL_COEFFICIENT = 0.025     # 乾燥燃料係数
BISQUE_FUEL_COEFFICIENT = 0.04      # 素焼き燃料係数
HASSUI_COEFFICIENT = 0.04           # 撥水剤係数
PAINT_COEFFICIENT = 0.05            # 絵具係数
FIRING_GAS_CONSTANT = 370           # 本焼きガス計算時の定数
MOLD_DIVISOR = 100                  # 型代計算用の割り係数

# 製造原価（例: ダミーの人件費・加工費など）
DUMMY_MANUFACTURING_COSTS = {
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

# 販売管理費（例: ダミーの人件費など）
DUMMY_SALES_COSTS = {
    'nouhin_jinkenhi': 500,
    'gasoline': 300
}

YIELD_COEFFICIENT = 0.95  # 歩留まり係数（仮）

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

# Blueprint の登録（必要に応じて URL のプレフィックスを設定可能）
app.register_blueprint(auth_blueprint, url_prefix='')
app.register_blueprint(estimate_blueprint, url_prefix='')


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
    total_cost = (
        sales_price + order_quantity + product_weight +
        mold_unit_price + mold_count + kiln_count +
        gas_unit_price + loss_defective
    )

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
        raw_material_cost_total += product_weight * DOHDAI_COEFFICIENT * order_quantity

    # 型代
    if include_kata:
        if mold_count > 0:
            raw_material_cost_total += (mold_unit_price / mold_count) / MOLD_DIVISOR * order_quantity
        else:
            return "使用型の数出し数が0です。"

    # 乾燥燃料費
    if include_drying_fuel:
        raw_material_cost_total += product_weight * DRYING_FUEL_COEFFICIENT * order_quantity

    # 素焼き燃料費
    if include_bisque_fuel:
        raw_material_cost_total += product_weight * BISQUE_FUEL_COEFFICIENT * order_quantity

    # 撥水剤
    if include_hassui:
        raw_material_cost_total += product_weight * HASSUI_COEFFICIENT * order_quantity

    # 絵具代
    if include_paint:
        raw_material_cost_total += product_weight * PAINT_COEFFICIENT * order_quantity

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
            raw_material_cost_total += (gas_unit_price * FIRING_GAS_CONSTANT) / kiln_count * order_quantity
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

    manufacturing_cost_total = 0
    if include_chumikin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['chumikin']
    if include_shiagechin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['shiagechin']
    if include_haiimonochin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['haiimonochin']
    if include_soyakeire_dashi:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['soyakeire_dashi']
    if include_soyakebarimono:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['soyakebarimono']
    if include_doban_hari:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['doban_hari']
    if include_hassui_kakouchin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['hassui_kakouchin']
    if include_etsukechin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['etsukechin']
    if include_shiyu_hiyou:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['shiyu_hiyou']
    if include_kamairi:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['kamairi']
    if include_kamadashi:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['kamadashi']
    if include_hamasuri:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['hamasuri']
    if include_kenpin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['kenpin']
    if include_print_kakouchin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['print_kakouchin']

    manufacturing_cost_ratio = (
        (manufacturing_cost_total / total_cost * 100)
        if total_cost > 0 else 0
    )

    # ----- 販売管理費の on/off 項目処理 -----
    include_nouhin_jinkenhi = request.form.get('include_nouhin_jinkenhi')
    include_gasoline        = request.form.get('include_gasoline')

    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += DUMMY_SALES_COSTS['nouhin_jinkenhi']
    if include_gasoline:
        sales_admin_cost_total += DUMMY_SALES_COSTS['gasoline']

    sales_admin_cost_ratio = (
        (sales_admin_cost_total / total_cost * 100)
        if total_cost > 0 else 0
    )

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
        # 材料費原価
        "raw_material_cost_total": raw_material_cost_total,
        "raw_material_cost_ratio": raw_material_cost_ratio,
        # 製造販管費
        "manufacturing_cost_total": manufacturing_cost_total,
        "manufacturing_cost_ratio": manufacturing_cost_ratio,
        "yield_coefficient": YIELD_COEFFICIENT,
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
                # cleanup_deleted が別途定義されている想定
                cleanup_deleted(user_id, cursor)

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
# （こちらも同様に係数を定数化）
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
    total_cost = (
        sales_price + order_quantity + product_weight +
        mold_unit_price + mold_count + kiln_count +
        gas_unit_price + loss_defective
    )

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
        raw_material_cost_total += product_weight * DOHDAI_COEFFICIENT * order_quantity

    if include_kata:
        if mold_count > 0:
            raw_material_cost_total += (mold_unit_price / mold_count) / MOLD_DIVISOR * order_quantity
        else:
            return jsonify({"error": "入力項目が不十分です"}), 400

    if include_drying_fuel:
        raw_material_cost_total += product_weight * DRYING_FUEL_COEFFICIENT * order_quantity

    if include_bisque_fuel:
        raw_material_cost_total += product_weight * BISQUE_FUEL_COEFFICIENT * order_quantity

    if include_hassui:
        raw_material_cost_total += product_weight * HASSUI_COEFFICIENT * order_quantity

    if include_paint:
        raw_material_cost_total += product_weight * PAINT_COEFFICIENT * order_quantity

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
            raw_material_cost_total += (gas_unit_price * FIRING_GAS_CONSTANT) / kiln_count * order_quantity
        else:
            return jsonify({"error": "入力項目が不十分です"}), 400

    if include_transfer_sheet:
        try:
            transfer_sheet_unit_price = float(request.form.get('transfer_sheet_unit_price', '0'))
        except Exception:
            return jsonify({"error": "入力項目が不十分です"}), 400
        raw_material_cost_total += transfer_sheet_unit_price * order_quantity

    raw_material_cost_ratio = (
        (sales_price / raw_material_cost_total)
        if raw_material_cost_total > 0 else 0
    )

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

    manufacturing_cost_total = 0
    if include_chumikin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['chumikin']
    if include_shiagechin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['shiagechin']
    if include_haiimonochin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['haiimonochin']
    if include_soyakeire_dashi:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['soyakeire_dashi']
    if include_soyakebarimono:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['soyakebarimono']
    if include_doban_hari:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['doban_hari']
    if include_hassui_kakouchin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['hassui_kakouchin']
    if include_etsukechin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['etsukechin']
    if include_shiyu_hiyou:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['shiyu_hiyou']
    if include_kamairi:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['kamairi']
    if include_kamadashi:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['kamadashi']
    if include_hamasuri:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['hamasuri']
    if include_kenpin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['kenpin']
    if include_print_kakouchin:
        manufacturing_cost_total += DUMMY_MANUFACTURING_COSTS['print_kakouchin']

    manufacturing_cost_ratio = (
        (manufacturing_cost_total / total_cost * 100)
        if total_cost > 0 else 0
    )

    # ----- 販売管理費の on/off 項目処理 -----
    include_nouhin_jinkenhi = request.form.get('include_nouhin_jinkenhi')
    include_gasoline        = request.form.get('include_gasoline')

    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += DUMMY_SALES_COSTS['nouhin_jinkenhi']
    if include_gasoline:
        sales_admin_cost_total += DUMMY_SALES_COSTS['gasoline']

    sales_admin_cost_ratio = (
        (sales_admin_cost_total / total_cost * 100)
        if total_cost > 0 else 0
    )

    # ----- 全体出力項目の算出 -----
    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total
    profit_amount = total_cost - production_plus_sales
    profit_ratio  = (
        (profit_amount / total_cost * 100)
        if total_cost > 0 else 0
    )

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
        "yield_coefficient": YIELD_COEFFICIENT,
        "sales_admin_cost_total": sales_admin_cost_total,
        "sales_admin_cost_ratio": sales_admin_cost_ratio,
        "production_cost_total": production_cost_total,
        "production_plus_sales": production_plus_sales,
        "profit_amount": profit_amount,
        "profit_ratio": profit_ratio
    }
    return jsonify(dashboard_data)

######################################
# メイン
######################################
if __name__ == '__main__':
    app.run(debug=True)
