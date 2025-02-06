from flask import Flask, request, session, render_template, url_for, redirect, jsonify
import os
import json
from flask_mail import Mail, Message
from passlib.hash import bcrypt_sha256
from datetime import datetime

# Blueprint (別ファイル) の読み込み
from auth import auth as auth_blueprint
from estimate import estimate_blueprint

# DB接続用 (例: PyMySQL) ※環境に合わせて実装してください
from db import get_connection

######################################
# 定数・係数一覧（一括管理）
######################################

# --- 原材料関連 (旧来の定数) ---
DOHDAI_COEFFICIENT       = 0.042  # 土代係数
DRYING_FUEL_COEFFICIENT  = 0.025  # 乾燥燃料係数
BISQUE_FUEL_COEFFICIENT  = 0.04   # 素焼き燃料係数
HASSUI_COEFFICIENT       = 0.04   # 撥水剤係数
PAINT_COEFFICIENT        = 0.05   # 絵具係数
FIRING_GAS_CONSTANT      = 370    # 本焼きガス計算時の定数
MOLD_DIVISOR             = 100    # 型代計算用の割り係数

# --- 時給定数 ---
HOURLY_WAGE = 3000  # 時給3000円

######################################
# Flask基本設定
######################################
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッション用キー(例)

# Flask-Mail の設定 (例: Gmail)
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = 'nworks12345@gmail.com'
app.config['MAIL_PASSWORD'] = 'yspr vktd yrmc wntn'
app.config['MAIL_DEFAULT_SENDER'] = 'nworks12345@gmail.com'
mail = Mail(app)

# Blueprint の登録
app.register_blueprint(auth_blueprint, url_prefix='')
app.register_blueprint(estimate_blueprint, url_prefix='')

# カスタムフィルタ例: 3桁区切り
@app.template_filter('format_thousand')
def format_thousand(value):
    try:
        value = int(value)
        return f"{value:,}"
    except Exception:
        return value

######################################
# ダッシュボード表示
######################################
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

