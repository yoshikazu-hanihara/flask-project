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
DOHDAI_COEFFICIENT       = 0.042  # 土代係数
DRYING_FUEL_COEFFICIENT  = 0.025  # 乾燥燃料係数
BISQUE_FUEL_COEFFICIENT  = 0.04   # 素焼き燃料係数
HASSUI_COEFFICIENT       = 0.04   # 撥水剤係数
PAINT_COEFFICIENT        = 0.05   # 絵具係数
FIRING_GAS_CONSTANT      = 370    # 本焼きガス計算時の定数
MOLD_DIVISOR             = 100    # 型代計算用の割り係数
HOURLY_WAGE              = 3000   # 時給3000円

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
# 小数点以下を一括で四捨五入する関数
######################################
def round_values_in_dict(data, digits=2):
    """
    data (dict) 内の float値をすべて小数点以下 digits 桁に四捨五入して更新する。
    ネストがない単純な辞書を想定。
    """
    for key, val in data.items():
        if isinstance(val, float):
            data[key] = round(val, digits)
    return data

######################################
# 安全に float/int に変換するヘルパー
######################################
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

##################################################
# 1) 入力値の取得（未入力は0とみなす）
##################################################
def parse_input_data(req):
    """
    従来のように「入力されていないとエラー」ではなく、
    入力が空なら 0 とみなす。
    """
    sales_price     = safe_float(req.get('sales_price', ''))
    order_quantity  = safe_int(req.get('order_quantity', ''))
    product_weight  = safe_float(req.get('product_weight', ''))
    mold_unit_price = safe_float(req.get('mold_unit_price', ''))
    mold_count      = safe_int(req.get('mold_count', ''))
    glaze_cost      = safe_float(req.get('glaze_cost', ''))
    poly_count      = safe_int(req.get('poly_count', ''))
    kiln_count      = safe_int(req.get('kiln_count', ''))
    gas_unit_price  = safe_float(req.get('gas_unit_price', ''))
    loss_defective  = safe_float(req.get('loss_defective', ''))

    return {
        "sales_price": sales_price,
        "order_quantity": order_quantity,
        "product_weight": product_weight,
        "mold_unit_price": mold_unit_price,
        "mold_count": mold_count,
        "glaze_cost": glaze_cost,
        "poly_count": poly_count,
        "kiln_count": kiln_count,
        "gas_unit_price": gas_unit_price,
        "loss_defective": loss_defective
    }

