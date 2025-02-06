from flask import Flask, request, session, render_template, url_for, redirect, jsonify
import os
import json
from flask_mail import Mail, Message
from passlib.hash import bcrypt_sha256
from datetime import datetime
from auth import auth as auth_blueprint
from estimate import estimate_blueprint
from db import get_connection

######################################
# 定数・係数一覧（一括管理）
######################################
# 材料関連定数（既存）
DOHDAI_COEFFICIENT = 0.042          # 土代係数
DRYING_FUEL_COEFFICIENT = 0.025     # 乾燥燃料係数
BISQUE_FUEL_COEFFICIENT = 0.04      # 素焼き燃料係数
HASSUI_COEFFICIENT = 0.04           # 撥水剤係数
PAINT_COEFFICIENT = 0.05            # 絵具係数
FIRING_GAS_CONSTANT = 370           # 本焼きガス計算時の定数
MOLD_DIVISOR = 100                  # 型代計算用の割り係数

# 時給定数（新規）
HOURLY_WAGE = 3000  # 3000円

######################################
# Flask基本設定
######################################
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッションキー

# カスタムフィルタ
@app.template_filter('format_thousand')
def format_thousand(value):
    try:
        value = int(value)
        return f"{value:,}"
    except Exception:
        return value

# Flask-Mail の設定（例）
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nworks12345@gmail.com'
app.config['MAIL_PASSWORD'] = 'yspr vktd yrmc wntn'
app.config['MAIL_DEFAULT_SENDER'] = 'nworks12345@gmail.com'
mail = Mail(app)

# Blueprint の登録
app.register_blueprint(auth_blueprint, url_prefix='')
app.register_blueprint(estimate_blueprint, url_prefix='')