########################################
# ダッシュボードのPOST処理 (例)
########################################
@app.route('/dashboard_post', methods=['POST'])
def dashboard_post():
    """
      dashboard.html のフォーム送信時の処理 (例)
      /calculate の処理と同様にサーバーサイドで計算し、
      結果をテンプレートへ渡す。
    """
    try:
        # 必須の数値入力項目を取得
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

    # 単純な「合計コスト」のダミー計算
    total_cost = (
        sales_price + order_quantity + product_weight +
        mold_unit_price + mold_count + kiln_count +
        gas_unit_price + loss_defective
    )

    # ---------- 原材料費の on/off ------------
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

    # 各項目の金額変数を初期化
    dohdai_cost = 0
    kata_cost = 0
    drying_fuel_cost = 0
    bisque_fuel_cost = 0
    hassui_cost = 0
    paint_cost = 0
    logo_copper_cost = 0
    glaze_material_cost = 0
    main_firing_gas_cost = 0
    transfer_sheet_cost = 0

    # 土代
    if include_dohdai:
        dohdai_cost = product_weight * DOHDAI_COEFFICIENT * order_quantity

    # 型代
    if include_kata:
        if mold_count > 0:
            kata_cost = (mold_unit_price / mold_count) / MOLD_DIVISOR * order_quantity
        else:
            return "使用型の数出しが0です。"

    # 乾燥燃料費
    if include_drying_fuel:
        drying_fuel_cost = product_weight * DRYING_FUEL_COEFFICIENT * order_quantity

    # 素焼燃料費
    if include_bisque_fuel:
        bisque_fuel_cost = product_weight * BISQUE_FUEL_COEFFICIENT * order_quantity

    # 撥水剤
    if include_hassui:
        hassui_cost = product_weight * HASSUI_COEFFICIENT * order_quantity

    # 絵具代
    if include_paint:
        paint_cost = product_weight * PAINT_COEFFICIENT * order_quantity

    # ロゴ 銅板代 (ラジオボタン10,20,30円)
    if include_logo_copper:
        try:
            copper_unit_price = float(request.form.get('copper_unit_price', '0'))
        except Exception as e:
            return "銅板単価が不正です: " + str(e)
        logo_copper_cost = copper_unit_price * order_quantity

    # 釉薬代
    if include_glaze_material:
        if poly_count > 0:
            glaze_material_cost = (glaze_cost / poly_count) * order_quantity
        else:
            return "ポリ塗れる枚数が0です。"

    # 本焼成ガス代
    if include_main_firing_gas:
        if kiln_count > 0:
            main_firing_gas_cost = (gas_unit_price * FIRING_GAS_CONSTANT) / kiln_count * order_quantity
        else:
            return "窯入数が0です。"

    # 転写シート代 (ラジオボタン10,20,30円)
    if include_transfer_sheet:
        try:
            transfer_sheet_unit_price = float(request.form.get('transfer_sheet_unit_price', '0'))
        except Exception as e:
            return "転写シート単価が不正です: " + str(e)
        transfer_sheet_cost = transfer_sheet_unit_price * order_quantity

    # 原材料費合計
    raw_material_cost_total = (
        dohdai_cost + kata_cost + drying_fuel_cost + bisque_fuel_cost
        + hassui_cost + paint_cost + logo_copper_cost
        + glaze_material_cost + main_firing_gas_cost + transfer_sheet_cost
    )

    raw_material_cost_ratio = (sales_price / raw_material_cost_total) if raw_material_cost_total > 0 else 0

    # ---------- 製造販管費の on/off ------------
    include_chumikin         = request.form.get('include_chumikin')
    include_shiagechin       = request.form.get('include_shiagechin')
    include_haiimonochin     = request.form.get('include_haiimonochin')
    include_seisojiken       = request.form.get('include_seisojiken')        # 生素地検品
    include_soyakeire_dashi  = request.form.get('include_soyakeire_dashi')   # 素焼入れ/出し
    include_soyakebarimono   = request.form.get('include_soyakebarimono')    # 素焼払いもの
    include_doban_hari       = request.form.get('include_doban_hari')        # 銅版貼り
    include_hassui_kakouchin = request.form.get('include_hassui_kakouchin')  # 撥水加工賃
    include_shiyu_hiyou      = request.form.get('include_shiyu_hiyou')       # 絵付け賃
    include_shiyu_cost       = request.form.get('include_shiyu_cost')        # 施釉費
    include_kamairi          = request.form.get('include_kamairi')
    include_kamadashi        = request.form.get('include_kamadashi')
    include_hamasuri         = request.form.get('include_hamasuri')
    include_kenpin           = request.form.get('include_kenpin')
    include_print_kakouchin  = request.form.get('include_print_kakouchin')

    # 各項目の金額を0で初期化
    chumikin_cost = 0
    shiagechin_cost = 0
    haiimonochin_cost = 0
    seisojiken_cost = 0
    soyakeire_dashi_cost = 0
    soyakebarimono_cost = 0
    doban_hari_cost = 0
    hassui_kakouchin_cost = 0
    shiyu_hiyou_cost = 0   # (絵付け賃)
    shiyu_cost = 0         # (施釉費)
    kamairi_cost = 0
    kamadashi_cost = 0
    hamasuri_cost = 0
    kenpin_cost = 0
    print_kakouchin_cost = 0

    # 1. 鋳込み賃 (ラジオ 10,20,30円 × 個数)
    if include_chumikin:
        chumikin_unit = float(request.form.get('chumikin_unit', '0'))
        chumikin_cost = chumikin_unit * order_quantity

    # 2. 仕上げ賃 (ラジオ 10,20,30円 × 個数)
    if include_shiagechin:
        shiagechin_unit = float(request.form.get('shiagechin_unit', '0'))
        shiagechin_cost = shiagechin_unit * order_quantity

    # 3. 掃いもの賃 ⇒ (使用型単価 / 1時間あたりの作業量) × 個数
    if include_haiimonochin:
        sawaimono_work = float(request.form.get('sawaimono_work', '0'))
        if sawaimono_work > 0:
            haiimonochin_cost = (mold_unit_price / sawaimono_work) * order_quantity
        else:
            haiimonochin_cost = 0  # もしくはエラーreturn

    # 4. 生素地検品代 ⇒ (時給 / 1時間あたりの検品数) × 個数
    if include_seisojiken:
        seisojiken_work = float(request.form.get('seisojiken_work', '0'))
        if seisojiken_work > 0:
            seisojiken_cost = (HOURLY_WAGE / seisojiken_work) * order_quantity
        else:
            seisojiken_cost = 0

    # 5. 素焼入れ/出し ⇒ (時給 / 1時間あたりの作業量) × 個数
    if include_soyakeire_dashi:
        soyakeire_work = float(request.form.get('soyakeire_work', '0'))
        if soyakeire_work > 0:
            soyakeire_dashi_cost = (HOURLY_WAGE / soyakeire_work) * order_quantity
        else:
            soyakeire_dashi_cost = 0

    # 6. 素焼払いもの ⇒ (時給 / 1時間あたりの作業量) × 個数
    if include_soyakebarimono:
        soyakebarimono_work = float(request.form.get('soyakebarimono_work', '0'))
        if soyakebarimono_work > 0:
            soyakebarimono_cost = (HOURLY_WAGE / soyakebarimono_work) * order_quantity
        else:
            soyakebarimono_cost = 0

    # 7. 銅版貼り ⇒ (ラジオ10,20,30円) × 個数
    if include_doban_hari:
        doban_hari_unit = float(request.form.get('doban_hari_unit', '0'))
        doban_hari_cost = doban_hari_unit * order_quantity

    # 8. 撥水加工賃 ⇒ (時給 / 1時間あたりの作業量) × 個数
    if include_hassui_kakouchin:
        hassui_kakouchin_work = float(request.form.get('hassui_kakouchin_work', '0'))
        if hassui_kakouchin_work > 0:
            hassui_kakouchin_cost = (HOURLY_WAGE / hassui_kakouchin_work) * order_quantity
        else:
            hassui_kakouchin_cost = 0

    # 9. 絵付け賃 ⇒ (ラジオ10,20,30円) × 個数
    if include_shiyu_hiyou:
        shiyu_hiyou_unit = float(request.form.get('shiyu_hiyou_unit', '0'))
        shiyu_hiyou_cost = shiyu_hiyou_unit * order_quantity

    # 10. 施釉費 ⇒ (時給 / 1時間あたりの作業量) × 個数
    if include_shiyu_cost:
        shiyu_work = float(request.form.get('shiyu_work', '0'))
        if shiyu_work > 0:
            shiyu_cost = (HOURLY_WAGE / shiyu_work) * order_quantity
        else:
            shiyu_cost = 0

    # 11. 窯入れ作業費 ⇒ 時給3000円 * kamairi_time / 窯数 × 発注数 (例)
    if include_kamairi:
        kamairi_time = float(request.form.get('kamairi_time', '0'))
        if kiln_count > 0 and kamairi_time > 0:
            kamairi_cost = (HOURLY_WAGE * kamairi_time / kiln_count) * order_quantity

    # 12. 窯出し作業費
    if include_kamadashi:
        kamadashi_time = float(request.form.get('kamadashi_time', '0'))
        if kiln_count > 0 and kamadashi_time > 0:
            kamadashi_cost = (HOURLY_WAGE * kamadashi_time / kiln_count) * order_quantity

    # 13. ハマスリ
    if include_hamasuri:
        hamasuri_time = float(request.form.get('hamasuri_time', '0'))
        if kiln_count > 0 and hamasuri_time > 0:
            hamasuri_cost = (HOURLY_WAGE * hamasuri_time / kiln_count) * order_quantity

    # 14. 検品
    if include_kenpin:
        kenpin_time = float(request.form.get('kenpin_time', '0'))
        if kiln_count > 0 and kenpin_time > 0:
            kenpin_cost = (HOURLY_WAGE * kenpin_time / kiln_count) * order_quantity

    # 15. プリント加工賃
    if include_print_kakouchin:
        print_kakouchin_unit = float(request.form.get('print_kakouchin_unit', '0'))
        print_kakouchin_cost = print_kakouchin_unit * order_quantity

    # 製造販管費の合計
    manufacturing_cost_total = (
        chumikin_cost + shiagechin_cost + haiimonochin_cost + seisojiken_cost
        + soyakeire_dashi_cost + soyakebarimono_cost + doban_hari_cost
        + hassui_kakouchin_cost + shiyu_hiyou_cost + shiyu_cost
        + kamairi_cost + kamadashi_cost + hamasuri_cost
        + kenpin_cost + print_kakouchin_cost
    )

    # 歩留まり(不良)係数を足しこむ例
    yield_coefficient = (raw_material_cost_total + manufacturing_cost_total) * loss_defective
    manufacturing_cost_total += yield_coefficient

    manufacturing_cost_ratio = (manufacturing_cost_total / total_cost * 100) if total_cost > 0 else 0

    # ----- 販売管理費（例: ダミーで on/off） -----
    include_nouhin_jinkenhi = request.form.get('include_nouhin_jinkenhi')
    include_gasoline        = request.form.get('include_gasoline')

    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += 500  # ダミー値
    if include_gasoline:
        sales_admin_cost_total += 300  # ダミー値

    sales_admin_cost_ratio = (sales_admin_cost_total / total_cost * 100) if total_cost > 0 else 0

    # ----- 全体コストと利益 -----
    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total
    profit_amount = total_cost - production_plus_sales
    profit_ratio  = (profit_amount / total_cost * 100) if total_cost > 0 else 0

    # レンダリング用の辞書
    dashboard_data = {
        # 基本入力
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
        # 原材料費
        "raw_material_cost_total": raw_material_cost_total,
        "raw_material_cost_ratio": raw_material_cost_ratio,
        "dohdai_cost": dohdai_cost,
        "kata_cost": kata_cost,
        "drying_fuel_cost": drying_fuel_cost,
        "bisque_fuel_cost": bisque_fuel_cost,
        "hassui_cost": hassui_cost,
        "paint_cost": paint_cost,
        "logo_copper_cost": logo_copper_cost,
        "glaze_material_cost": glaze_material_cost,
        "main_firing_gas_cost": main_firing_gas_cost,
        "transfer_sheet_cost": transfer_sheet_cost,
        # 製造販管費
        "chumikin_cost": chumikin_cost,
        "shiagechin_cost": shiagechin_cost,
        "haiimonochin_cost": haiimonochin_cost,
        "seisojiken_cost": seisojiken_cost,
        "soyakeire_dashi_cost": soyakeire_dashi_cost,
        "soyakebarimono_cost": soyakebarimono_cost,
        "doban_hari_cost": doban_hari_cost,
        "hassui_kakouchin_cost": hassui_kakouchin_cost,
        "shiyu_hiyou_cost": shiyu_hiyou_cost,
        "shiyu_cost": shiyu_cost,
        "kamairi_cost": kamairi_cost,
        "kamadashi_cost": kamadashi_cost,
        "hamasuri_cost": hamasuri_cost,
        "kenpin_cost": kenpin_cost,
        "print_kakouchin_cost": print_kakouchin_cost,
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

    # DB登録など (必要に応じて)
    # 例: ログイン中のユーザーがいれば estimatesテーブルに保存する等
    estimate_id = None
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_connection()
        with conn.cursor() as cursor:
            # 例: activeな見積もりが3件を超えたら古いものを削除
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
                # 必要に応じて削除後の後処理

            # 新規登録
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

    # 計算結果をテンプレートに表示
    return render_template('dashboard_result.html', dashboard_data=dashboard_data)


############################################
# 自動計算用エンドポイント /calculate
# （フロントで fetch('/calculate') するとJSON返却）
############################################
@app.route('/calculate', methods=['POST'])
def calculate():
    """
      JSから非同期で呼ばれる自動計算用API。
      /dashboard_post とほぼ同じ計算を行い JSONを返す。
    """
    try:
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

    total_cost = (
        sales_price + order_quantity + product_weight +
        mold_unit_price + mold_count + kiln_count +
        gas_unit_price + loss_defective
    )

    # --- 原材料費項目 ---
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

    dohdai_cost = 0
    kata_cost = 0
    drying_fuel_cost = 0
    bisque_fuel_cost = 0
    hassui_cost = 0
    paint_cost = 0
    logo_copper_cost = 0
    glaze_material_cost = 0
    main_firing_gas_cost = 0
    transfer_sheet_cost = 0

    if include_dohdai:
        dohdai_cost = product_weight * DOHDAI_COEFFICIENT * order_quantity

    if include_kata:
        if mold_count > 0:
            kata_cost = (mold_unit_price / mold_count) / MOLD_DIVISOR * order_quantity
        else:
            return jsonify({"error": "使用型の数出しが0です"}), 400

    if include_drying_fuel:
        drying_fuel_cost = product_weight * DRYING_FUEL_COEFFICIENT * order_quantity

    if include_bisque_fuel:
        bisque_fuel_cost = product_weight * BISQUE_FUEL_COEFFICIENT * order_quantity

    if include_hassui:
        hassui_cost = product_weight * HASSUI_COEFFICIENT * order_quantity

    if include_paint:
        paint_cost = product_weight * PAINT_COEFFICIENT * order_quantity

    if include_logo_copper:
        try:
            copper_unit_price = float(request.form.get('copper_unit_price', '0'))
        except Exception:
            return jsonify({"error": "銅板単価が不正です"}), 400
        logo_copper_cost = copper_unit_price * order_quantity

    if include_glaze_material:
        if poly_count > 0:
            glaze_material_cost = (glaze_cost / poly_count) * order_quantity
        else:
            return jsonify({"error": "ポリ枚数が0です"}), 400

    if include_main_firing_gas:
        if kiln_count > 0:
            main_firing_gas_cost = (gas_unit_price * FIRING_GAS_CONSTANT) / kiln_count * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    if include_transfer_sheet:
        try:
            transfer_sheet_unit_price = float(request.form.get('transfer_sheet_unit_price', '0'))
        except Exception:
            return jsonify({"error": "転写シート単価が不正です"}), 400
        transfer_sheet_cost = transfer_sheet_unit_price * order_quantity

    raw_material_cost_total = (
        dohdai_cost + kata_cost + drying_fuel_cost + bisque_fuel_cost
        + hassui_cost + paint_cost + logo_copper_cost
        + glaze_material_cost + main_firing_gas_cost + transfer_sheet_cost
    )
    raw_material_cost_ratio = (sales_price / raw_material_cost_total) if raw_material_cost_total > 0 else 0

    # --- 製造販管費項目 ---
    include_chumikin         = request.form.get('include_chumikin')
    include_shiagechin       = request.form.get('include_shiagechin')
    include_haiimonochin     = request.form.get('include_haiimonochin')
    include_seisojiken       = request.form.get('include_seisojiken')
    include_soyakeire_dashi  = request.form.get('include_soyakeire_dashi')
    include_soyakebarimono   = request.form.get('include_soyakebarimono')
    include_doban_hari       = request.form.get('include_doban_hari')
    include_hassui_kakouchin = request.form.get('include_hassui_kakouchin')
    include_shiyu_hiyou      = request.form.get('include_shiyu_hiyou')
    include_shiyu_cost       = request.form.get('include_shiyu_cost')
    include_kamairi          = request.form.get('include_kamairi')
    include_kamadashi        = request.form.get('include_kamadashi')
    include_hamasuri         = request.form.get('include_hamasuri')
    include_kenpin           = request.form.get('include_kenpin')
    include_print_kakouchin  = request.form.get('include_print_kakouchin')

    chumikin_cost = 0
    shiagechin_cost = 0
    haiimonochin_cost = 0
    seisojiken_cost = 0
    soyakeire_dashi_cost = 0
    soyakebarimono_cost = 0
    doban_hari_cost = 0
    hassui_kakouchin_cost = 0
    shiyu_hiyou_cost = 0
    shiyu_cost = 0
    kamairi_cost = 0
    kamadashi_cost = 0
    hamasuri_cost = 0
    kenpin_cost = 0
    print_kakouchin_cost = 0

    # 鋳込み賃
    if include_chumikin:
        chumikin_unit = float(request.form.get('chumikin_unit', '0'))
        chumikin_cost = chumikin_unit * order_quantity

    # 仕上げ賃
    if include_shiagechin:
        shiagechin_unit = float(request.form.get('shiagechin_unit', '0'))
        shiagechin_cost = shiagechin_unit * order_quantity

    # 掃いもの賃
    if include_haiimonochin:
        sawaimono_work = float(request.form.get('sawaimono_work', '0'))
        if sawaimono_work > 0:
            haiimonochin_cost = (mold_unit_price / sawaimono_work) * order_quantity

    # 生素地検品代
    if include_seisojiken:
        seisojiken_work = float(request.form.get('seisojiken_work', '0'))
        if seisojiken_work > 0:
            seisojiken_cost = (HOURLY_WAGE / seisojiken_work) * order_quantity

    # 素焼入れ/出し
    if include_soyakeire_dashi:
        soyakeire_work = float(request.form.get('soyakeire_work', '0'))
        if soyakeire_work > 0:
            soyakeire_dashi_cost = (HOURLY_WAGE / soyakeire_work) * order_quantity

    # 素焼払いもの
    if include_soyakebarimono:
        soyakebarimono_work = float(request.form.get('soyakebarimono_work', '0'))
        if soyakebarimono_work > 0:
            soyakebarimono_cost = (HOURLY_WAGE / soyakebarimono_work) * order_quantity

    # 銅版貼り
    if include_doban_hari:
        doban_hari_unit = float(request.form.get('doban_hari_unit', '0'))
        doban_hari_cost = doban_hari_unit * order_quantity

    # 撥水加工賃
    if include_hassui_kakouchin:
        hassui_kakouchin_work = float(request.form.get('hassui_kakouchin_work', '0'))
        if hassui_kakouchin_work > 0:
            hassui_kakouchin_cost = (HOURLY_WAGE / hassui_kakouchin_work) * order_quantity

    # 絵付け賃
    if include_shiyu_hiyou:
        shiyu_hiyou_unit = float(request.form.get('shiyu_hiyou_unit', '0'))
        shiyu_hiyou_cost = shiyu_hiyou_unit * order_quantity

    # 施釉費
    if include_shiyu_cost:
        shiyu_work = float(request.form.get('shiyu_work', '0'))
        if shiyu_work > 0:
            shiyu_cost = (HOURLY_WAGE / shiyu_work) * order_quantity

    # 窯入れ
    if include_kamairi:
        kamairi_time = float(request.form.get('kamairi_time', '0'))
        if kiln_count > 0 and kamairi_time > 0:
            kamairi_cost = (HOURLY_WAGE * kamairi_time / kiln_count) * order_quantity

    # 窯出し
    if include_kamadashi:
        kamadashi_time = float(request.form.get('kamadashi_time', '0'))
        if kiln_count > 0 and kamadashi_time > 0:
            kamadashi_cost = (HOURLY_WAGE * kamadashi_time / kiln_count) * order_quantity

    # ハマスリ
    if include_hamasuri:
        hamasuri_time = float(request.form.get('hamasuri_time', '0'))
        if kiln_count > 0 and hamasuri_time > 0:
            hamasuri_cost = (HOURLY_WAGE * hamasuri_time / kiln_count) * order_quantity

    # 検品
    if include_kenpin:
        kenpin_time = float(request.form.get('kenpin_time', '0'))
        if kiln_count > 0 and kenpin_time > 0:
            kenpin_cost = (HOURLY_WAGE * kenpin_time / kiln_count) * order_quantity

    # プリント加工賃
    if include_print_kakouchin:
        print_kakouchin_unit = float(request.form.get('print_kakouchin_unit', '0'))
        print_kakouchin_cost = print_kakouchin_unit * order_quantity

    manufacturing_cost_total = (
        chumikin_cost + shiagechin_cost + haiimonochin_cost + seisojiken_cost
        + soyakeire_dashi_cost + soyakebarimono_cost + doban_hari_cost
        + hassui_kakouchin_cost + shiyu_hiyou_cost + shiyu_cost
        + kamairi_cost + kamadashi_cost + hamasuri_cost
        + kenpin_cost + print_kakouchin_cost
    )

    # 歩留まり (不良率) を加算
    yield_coefficient = (raw_material_cost_total + manufacturing_cost_total) * loss_defective
    manufacturing_cost_total += yield_coefficient

    manufacturing_cost_ratio = (manufacturing_cost_total / total_cost * 100) if total_cost > 0 else 0

    # 販売管理費（ダミー）
    include_nouhin_jinkenhi = request.form.get('include_nouhin_jinkenhi')
    include_gasoline        = request.form.get('include_gasoline')

    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += 500
    if include_gasoline:
        sales_admin_cost_total += 300

    sales_admin_cost_ratio = (sales_admin_cost_total / total_cost * 100) if total_cost > 0 else 0

    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total
    profit_amount = total_cost - production_plus_sales
    profit_ratio  = (profit_amount / total_cost * 100) if total_cost > 0 else 0

    # 結果をJSONで返却
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
        # 原材料費
        "raw_material_cost_total": raw_material_cost_total,
        "raw_material_cost_ratio": raw_material_cost_ratio,
        "dohdai_cost": dohdai_cost,
        "kata_cost": kata_cost,
        "drying_fuel_cost": drying_fuel_cost,
        "bisque_fuel_cost": bisque_fuel_cost,
        "hassui_cost": hassui_cost,
        "paint_cost": paint_cost,
        "logo_copper_cost": logo_copper_cost,
        "glaze_material_cost": glaze_material_cost,
        "main_firing_gas_cost": main_firing_gas_cost,
        "transfer_sheet_cost": transfer_sheet_cost,
        # 製造販管費
        "chumikin_cost": chumikin_cost,
        "shiagechin_cost": shiagechin_cost,
        "haiimonochin_cost": haiimonochin_cost,
        "seisojiken_cost": seisojiken_cost,
        "soyakeire_dashi_cost": soyakeire_dashi_cost,
        "soyakebarimono_cost": soyakebarimono_cost,
        "doban_hari_cost": doban_hari_cost,
        "hassui_kakouchin_cost": hassui_kakouchin_cost,
        "shiyu_hiyou_cost": shiyu_hiyou_cost,
        "shiyu_cost": shiyu_cost,
        "kamairi_cost": kamairi_cost,
        "kamadashi_cost": kamadashi_cost,
        "hamasuri_cost": hamasuri_cost,
        "kenpin_cost": kenpin_cost,
        "print_kakouchin_cost": print_kakouchin_cost,
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
    return jsonify(dashboard_data)

######################################
# メイン起動
######################################
if __name__ == '__main__':
    app.run(debug=True)