##################################################
# 2) 原材料費計算
##################################################
def calculate_raw_material_costs(inp, form):
    """
    原材料費の on/off チェックと計算
    inp: parse_input_data()の戻り値 (未入力は0で補完済み)
    form: request.form
    """
    # フォームの on/off
    include_dohdai          = form.get('include_dohdai')
    include_kata            = form.get('include_kata')
    include_drying_fuel     = form.get('include_drying_fuel')
    include_bisque_fuel     = form.get('include_bisque_fuel')
    include_hassui          = form.get('include_hassui')
    include_paint           = form.get('include_paint')
    include_logo_copper     = form.get('include_logo_copper')
    include_glaze_material  = form.get('include_glaze_material')
    include_main_firing_gas = form.get('include_main_firing_gas')
    include_transfer_sheet  = form.get('include_transfer_sheet')

    # 入力パラメータ
    sales_price     = inp["sales_price"]
    order_quantity  = inp["order_quantity"]
    product_weight  = inp["product_weight"]
    mold_unit_price = inp["mold_unit_price"]
    mold_count      = inp["mold_count"]
    glaze_cost      = inp["glaze_cost"]
    poly_count      = inp["poly_count"]
    kiln_count      = inp["kiln_count"]
    gas_unit_price  = inp["gas_unit_price"]

    # 各項目の初期化
    dohdai_cost           = 0
    kata_cost             = 0
    drying_fuel_cost      = 0
    bisque_fuel_cost      = 0
    hassui_cost           = 0
    paint_cost            = 0
    logo_copper_cost      = 0
    glaze_material_cost   = 0
    main_firing_gas_cost  = 0
    transfer_sheet_cost   = 0

    # 計算時に使用する単価系
    copper_unit_price         = 0
    transfer_sheet_unit_price = 0

    # 1) 土代
    if include_dohdai:
        if product_weight > 0 and order_quantity > 0:
            dohdai_cost = product_weight * DOHDAI_COEFFICIENT * order_quantity

    # 2) 型代
    if include_kata:
        if mold_count > 0 and order_quantity > 0:
            kata_cost = (mold_unit_price / mold_count) / MOLD_DIVISOR * order_quantity

    # 3) 乾燥燃料
    if include_drying_fuel:
        if product_weight > 0 and order_quantity > 0:
            drying_fuel_cost = product_weight * DRYING_FUEL_COEFFICIENT * order_quantity

    # 4) 素焼燃料
    if include_bisque_fuel:
        if product_weight > 0 and order_quantity > 0:
            bisque_fuel_cost = product_weight * BISQUE_FUEL_COEFFICIENT * order_quantity

    # 5) 撥水剤
    if include_hassui:
        if product_weight > 0 and order_quantity > 0:
            hassui_cost = product_weight * HASSUI_COEFFICIENT * order_quantity

    # 6) 絵具
    if include_paint:
        if product_weight > 0 and order_quantity > 0:
            paint_cost = product_weight * PAINT_COEFFICIENT * order_quantity

    # 7) ロゴ銅板
    if include_logo_copper:
        try:
            copper_unit_price = float(form.get('copper_unit_price', '0'))
        except:
            copper_unit_price = 0
        if order_quantity > 0:
            logo_copper_cost = copper_unit_price * order_quantity

    # 8) 釉薬
    if include_glaze_material:
        if poly_count > 0 and order_quantity > 0:
            glaze_material_cost = (glaze_cost / poly_count) * order_quantity

    # 9) 本焼成ガス
    if include_main_firing_gas:
        if kiln_count > 0 and order_quantity > 0:
            main_firing_gas_cost = (gas_unit_price * FIRING_GAS_CONSTANT) / kiln_count * order_quantity

    # 10) 転写シート
    if include_transfer_sheet:
        try:
            transfer_sheet_unit_price = float(form.get('transfer_sheet_unit_price', '0'))
        except:
            transfer_sheet_unit_price = 0
        if order_quantity > 0:
            transfer_sheet_cost = transfer_sheet_unit_price * order_quantity

    # 材料費項目-小計
    genzairyousyoukei_coefficient = (
        (product_weight * DOHDAI_COEFFICIENT if product_weight>0 else 0)
        + ((mold_unit_price / mold_count) / MOLD_DIVISOR if (mold_count>0) else 0)
        + (product_weight * DRYING_FUEL_COEFFICIENT if product_weight>0 else 0)
        + (product_weight * BISQUE_FUEL_COEFFICIENT if product_weight>0 else 0)
        + (product_weight * HASSUI_COEFFICIENT if product_weight>0 else 0)
        + (product_weight * PAINT_COEFFICIENT if product_weight>0 else 0)
        + copper_unit_price
        + ((glaze_cost / poly_count) if poly_count>0 else 0)
        + ((gas_unit_price * FIRING_GAS_CONSTANT) if kiln_count>0 else 0)
        + transfer_sheet_unit_price
    )

    raw_material_cost_total = (
        dohdai_cost + kata_cost + drying_fuel_cost + bisque_fuel_cost
        + hassui_cost + paint_cost + logo_copper_cost
        + glaze_material_cost + main_firing_gas_cost + transfer_sheet_cost
    )

    # 原材料費原価率(例: 売価×数量に対する割合)
    raw_material_cost_ratio = 0
    if sales_price > 0 and order_quantity > 0:
        raw_material_cost_ratio = (raw_material_cost_total / (sales_price * order_quantity)) * 100

    return {
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
        "raw_material_cost_total": raw_material_cost_total,
        "raw_material_cost_ratio": raw_material_cost_ratio,
        "genzairyousyoukei_coefficient": genzairyousyoukei_coefficient
    }

