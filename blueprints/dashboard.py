# blueprints/dashboard.py

from flask import Blueprint, request, session, render_template, jsonify
import json
from db import get_connection

######################################
# 定数・係数
######################################
DOHDAI_COEFFICIENT       = 0.042
DRYING_FUEL_COEFFICIENT  = 0.025
BISQUE_FUEL_COEFFICIENT  = 0.04
HASSUI_COEFFICIENT       = 0.04
PAINT_COEFFICIENT        = 0.05
FIRING_GAS_CONSTANT      = 370
MOLD_DIVISOR             = 100
HOURLY_WAGE              = 3000


dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.app_template_filter('format_thousand')
def format_thousand(value):
    try:
        value = int(value)
        return f"{value:,}"
    except:
        return value

def round_values_in_dict(data, digits=0):
    for key, val in data.items():
        if isinstance(val, float):
            data[key] = round(val, digits)
    return data

def parse_input_data(req):
    try:
        sales_price     = float(req.get('sales_price', '').strip())
        order_quantity  = int(req.get('order_quantity', '').strip())
        product_weight  = float(req.get('product_weight', '').strip())
        mold_unit_price = float(req.get('mold_unit_price', '').strip())
        mold_count      = int(req.get('mold_count', '').strip())
        glaze_cost      = float(req.get('glaze_cost', '').strip())
        poly_count      = int(req.get('poly_count', '').strip())
        kiln_count      = int(req.get('kiln_count', '').strip())
        gas_unit_price  = float(req.get('gas_unit_price', '').strip())
        loss_defective  = float(req.get('loss_defective', '').strip())
    except Exception as e:
        raise ValueError("入力項目が不十分です: " + str(e))

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

def calculate_raw_material_costs(inp, form):
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

    sales_price     = inp["sales_price"]
    order_quantity  = inp["order_quantity"]
    product_weight  = inp["product_weight"]
    mold_unit_price = inp["mold_unit_price"]
    mold_count      = inp["mold_count"]
    glaze_cost      = inp["glaze_cost"]
    poly_count      = inp["poly_count"]
    kiln_count      = inp["kiln_count"]
    gas_unit_price  = inp["gas_unit_price"]

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

    copper_unit_price         = 0
    transfer_sheet_unit_price = 0

    if include_dohdai:
        dohdai_cost = product_weight * DOHDAI_COEFFICIENT * order_quantity

    if include_kata:
        if mold_count <= 0:
            raise ValueError("使用型の数出し数が0以下です。")
        kata_cost = (mold_unit_price / mold_count) / MOLD_DIVISOR * order_quantity

    if include_drying_fuel:
        drying_fuel_cost = product_weight * DRYING_FUEL_COEFFICIENT * order_quantity

    if include_bisque_fuel:
        bisque_fuel_cost = product_weight * BISQUE_FUEL_COEFFICIENT * order_quantity

    if include_hassui:
        hassui_cost = product_weight * HASSUI_COEFFICIENT * order_quantity

    if include_paint:
        paint_cost = product_weight * PAINT_COEFFICIENT * order_quantity

    if include_logo_copper:
        copper_unit_price = float(form.get('copper_unit_price', '0') or 0)
        logo_copper_cost  = copper_unit_price * order_quantity

    if include_glaze_material:
        if poly_count <= 0:
            raise ValueError("ポリの枚数が0以下です。")
        glaze_material_cost = (glaze_cost / poly_count) * order_quantity

    if include_main_firing_gas:
        if kiln_count <= 0:
            raise ValueError("窯入数が0以下です。")
        main_firing_gas_cost = (gas_unit_price * FIRING_GAS_CONSTANT) / kiln_count * order_quantity

    if include_transfer_sheet:
        transfer_sheet_unit_price = float(form.get('transfer_sheet_unit_price', '0') or 0)
        transfer_sheet_cost       = transfer_sheet_unit_price * order_quantity

    genzairyousyoukei_coefficient = (
        (product_weight * DOHDAI_COEFFICIENT if include_dohdai else 0)
        + (((mold_unit_price / mold_count) / MOLD_DIVISOR) if include_kata and mold_count>0 else 0)
        + (product_weight * DRYING_FUEL_COEFFICIENT if include_drying_fuel else 0)
        + (product_weight * BISQUE_FUEL_COEFFICIENT if include_bisque_fuel else 0)
        + (product_weight * HASSUI_COEFFICIENT if include_hassui else 0)
        + (product_weight * PAINT_COEFFICIENT if include_paint else 0)
        + (copper_unit_price if include_logo_copper else 0)
        + ((glaze_cost / poly_count) if include_glaze_material and poly_count>0 else 0)
        + ((gas_unit_price * FIRING_GAS_CONSTANT) if include_main_firing_gas else 0)
        + (transfer_sheet_unit_price if include_transfer_sheet else 0)
    )

    raw_material_cost_total = (
        dohdai_cost + kata_cost + drying_fuel_cost + bisque_fuel_cost
        + hassui_cost + paint_cost + logo_copper_cost
        + glaze_material_cost + main_firing_gas_cost + transfer_sheet_cost
    )

    raw_material_cost_ratio = 0
    if sales_price > 0:
        raw_material_cost_ratio = raw_material_cost_total / sales_price

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

