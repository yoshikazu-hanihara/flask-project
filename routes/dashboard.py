# dashboard.py
from flask import Blueprint, render_template, request, session
from utils.validators import parse_input_data
from utils.calculators import calculate_raw_material_costs, calculate_manufacturing_costs, calculate_sales_admin_cost
from utils.helpers import assemble_dashboard_data, round_values_in_dict
from db import get_connection
import json

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@dashboard_bp.route('/dashboard_post', methods=['POST'])
def dashboard_post():
    # 元の処理をここに移植
    pass