##################################################
# 3) 製造販管費計算
##################################################
def calculate_manufacturing_costs(inp, form, raw_material_cost_total):
    """
    製造販管費の on/off チェックと計算
    inp: parse_input_data()の戻り値
    form: request.form
    raw_material_cost_total: 原材料費(後で歩留まり計算に使用)
    """
    # フォームの on/off
    include_chumikin         = form.get('include_chumikin')
    include_shiagechin       = form.get('include_shiagechin')
    include_haiimonochin     = form.get('include_haiimonochin')
    include_seisojiken       = form.get('include_seisojiken')
    include_soyakeire_dashi  = form.get('include_soyakeire_dashi')
    include_soyakebarimono   = form.get('include_soyakebarimono')
    include_doban_hari       = form.get('include_doban_hari')
    include_hassui_kakouchin = form.get('include_hassui_kakouchin')
    include_shiyu_hiyou      = form.get('include_shiyu_hiyou')
    include_shiyu_cost       = form.get('include_shiyu_cost')
    include_kamairi          = form.get('include_kamairi')
    include_kamadashi        = form.get('include_kamadashi')
    include_hamasuri         = form.get('include_hamasuri')
    include_kenpin           = form.get('include_kenpin')
    include_print_kakouchin  = form.get('include_print_kakouchin')

    # 入力パラメータ
    sales_price     = inp["sales_price"]
    order_quantity  = inp["order_quantity"]
    mold_unit_price = inp["mold_unit_price"]
    kiln_count      = inp["kiln_count"]
    loss_defective  = inp["loss_defective"]

    # 各コスト初期化
    chumikin_cost          = 0
    shiagechin_cost        = 0
    haiimonochin_cost      = 0
    seisojiken_cost        = 0
    soyakeire_dashi_cost   = 0
    soyakebarimono_cost    = 0
    doban_hari_cost        = 0
    hassui_kakouchin_cost  = 0
    shiyu_hiyou_cost       = 0
    shiyu_cost             = 0
    kamairi_cost           = 0
    kamadashi_cost         = 0
    hamasuri_cost          = 0
    kenpin_cost            = 0
    print_kakouchin_cost   = 0

    # 1) 鋳込み賃
    chumikin_unit = 0
    if include_chumikin and order_quantity > 0:
        try:
            chumikin_unit = float(form.get('chumikin_unit', '0'))
        except:
            chumikin_unit = 0
        chumikin_cost = chumikin_unit * order_quantity

    # 2) 仕上げ賃
    shiagechin_unit = 0
    if include_shiagechin and order_quantity > 0:
        try:
            shiagechin_unit = float(form.get('shiagechin_unit', '0'))
        except:
            shiagechin_unit = 0
        shiagechin_cost = shiagechin_unit * order_quantity

    # 3) 掃いもの賃
    #   例では「sawaimono_work」で1時間あたり作業量→時給換算などがあるかもしれませんが、
    #   とりあえずサンプルとして0除算にならないようにチェック
    sawaimono_work = safe_float(form.get('sawaimono_work', '0'))
    if include_haiimonochin and sawaimono_work>0 and order_quantity>0:
        # 例： (型単価 / 1時間の作業量) * 個数
        haiimonochin_cost = (mold_unit_price / sawaimono_work) * order_quantity

    # 4) 生素地検品代
    seisojiken_work = safe_float(form.get('seisojiken_work', '0'))
    if include_seisojiken and seisojiken_work>0 and order_quantity>0:
        seisojiken_cost = (HOURLY_WAGE / seisojiken_work) * order_quantity

    # 5) 素焼入れ/出し
    soyakeire_work = safe_float(form.get('soyakeire_work', '0'))
    if include_soyakeire_dashi and soyakeire_work>0 and order_quantity>0:
        soyakeire_dashi_cost = (HOURLY_WAGE / soyakeire_work) * order_quantity

    # 6) 素焼払いもの
    soyakebarimono_work = safe_float(form.get('soyakebarimono_work', '0'))
    if include_soyakebarimono and soyakebarimono_work>0 and order_quantity>0:
        soyakebarimono_cost = (HOURLY_WAGE / soyakebarimono_work) * order_quantity

    # 7) 銅版貼り
    doban_hari_unit = 0
    if include_doban_hari and order_quantity>0:
        try:
            doban_hari_unit = float(form.get('doban_hari_unit', '0'))
        except:
            doban_hari_unit = 0
        doban_hari_cost = doban_hari_unit * order_quantity

    # 8) 撥水加工賃
    hassui_kakouchin_work = safe_float(form.get('hassui_kakouchin_work', '0'))
    if include_hassui_kakouchin and hassui_kakouchin_work>0 and order_quantity>0:
        hassui_kakouchin_cost = (HOURLY_WAGE / hassui_kakouchin_work) * order_quantity

    # 9) 絵付け賃
    shiyu_hiyou_unit = 0
    if include_shiyu_hiyou and order_quantity>0:
        try:
            shiyu_hiyou_unit = float(form.get('shiyu_hiyou_unit', '0'))
        except:
            shiyu_hiyou_unit = 0
        shiyu_hiyou_cost = shiyu_hiyou_unit * order_quantity

    # 10) 施釉費
    shiyu_work = safe_float(form.get('shiyu_work', '0'))
    if include_shiyu_cost and shiyu_work>0 and order_quantity>0:
        shiyu_cost = (HOURLY_WAGE / shiyu_work) * order_quantity

    # 11) 窯入れ
    kamairi_time = safe_float(form.get('kamairi_time', '0'))
    if include_kamairi and kiln_count>0 and kamairi_time>0 and order_quantity>0:
        kamairi_cost = (HOURLY_WAGE * kamairi_time / kiln_count) * order_quantity

    # 12) 窯出し
    kamadashi_time = safe_float(form.get('kamadashi_time', '0'))
    if include_kamadashi and kiln_count>0 and kamadashi_time>0 and order_quantity>0:
        kamadashi_cost = (HOURLY_WAGE * kamadashi_time / kiln_count) * order_quantity

    # 13) ハマスリ
    hamasuri_time = safe_float(form.get('hamasuri_time', '0'))
    if include_hamasuri and kiln_count>0 and hamasuri_time>0 and order_quantity>0:
        hamasuri_cost = (HOURLY_WAGE * hamasuri_time / kiln_count) * order_quantity

    # 14) 検品
    kenpin_time = safe_float(form.get('kenpin_time', '0'))
    if include_kenpin and kiln_count>0 and kenpin_time>0 and order_quantity>0:
        kenpin_cost = (HOURLY_WAGE * kenpin_time / kiln_count) * order_quantity

    # 15) プリント加工賃
    print_kakouchin_unit = 0
    if include_print_kakouchin and order_quantity>0:
        try:
            print_kakouchin_unit = float(form.get('print_kakouchin_unit', '0'))
        except:
            print_kakouchin_unit = 0
        print_kakouchin_cost = print_kakouchin_unit * order_quantity

    # 製造項目-小計(係数)
    # ここでは例として単純に上記「単価系」をすべて足すイメージ
    seizousyoukei_coefficient = (
        chumikin_unit
        + shiagechin_unit
        + (mold_unit_price / sawaimono_work if sawaimono_work>0 else 0)
        + (HOURLY_WAGE / seisojiken_work if seisojiken_work>0 else 0)
        + (HOURLY_WAGE / soyakeire_work if soyakeire_work>0 else 0)
        + (HOURLY_WAGE / soyakebarimono_work if soyakebarimono_work>0 else 0)
        + doban_hari_unit
        + (HOURLY_WAGE / hassui_kakouchin_work if hassui_kakouchin_work>0 else 0)
        + shiyu_hiyou_unit
        + (HOURLY_WAGE / shiyu_work if shiyu_work>0 else 0)
        + (HOURLY_WAGE * kamairi_time / kiln_count if (kiln_count>0 and kamairi_time>0) else 0)
        + (HOURLY_WAGE * kamadashi_time / kiln_count if (kiln_count>0 and kamadashi_time>0) else 0)
        + (HOURLY_WAGE * hamasuri_time / kiln_count if (kiln_count>0 and hamasuri_time>0) else 0)
        + (HOURLY_WAGE * kenpin_time / kiln_count if (kiln_count>0 and kenpin_time>0) else 0)
        + print_kakouchin_unit
    )

    # 歩留まり係数
    yield_coefficient = (raw_material_cost_total + seizousyoukei_coefficient) * loss_defective

    manufacturing_cost_total = seizousyoukei_coefficient + yield_coefficient

    # 製造販管費原価率(例: 売価×数量に対する割合)
    manufacturing_cost_ratio = 0
    if sales_price>0 and order_quantity>0:
        manufacturing_cost_ratio = (manufacturing_cost_total / (sales_price * order_quantity)) * 100

    return {
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
        "yield_coefficient": yield_coefficient,
        "manufacturing_cost_total": manufacturing_cost_total,
        "seizousyoukei_coefficient": seizousyoukei_coefficient,
        "manufacturing_cost_ratio": manufacturing_cost_ratio
    }

