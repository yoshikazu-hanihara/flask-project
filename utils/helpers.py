# helpers.py
def round_values_in_dict(data, digits=2):
    for key, val in data.items():
        if isinstance(val, float):
            data[key] = round(val, digits)
    return data

def assemble_dashboard_data(inp, raw_dict, man_dict, sales_admin_cost_total, sales_admin_cost_ratio):
    # 結果まとめ処理
    pass