def calculate_manufacturing_costs(inp, form, raw_material_cost_total):
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

    order_quantity  = inp["order_quantity"]
    mold_unit_price = inp["mold_unit_price"]
    kiln_count      = inp["kiln_count"]
    loss_defective  = inp["loss_defective"]
    sales_price     = inp["sales_price"]

    chumikin_cost = float(form.get('chumikin_unit', 0)) * order_quantity if include_chumikin else 0
    shiagechin_cost = float(form.get('shiagechin_unit', 0)) * order_quantity if include_shiagechin else 0

    haiimonochin_cost = ((mold_unit_price / float(form.get('sawaimono_work', 1))) * order_quantity) if include_haiimonochin else 0
    seisojiken_cost = ((HOURLY_WAGE / float(form.get('seisojiken_work', 1))) * order_quantity) if include_seisojiken else 0
    soyakeire_dashi_cost = ((HOURLY_WAGE / float(form.get('soyakeire_work', 1))) * order_quantity) if include_soyakeire_dashi else 0
    soyakebarimono_cost = ((HOURLY_WAGE / float(form.get('soyakebarimono_work', 1))) * order_quantity) if include_soyakebarimono else 0

    doban_hari_cost = float(form.get('doban_hari_unit', 0)) * order_quantity if include_doban_hari else 0
    hassui_kakouchin_cost = ((HOURLY_WAGE / float(form.get('hassui_kakouchin_work', 1))) * order_quantity) if include_hassui_kakouchin else 0

    shiyu_hiyou_cost = float(form.get('shiyu_hiyou_unit', 0)) * order_quantity if include_shiyu_hiyou else 0
    shiyu_cost = ((HOURLY_WAGE / float(form.get('shiyu_work', 1))) * order_quantity) if include_shiyu_cost else 0

    kamairi_cost = (HOURLY_WAGE * float(form.get('kamairi_time', 0)) / kiln_count * order_quantity) if include_kamairi else 0
    kamadashi_cost = (HOURLY_WAGE * float(form.get('kamadashi_time', 0)) / kiln_count * order_quantity) if include_kamadashi else 0
    hamasuri_cost = (HOURLY_WAGE * float(form.get('hamasuri_time', 0)) / kiln_count * order_quantity) if include_hamasuri else 0
    kenpin_cost = (HOURLY_WAGE * float(form.get('kenpin_time', 0)) / kiln_count * order_quantity) if include_kenpin else 0
    print_kakouchin_cost = float(form.get('print_kakouchin_unit', 0)) * order_quantity if include_print_kakouchin else 0

    seizousyoukei_total = (
        chumikin_cost + shiagechin_cost + haiimonochin_cost + seisojiken_cost +
        soyakeire_dashi_cost + soyakebarimono_cost + doban_hari_cost +
        hassui_kakouchin_cost + shiyu_hiyou_cost + shiyu_cost +
        kamairi_cost + kamadashi_cost + hamasuri_cost +
        kenpin_cost + print_kakouchin_cost
    )

    seizousyoukei_coefficient = seizousyoukei_total / order_quantity if order_quantity else 0
    yield_coefficient = (seizousyoukei_coefficient + raw_material_cost_total / order_quantity) * loss_defective
    manufacturing_cost_total = seizousyoukei_total + (yield_coefficient * order_quantity)
    manufacturing_cost_ratio = ((seizousyoukei_coefficient + yield_coefficient) / sales_price * 100) if sales_price else 0

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

        "seizousyoukei_coefficient": seizousyoukei_coefficient,
        "yield_coefficient": yield_coefficient,
        "manufacturing_cost_total": manufacturing_cost_total,
        "manufacturing_cost_ratio": manufacturing_cost_ratio,
    }