##################################################
# 4) 販売管理費計算 (ダミー例)
##################################################
def calculate_sales_admin_cost(form, total_cost):
    """
    販売管理費 on/off チェック。
    今回はダミー(納品人件費=500,ガソリン=300)で加算する例
    """
    include_nouhin_jinkenhi = form.get('include_nouhin_jinkenhi')
    include_gasoline        = form.get('include_gasoline')

    sales_admin_cost_total = 0
    if include_nouhin_jinkenhi:
        sales_admin_cost_total += 500
    if include_gasoline:
        sales_admin_cost_total += 300

    # 全体コストが0でないときだけ比率を算出
    sales_admin_cost_ratio = 0
    if total_cost > 0:
        sales_admin_cost_ratio = (sales_admin_cost_total / total_cost) * 100

    return sales_admin_cost_total, sales_admin_cost_ratio

##################################################
# 5) 結果をまとめるヘルパー
##################################################
def assemble_dashboard_data(
    inp,
    raw_dict,
    man_dict,
    sales_admin_cost_total,
    sales_admin_cost_ratio
):
    sales_price     = inp["sales_price"]
    order_quantity  = inp["order_quantity"]
    product_weight  = inp["product_weight"]
    mold_unit_price = inp["mold_unit_price"]
    mold_count      = inp["mold_count"]
    kiln_count      = inp["kiln_count"]
    gas_unit_price  = inp["gas_unit_price"]
    loss_defective  = inp["loss_defective"]
    poly_count      = inp["poly_count"]
    glaze_cost      = inp["glaze_cost"]

    # 便宜的な total_cost 例 (要件次第でお好きに)
    # 普通は「売上 = sales_price * order_quantity」などを想定
    total_cost = (
        sales_price + order_quantity + product_weight +
        mold_unit_price + mold_count + kiln_count +
        gas_unit_price + loss_defective
    )

    raw_material_cost_total = raw_dict["raw_material_cost_total"]
    raw_material_cost_ratio = raw_dict["raw_material_cost_ratio"]
    manufacturing_cost_total = man_dict["manufacturing_cost_total"]
    manufacturing_cost_ratio = man_dict["manufacturing_cost_ratio"]
    yield_coefficient = man_dict["yield_coefficient"]

    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total

    profit_amount = total_cost - production_plus_sales
    profit_ratio  = 0
    if total_cost > 0:
        profit_ratio  = (profit_amount / total_cost) * 100

    return {
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
        "dohdai_cost": raw_dict["dohdai_cost"],
        "kata_cost": raw_dict["kata_cost"],
        "drying_fuel_cost": raw_dict["drying_fuel_cost"],
        "bisque_fuel_cost": raw_dict["bisque_fuel_cost"],
        "hassui_cost": raw_dict["hassui_cost"],
        "paint_cost": raw_dict["paint_cost"],
        "logo_copper_cost": raw_dict["logo_copper_cost"],
        "glaze_material_cost": raw_dict["glaze_material_cost"],
        "main_firing_gas_cost": raw_dict["main_firing_gas_cost"],
        "transfer_sheet_cost": raw_dict["transfer_sheet_cost"],
        "genzairyousyoukei_coefficient": raw_dict["genzairyousyoukei_coefficient"],

        # 製造販管費
        "chumikin_cost": man_dict["chumikin_cost"],
        "shiagechin_cost": man_dict["shiagechin_cost"],
        "haiimonochin_cost": man_dict["haiimonochin_cost"],
        "seisojiken_cost": man_dict["seisojiken_cost"],
        "soyakeire_dashi_cost": man_dict["soyakeire_dashi_cost"],
        "soyakebarimono_cost": man_dict["soyakebarimono_cost"],
        "doban_hari_cost": man_dict["doban_hari_cost"],
        "hassui_kakouchin_cost": man_dict["hassui_kakouchin_cost"],
        "shiyu_hiyou_cost": man_dict["shiyu_hiyou_cost"],
        "shiyu_cost": man_dict["shiyu_cost"],
        "kamairi_cost": man_dict["kamairi_cost"],
        "kamadashi_cost": man_dict["kamadashi_cost"],
        "hamasuri_cost": man_dict["hamasuri_cost"],
        "kenpin_cost": man_dict["kenpin_cost"],
        "print_kakouchin_cost": man_dict["print_kakouchin_cost"],
        "yield_coefficient": yield_coefficient,
        "manufacturing_cost_total": manufacturing_cost_total,
        "manufacturing_cost_ratio": manufacturing_cost_ratio,
        "seizousyoukei_coefficient": man_dict["seizousyoukei_coefficient"],

        # 販売管理費
        "sales_admin_cost_total": sales_admin_cost_total,
        "sales_admin_cost_ratio": sales_admin_cost_ratio,

        # 全体
        "production_cost_total": production_cost_total,
        "production_plus_sales": production_plus_sales,
        "profit_amount": profit_amount,
        "profit_ratio": profit_ratio
    }

