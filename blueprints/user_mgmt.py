from flask import Blueprint, render_template, redirect, url_for, session, request
from db import get_connection, get_account_column

user_mgmt_bp = Blueprint('user_mgmt', __name__, url_prefix='/user_mgmt')

@user_mgmt_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    conn = get_connection()
    account_col = get_account_column()
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT id, {account_col} FROM users ORDER BY id")
        users = cursor.fetchall()
        for user in users:
            user['account_name'] = user.get(account_col)
    conn.close()
    return render_template('user_mgmt.html', users=users)

@user_mgmt_bp.route('/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id: int):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('user_mgmt.index'))