######################################
# ダッシュボード表示
######################################
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/dashboard_post', methods=['POST'])
def dashboard_post():
    # ※従来の処理（必要に応じて更新）
    # ここでは /calculate での計算結果をもとにDB登録等を行う例
    try:
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

    total_cost = (sales_price + order_quantity + product_weight +
                  mold_unit_price + mold_count + kiln_count +
                  gas_unit_price + loss_defective)

    # 材料費原価計算（従来通り）
    include_dohdai = request.form.get('include_dohdai')
    include_kata = request.form.get('include_kata')
    include_drying_fuel = request.form.get('include_drying_fuel')
    include_bisque_fuel = request.form.get('include_bisque_fuel')
    include_hassui = request.form.get('include_hassui')
    include_paint = request.form.get('include_paint')
    include_logo_copper = request.form.get('include_logo_copper')
    include_glaze_material = request.form.get('include_glaze_material')
    include_main_firing_gas = request.form.get('include_main_firing_gas')
    include_transfer_sheet = request.form.get('include_transfer_sheet')

    raw_material_cost_total = 0
    if include_dohdai:
        raw_material_cost_total += product_weight * DOHDAI_COEFFICIENT * order_quantity
    if include_kata:
        if mold_count > 0:
            raw_material_cost_total += (mold_unit_price / mold_count) / MOLD_DIVISOR * order_quantity
        else:
            return "使用型の数出し数が0です。"
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
            return "銅板単価が不正です。"
        raw_material_cost_total += copper_unit_price * order_quantity
    if include_glaze_material:
        if poly_count > 0:
            raw_material_cost_total += (glaze_cost / poly_count) * order_quantity
        else:
            return "ポリの枚数が0です。"
    if include_main_firing_gas:
        if kiln_count > 0:
            raw_material_cost_total += (gas_unit_price * FIRING_GAS_CONSTANT) / kiln_count * order_quantity
        else:
            return "窯入数が0です。"
    if include_transfer_sheet:
        try:
            transfer_sheet_unit_price = float(request.form.get('transfer_sheet_unit_price', '0'))
        except Exception:
            return "転写単価が不正です。"
        raw_material_cost_total += transfer_sheet_unit_price * order_quantity

    raw_material_cost_ratio = (sales_price / raw_material_cost_total) if raw_material_cost_total > 0 else 0

    # 製造販管費の各項目計算（新仕様）
    # 各項目は、チェックがオンの場合に新規入力やラジオ選択の値を用いて計算する

    # 1. 鋳込み賃
    include_chumikin = request.form.get('include_chumikin')
    chumikin_cost = 0
    if include_chumikin:
        chumikin_unit = float(request.form.get('chumikin_unit', '0'))
        chumikin_cost = chumikin_unit * order_quantity

    # 2. 仕上げ賃
    include_shiagechin = request.form.get('include_shiagechin')
    shiagechin_cost = 0
    if include_shiagechin:
        shiagechin_unit = float(request.form.get('shiagechin_unit', '0'))
        shiagechin_cost = shiagechin_unit * order_quantity

    # 3. 掃いもの賃
    include_haiimonochin = request.form.get('include_haiimonochin')
    haiimonochin_cost = 0
    if include_haiimonochin:
        haiimonochin_unit = float(request.form.get('haiimonochin_unit', '0'))
        sawaimono_work = float(request.form.get('sawaimono_work', '0'))
        haiimonochin_cost = haiimonochin_unit * sawaimono_work * order_quantity

    # 4. 生素地検品代
    include_seisojiken = request.form.get('include_seisojiken')
    seisojiken_cost = 0
    if include_seisojiken:
        seisojiken_unit = float(request.form.get('seisojiken_unit', '0'))
        seisojiken_work = float(request.form.get('seisojiken_work', '0'))
        seisojiken_cost = seisojiken_unit * seisojiken_work * order_quantity

    # 5. 素焼入れ/出し
    include_soyakeire_dashi = request.form.get('include_soyakeire_dashi')
    soyakeire_dashi_cost = 0
    if include_soyakeire_dashi:
        soyakeire_dashi_unit = float(request.form.get('soyakeire_dashi_unit', '0'))
        soyakeire_work = float(request.form.get('soyakeire_work', '0'))
        soyakeire_dashi_cost = soyakeire_dashi_unit * soyakeire_work * order_quantity

    # 6. 素焼払いもの
    include_soyakebarimono = request.form.get('include_soyakebarimono')
    soyakebarimono_cost = 0
    if include_soyakebarimono:
        soyakebarimono_unit = float(request.form.get('soyakebarimono_unit', '0'))
        soyakebarimono_work = float(request.form.get('soyakebarimono_work', '0'))
        soyakebarimono_cost = soyakebarimono_unit * soyakebarimono_work * order_quantity

    # 7. 銅版貼り
    include_doban_hari = request.form.get('include_doban_hari')
    doban_hari_cost = 0
    if include_doban_hari:
        doban_hari_unit = float(request.form.get('doban_hari_unit', '0'))
        doban_hari_work = float(request.form.get('doban_hari_work', '0'))
        doban_hari_cost = doban_hari_unit * doban_hari_work * order_quantity

    # 8. 撥水加工賃
    include_hassui_kakouchin = request.form.get('include_hassui_kakouchin')
    hassui_kakouchin_cost = 0
    if include_hassui_kakouchin:
        hassui_kakouchin_unit = float(request.form.get('hassui_kakouchin_unit', '0'))
        hassui_kakouchin_work = float(request.form.get('hassui_kakouchin_work', '0'))
        hassui_kakouchin_cost = hassui_kakouchin_unit * hassui_kakouchin_work * order_quantity

    # 9. 絵付け賃
    include_shiyu_hiyou = request.form.get('include_shiyu_hiyou')
    shiyu_hiyou_cost = 0
    if include_shiyu_hiyou:
        shiyu_hiyou_unit = float(request.form.get('shiyu_hiyou_unit', '0'))
        shiyu_hiyou_work = float(request.form.get('shiyu_hiyou_work', '0'))
        shiyu_hiyou_cost = shiyu_hiyou_unit * shiyu_hiyou_work * order_quantity

    # 10. 施釉費
    include_shiyu_cost = request.form.get('include_shiyu_cost')
    shiyu_cost = 0
    if include_shiyu_cost:
        shiyu_work = float(request.form.get('shiyu_work', '0'))
        if shiyu_work > 0:
            shiyu_cost = (HOURLY_WAGE / shiyu_work) * order_quantity
        else:
            return jsonify({"error": "施釉作業量が0です"}), 400

    # 11. 窯入れ作業費
    include_kamairi = request.form.get('include_kamairi')
    kamairi_cost = 0
    if include_kamairi:
        kamairi_time = float(request.form.get('kamairi_time', '0'))
        if kiln_count > 0:
            kamairi_cost = (HOURLY_WAGE * kamairi_time / kiln_count) * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    # 12. 窯出し作業費
    include_kamadashi = request.form.get('include_kamadashi')
    kamadashi_cost = 0
    if include_kamadashi:
        kamadashi_time = float(request.form.get('kamadashi_time', '0'))
        if kiln_count > 0:
            kamadashi_cost = (HOURLY_WAGE * kamadashi_time / kiln_count) * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    # 13. ハマスリ費用
    include_hamasuri = request.form.get('include_hamasuri')
    hamasuri_cost = 0
    if include_hamasuri:
        hamasuri_time = float(request.form.get('hamasuri_time', '0'))
        if kiln_count > 0:
            hamasuri_cost = (HOURLY_WAGE * hamasuri_time / kiln_count) * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    # 14. 検品費用
    include_kenpin = request.form.get('include_kenpin')
    kenpin_cost = 0
    if include_kenpin:
        kenpin_time = float(request.form.get('kenpin_time', '0'))
        if kiln_count > 0:
            kenpin_cost = (HOURLY_WAGE * kenpin_time / kiln_count) * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    # 15. プリント加工賃
    include_print_kakouchin = request.form.get('include_print_kakouchin')
    print_kakouchin_cost = 0
    if include_print_kakouchin:
        print_kakouchin_unit = float(request.form.get('print_kakouchin_unit', '0'))
        print_kakouchin_cost = print_kakouchin_unit * order_quantity

    # 製造販管費の合計（各項目の合計）
    manufacturing_cost_total = (chumikin_cost + shiagechin_cost + haiimonochin_cost +
                                  seisojiken_cost + soyakeire_dashi_cost + soyakebarimono_cost +
                                  doban_hari_cost + hassui_kakouchin_cost + shiyu_hiyou_cost +
                                  shiyu_cost + kamairi_cost + kamadashi_cost +
                                  hamasuri_cost + kenpin_cost + print_kakouchin_cost)

    # 歩留まり係数： (原材料費合計 + 製造販管費合計) * ロス 不良
    yield_coefficient = (raw_material_cost_total + manufacturing_cost_total) * loss_defective

    # 製造販管費最終合計（歩留まりを加算）
    manufacturing_cost_total += yield_coefficient

    manufacturing_cost_ratio = (manufacturing_cost_total / total_cost * 100) if total_cost > 0 else 0

    # 販売管理費（従来のダミー処理）
    include_nouhin_jinkenhi = request.form.get('include_nouhin_jinkenhi')
    include_gasoline = request.form.get('include_gasoline')
    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += 500  # ダミー値
    if include_gasoline:
        sales_admin_cost_total += 300  # ダミー値
    sales_admin_cost_ratio = (sales_admin_cost_total / total_cost * 100) if total_cost > 0 else 0

    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total
    profit_amount = total_cost - production_plus_sales
    profit_ratio = (profit_amount / total_cost * 100) if total_cost > 0 else 0

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
        # 製造販管費各項目
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

    # DB登録等（省略・必要に応じて実装）
    session['dashboard_data'] = dashboard_data
    return render_template('dashboard_result.html', dashboard_data=dashboard_data)