######################################
# ダッシュボード表示
######################################
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

########################################
# ダッシュボードのPOST処理
########################################
@app.route('/dashboard_post', methods=['POST'])
def dashboard_post():
    """
      dashboard.html のフォーム送信時の処理
      （こちらはあまり変更なし。未入力は0扱いになっている）
    """
    # インプット取得
    inp = parse_input_data(request.form)

    # 便宜的な total_cost
    total_cost = (
        inp["sales_price"] + inp["order_quantity"] + inp["product_weight"] +
        inp["mold_unit_price"] + inp["mold_count"] + inp["kiln_count"] +
        inp["gas_unit_price"] + inp["loss_defective"]
    )

    # 原材料費
    raw_dict = calculate_raw_material_costs(inp, request.form)
    # 製造販管費
    man_dict = calculate_manufacturing_costs(inp, request.form, raw_dict["raw_material_cost_total"])
    # 販売管理費
    sales_admin_cost_total, sales_admin_cost_ratio = calculate_sales_admin_cost(request.form, total_cost)
    # 結果まとめ
    dashboard_data = assemble_dashboard_data(inp, raw_dict, man_dict, sales_admin_cost_total, sales_admin_cost_ratio)
    # 丸め
    round_values_in_dict(dashboard_data, digits=2)

    # DB登録など (必要に応じて)
    estimate_id = None
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_connection()
        with conn.cursor() as cursor:
            # アクティブ件数などの管理例
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

    return render_template('dashboard_result.html', dashboard_data=dashboard_data)