def calculate_sales_admin_cost(form, order_quantity, total_cost):
    include_nouhin_jinkenhi = form.get('include_nouhin_jinkenhi')
    include_gasoline        = form.get('include_gasoline')

    total_sales_admin_cost = 0
    if include_nouhin_jinkenhi:
        total_sales_admin_cost += 7500
    if include_gasoline:
        total_sales_admin_cost += 750

    sales_admin_cost_total = total_sales_admin_cost / order_quantity if order_quantity else 0

    sales_admin_cost_ratio = (sales_admin_cost_total / total_cost * 100) if total_cost > 0 else 0
    return sales_admin_cost_total, sales_admin_cost_ratio


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

    total_cost = (
        sales_price + order_quantity + product_weight +
        mold_unit_price + mold_count + kiln_count +
        gas_unit_price + loss_defective
    )

    raw_material_cost_total = raw_dict.get("raw_material_cost_total", 0)
    raw_material_cost_ratio = raw_dict.get("raw_material_cost_ratio", 0)
    manufacturing_cost_total = man_dict.get("manufacturing_cost_total", 0)
    yield_coefficient = man_dict.get("yield_coefficient", 0)

    production_cost_total = raw_material_cost_total + manufacturing_cost_total
    production_plus_sales = production_cost_total + sales_admin_cost_total

    profit_amount = total_cost - production_plus_sales
    profit_ratio  = (profit_amount / total_cost * 100) if total_cost > 0 else 0

    manufacturing_cost_ratio = man_dict.get("manufacturing_cost_ratio", 0)

    return {
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
        "dohdai_cost": raw_dict.get("dohdai_cost", 0),
        "kata_cost": raw_dict.get("kata_cost", 0),
        "drying_fuel_cost": raw_dict.get("drying_fuel_cost", 0),
        "bisque_fuel_cost": raw_dict.get("bisque_fuel_cost", 0),
        "hassui_cost": raw_dict.get("hassui_cost", 0),
        "paint_cost": raw_dict.get("paint_cost", 0),
        "logo_copper_cost": raw_dict.get("logo_copper_cost", 0),
        "glaze_material_cost": raw_dict.get("glaze_material_cost", 0),
        "main_firing_gas_cost": raw_dict.get("main_firing_gas_cost", 0),
        "transfer_sheet_cost": raw_dict.get("transfer_sheet_cost", 0),
        "genzairyousyoukei_coefficient": raw_dict.get("genzairyousyoukei_coefficient", 0),

        "chumikin_cost": man_dict.get("chumikin_cost", 0),
        "shiagechin_cost": man_dict.get("shiagechin_cost", 0),
        "haiimonochin_cost": man_dict.get("haiimonochin_cost", 0),
        "seisojiken_cost": man_dict.get("seisojiken_cost", 0),
        "soyakeire_dashi_cost": man_dict.get("soyakeire_dashi_cost", 0),
        "soyakebarimono_cost": man_dict.get("soyakebarimono_cost", 0),
        "doban_hari_cost": man_dict.get("doban_hari_cost", 0),
        "hassui_kakouchin_cost": man_dict.get("hassui_kakouchin_cost", 0),
        "shiyu_hiyou_cost": man_dict.get("shiyu_hiyou_cost", 0),
        "shiyu_cost": man_dict.get("shiyu_cost", 0),
        "kamairi_cost": man_dict.get("kamairi_cost", 0),
        "kamadashi_cost": man_dict.get("kamadashi_cost", 0),
        "hamasuri_cost": man_dict.get("hamasuri_cost", 0),
        "kenpin_cost": man_dict.get("kenpin_cost", 0),
        "print_kakouchin_cost": man_dict.get("print_kakouchin_cost", 0),
        "yield_coefficient": yield_coefficient,
        "manufacturing_cost_total": manufacturing_cost_total,
        "manufacturing_cost_ratio": manufacturing_cost_ratio,
        "seizousyoukei_coefficient": man_dict.get("seizousyoukei_coefficient", 0),

        "sales_admin_cost_total": sales_admin_cost_total,
        "sales_admin_cost_ratio": sales_admin_cost_ratio,

        "production_cost_total": production_cost_total,
        "production_plus_sales": production_plus_sales,
        "profit_amount": profit_amount,
        "profit_ratio": profit_ratio
    }


# --- ここからすべてを dashboard_bp で定義 ---

@dashboard_bp.route('/')
def dashboard():
    """ダッシュボード表示"""
    return render_template('dashboard.html')


@dashboard_bp.route('/post', methods=['POST'])
def dashboard_post():
    try:
        inp = parse_input_data(request.form)
    except ValueError as e:
        return str(e)

    total_cost = (
        inp["sales_price"] + inp["order_quantity"] + inp["product_weight"] +
        inp["mold_unit_price"] + inp["mold_count"] + inp["kiln_count"] +
        inp["gas_unit_price"] + inp["loss_defective"]
    )

    try:
        raw_dict = calculate_raw_material_costs(inp, request.form)
    except ValueError as e:
        return str(e)

    man_dict = calculate_manufacturing_costs(inp, request.form, raw_dict["raw_material_cost_total"])

    sales_admin_cost_total, sales_admin_cost_ratio = calculate_sales_admin_cost(request.form, total_cost)

    dashboard_data = assemble_dashboard_data(inp, raw_dict, man_dict, sales_admin_cost_total, sales_admin_cost_ratio)
    round_values_in_dict(dashboard_data, digits=0)

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


@dashboard_bp.route('/calculate', methods=['POST'])
def calculate():
    try:
        inp = parse_input_data(request.form)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    total_cost = (
        inp["sales_price"] + inp["order_quantity"] + inp["product_weight"] +
        inp["mold_unit_price"] + inp["mold_count"] + inp["kiln_count"] +
        inp["gas_unit_price"] + inp["loss_defective"]
    )

    try:
        raw_dict = calculate_raw_material_costs(inp, request.form)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    man_dict = calculate_manufacturing_costs(inp, request.form, raw_dict["raw_material_cost_total"])

    sales_admin_cost_total, sales_admin_cost_ratio = calculate_sales_admin_cost(request.form, total_cost)

    dashboard_data = assemble_dashboard_data(inp, raw_dict, man_dict, sales_admin_cost_total, sales_admin_cost_ratio)
    round_values_in_dict(dashboard_data, digits=0)

    return jsonify(dashboard_data)
