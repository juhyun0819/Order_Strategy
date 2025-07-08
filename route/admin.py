from flask import Blueprint, request, redirect, url_for, flash
from service.db import delete_by_date, reset_db

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/delete-date', methods=['POST'])
def delete_date():
    date_to_delete = request.form.get('date')
    if date_to_delete:
        deleted = delete_by_date(date_to_delete)
        if deleted > 0:
            flash(f'{date_to_delete} 데이터 {deleted}건 삭제 완료!', 'success')
        else:
            flash('삭제할 데이터가 없습니다.', 'warning')
    return redirect(url_for('dashboard.dashboard'))

@admin_bp.route('/reset-db')
def reset_database():
    try:
        reset_db()
        flash('데이터베이스가 성공적으로 초기화되었습니다.', 'success')
    except Exception as e:
        flash(f'데이터베이스 초기화 중 오류가 발생했습니다: {str(e)}', 'error')
    return redirect(url_for('dashboard.dashboard')) 