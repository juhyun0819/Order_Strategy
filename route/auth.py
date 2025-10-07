from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import os
import hmac

auth_bp = Blueprint('auth', __name__)


def _get_app_password() -> str:
    # 운영에서는 환경변수로 제공: APP_PASSWORD
    return os.environ.get('APP_PASSWORD', 'changeme')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        expected = _get_app_password()
        if hmac.compare_digest(password, expected):
            session['authenticated'] = True
            flash('로그인되었습니다.', 'success')
            next_url = request.args.get('next') or url_for('dashboard.dashboard')
            return redirect(next_url)
        flash('비밀번호가 올바르지 않습니다.', 'error')
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('로그아웃되었습니다.', 'success')
    return redirect(url_for('auth.login'))


