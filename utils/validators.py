# validators.py
def parse_input_data(req):
    try:
        return {
            "sales_price": float(req.get('sales_price', '').strip()),
            "order_quantity": int(req.get('order_quantity', '').strip()),
            "product_weight": float(req.get('product_weight', '').strip()),
            "mold_unit_price": float(req.get('mold_unit_price', '').strip()),
            "mold_count": int(req.get('mold_count', '').strip()),
            "glaze_cost": float(req.get('glaze_cost', '').strip()),
            "poly_count": int(req.get('poly_count', '').strip()),
            "kiln_count": int(req.get('kiln_count', '').strip()),
            "gas_unit_price": float(req.get('gas_unit_price', '').strip()),
            "loss_defective": float(req.get('loss_defective', '').strip())
        }
    except Exception as e:
        raise ValueError("入力項目が不十分です: " + str(e))