############################################
# 自動計算用エンドポイント /calculate
############################################
@app.route('/calculate', methods=['POST'])
def calculate():
    """
      JSから非同期で呼ばれる自動計算用API。
      未入力項目は全て0扱いで計算し、部分結果を返す。
    """
    # 入力データをパース（未入力は0にする）
    inp = parse_input_data(request.form)

    # 便宜的 total_cost
    total_cost = (
        inp["sales_price"] + inp["order_quantity"] + inp["product_weight"] +
        inp["mold_unit_price"] + inp["mold_count"] + inp["kiln_count"] +
        inp["gas_unit_price"] + inp["loss_defective"]
    )

    # 1) 原材料費
    raw_dict = calculate_raw_material_costs(inp, request.form)
    # 2) 製造販管費
    man_dict = calculate_manufacturing_costs(inp, request.form, raw_dict["raw_material_cost_total"])
    # 3) 販売管理費
    sales_admin_cost_total, sales_admin_cost_ratio = calculate_sales_admin_cost(request.form, total_cost)
    # 4) 組み立て
    dashboard_data = assemble_dashboard_data(inp, raw_dict, man_dict, sales_admin_cost_total, sales_admin_cost_ratio)
    # 5) 丸め
    round_values_in_dict(dashboard_data, digits=2)

    return jsonify(dashboard_data)

######################################
# メイン起動
######################################
if __name__ == '__main__':
    app.run(debug=True)