######################################
# 自動計算用エンドポイント /calculate
######################################
@app.route('/calculate', methods=['POST'])
def calculate():
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

    total_cost = (sales_price + order_quantity + product_weight +
                  mold_unit_price + mold_count + kiln_count +
                  gas_unit_price + loss_defective)

    # 材料費原価（同様に計算）
    include_dohdai = request.form.get('include_dohdai')
    include_kata = request.form.get('include_kata')
    include_drying_fuel = request.form.get('include_drying_fuel')
    include_bisque_fuel = request.form.get('include_bisque_fuel')
    include_hassui = request.form.get('include_hassui')
    include_paint = request.form.get('include_paint')
    include_logo_copper = request.form.get('include_logo_copper')
    include_glaze_material = request.form.get('include_glaze_material')
    include_main_firing_gas = request.form.get('include_main_firing_gas')
    include_transfer_sheet = request.form.get('include_transfer_sheet')

    raw_material_cost_total = 0
    if include_dohdai:
        raw_material_cost_total += product_weight * DOHDAI_COEFFICIENT * order_quantity
    if include_kata:
        if mold_count > 0:
            raw_material_cost_total += (mold_unit_price / mold_count) / MOLD_DIVISOR * order_quantity
        else:
            return jsonify({"error": "使用型の数出し数が0です"}), 400
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
            return jsonify({"error": "銅板単価が不正です"}), 400
        raw_material_cost_total += copper_unit_price * order_quantity
    if include_glaze_material:
        if poly_count > 0:
            raw_material_cost_total += (glaze_cost / poly_count) * order_quantity
        else:
            return jsonify({"error": "ポリの枚数が0です"}), 400
    if include_main_firing_gas:
        if kiln_count > 0:
            raw_material_cost_total += (gas_unit_price * FIRING_GAS_CONSTANT) / kiln_count * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400
    if include_transfer_sheet:
        try:
            transfer_sheet_unit_price = float(request.form.get('transfer_sheet_unit_price', '0'))
        except Exception:
            return jsonify({"error": "転写単価が不正です"}), 400
        raw_material_cost_total += transfer_sheet_unit_price * order_quantity

    raw_material_cost_ratio = (sales_price / raw_material_cost_total) if raw_material_cost_total > 0 else 0

    # 製造販管費（新仕様）
    # 1. 鋳込み賃
    include_chumikin = request.form.get('include_chumikin')
    chumikin_cost = 0
    if include_chumikin:
        chumikin_unit = float(request.form.get('chumikin_unit', '0'))
        chumikin_cost = chumikin_unit * order_quantity

    # 2. 仕上げ賃
    include_shiagechin = request.form.get('include_shiagechin')
    shiagechin_cost = 0
    if include_shiagechin:
        shiagechin_unit = float(request.form.get('shiagechin_unit', '0'))
        shiagechin_cost = shiagechin_unit * order_quantity

    # 3. 掃いもの賃
    include_haiimonochin = request.form.get('include_haiimonochin')
    haiimonochin_cost = 0
    if include_haiimonochin:
        haiimonochin_unit = float(request.form.get('haiimonochin_unit', '0'))
        sawaimono_work = float(request.form.get('sawaimono_work', '0'))
        haiimonochin_cost = haiimonochin_unit * sawaimono_work * order_quantity

    # 4. 生素地検品代
    include_seisojiken = request.form.get('include_seisojiken')
    seisojiken_cost = 0
    if include_seisojiken:
        seisojiken_unit = float(request.form.get('seisojiken_unit', '0'))
        seisojiken_work = float(request.form.get('seisojiken_work', '0'))
        seisojiken_cost = seisojiken_unit * seisojiken_work * order_quantity

    # 5. 素焼入れ/出し
    include_soyakeire_dashi = request.form.get('include_soyakeire_dashi')
    soyakeire_dashi_cost = 0
    if include_soyakeire_dashi:
        soyakeire_dashi_unit = float(request.form.get('soyakeire_dashi_unit', '0'))
        soyakeire_work = float(request.form.get('soyakeire_work', '0'))
        soyakeire_dashi_cost = soyakeire_dashi_unit * soyakeire_work * order_quantity

    # 6. 素焼払いもの
    include_soyakebarimono = request.form.get('include_soyakebarimono')
    soyakebarimono_cost = 0
    if include_soyakebarimono:
        soyakebarimono_unit = float(request.form.get('soyakebarimono_unit', '0'))
        soyakebarimono_work = float(request.form.get('soyakebarimono_work', '0'))
        soyakebarimono_cost = soyakebarimono_unit * soyakebarimono_work * order_quantity

    # 7. 銅版貼り
    include_doban_hari = request.form.get('include_doban_hari')
    doban_hari_cost = 0
    if include_doban_hari:
        doban_hari_unit = float(request.form.get('doban_hari_unit', '0'))
        doban_hari_work = float(request.form.get('doban_hari_work', '0'))
        doban_hari_cost = doban_hari_unit * doban_hari_work * order_quantity

    # 8. 撥水加工賃
    include_hassui_kakouchin = request.form.get('include_hassui_kakouchin')
    hassui_kakouchin_cost = 0
    if include_hassui_kakouchin:
        hassui_kakouchin_unit = float(request.form.get('hassui_kakouchin_unit', '0'))
        hassui_kakouchin_work = float(request.form.get('hassui_kakouchin_work', '0'))
        hassui_kakouchin_cost = hassui_kakouchin_unit * hassui_kakouchin_work * order_quantity

    # 9. 絵付け賃
    include_shiyu_hiyou = request.form.get('include_shiyu_hiyou')
    shiyu_hiyou_cost = 0
    if include_shiyu_hiyou:
        shiyu_hiyou_unit = float(request.form.get('shiyu_hiyou_unit', '0'))
        shiyu_hiyou_work = float(request.form.get('shiyu_hiyou_work', '0'))
        shiyu_hiyou_cost = shiyu_hiyou_unit * shiyu_hiyou_work * order_quantity

    # 10. 施釉費
    include_shiyu_cost = request.form.get('include_shiyu_cost')
    shiyu_cost = 0
    if include_shiyu_cost:
        shiyu_work = float(request.form.get('shiyu_work', '0'))
        if shiyu_work > 0:
            shiyu_cost = (HOURLY_WAGE / shiyu_work) * order_quantity
        else:
            return jsonify({"error": "施釉作業量が0です"}), 400

    # 11. 窯入れ作業費
    include_kamairi = request.form.get('include_kamairi')
    kamairi_cost = 0
    if include_kamairi:
        kamairi_time = float(request.form.get('kamairi_time', '0'))
        if kiln_count > 0:
            kamairi_cost = (HOURLY_WAGE * kamairi_time / kiln_count) * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    # 12. 窯出し作業費
    include_kamadashi = request.form.get('include_kamadashi')
    kamadashi_cost = 0
    if include_kamadashi:
        kamadashi_time = float(request.form.get('kamadashi_time', '0'))
        if kiln_count > 0:
            kamadashi_cost = (HOURLY_WAGE * kamadashi_time / kiln_count) * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    # 13. ハマスリ費用
    include_hamasuri = request.form.get('include_hamasuri')
    hamasuri_cost = 0
    if include_hamasuri:
        hamasuri_time = float(request.form.get('hamasuri_time', '0'))
        if kiln_count > 0:
            hamasuri_cost = (HOURLY_WAGE * hamasuri_time / kiln_count) * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    # 14. 検品費用
    include_kenpin = request.form.get('include_kenpin')
    kenpin_cost = 0
    if include_kenpin:
        kenpin_time = float(request.form.get('kenpin_time', '0'))
        if kiln_count > 0:
            kenpin_cost = (HOURLY_WAGE * kenpin_time / kiln_count) * order_quantity
        else:
            return jsonify({"error": "窯入数が0です"}), 400

    # 15. プリント加工賃
    include_print_kakouchin = request.form.get('include_print_kakouchin')
    print_kakouchin_cost = 0
    if include_print_kakouchin:
        print_kakouchin_unit = float(request.form.get('print_kakouchin_unit', '0'))
        print_kakouchin_cost = print_kakouchin_unit * order_quantity

    manufacturing_cost_total = (chumikin_cost + shiagechin_cost + haiimonochin_cost +
                                seisojiken_cost + soyakeire_dashi_cost + soyakebarimono_cost +
                                doban_hari_cost + hassui_kakouchin_cost + shiyu_hiyou_cost +
                                shiyu_cost + kamairi_cost + kamadashi_cost +
                                hamasuri_cost + kenpin_cost + print_kakouchin_cost)

    yield_coefficient = (raw_material_cost_total + manufacturing_cost_total) * loss_defective
    manufacturing_cost_total += yield_coefficient

    manufacturing_cost_ratio = (manufacturing_cost_total / total_cost * 100) if total_cost > 0 else 0

    # 販売管理費（ダミー）
    include_nouhin_jinkenhi = request.form.get('include_nouhin_jinkenhi')
    include_gasoline = request.form.get('include_gasoline')
    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += 500
    if include_gasoline:
        sales_admin_cost_total += 300
    sales_admin_cost_ratio = (sales_admin_cost_total / total_cost * 100) if total_cost > 0 else 0

    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total
    profit_amount = total_cost - production_plus_sales
    profit_ratio = (profit_amount / total_cost * 100) if total_cost > 0 else 0

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
        # 製造販管費各項目
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
# メイン
######################################
if __name__ == '__main__':
    app.run(debug=True)
