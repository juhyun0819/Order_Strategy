# -*- coding: utf-8 -*-
# 여성복 의류 도매 재고 관리 및 판매 분석 시스템

from flask import Flask, session, redirect, url_for, request
from service.db import init_db
from route.dashboard import dashboard_bp
from route.admin import admin_bp
from route.api import api_bp
from route.auth import auth_bp

# Flask 앱 생성
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Blueprint 등록
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# 전역 접근 가드: 로그인 필요
@app.before_request
def require_login():
    open_paths = {'/login', '/logout'}
    if request.path.startswith('/static') or request.path in open_paths or request.path.startswith('/api/'):
        return None
    if not session.get('authenticated'):
        next_url = request.path if request.query_string == b'' else request.path + '?' + request.query_string.decode('utf-8', errors='ignore')
        return redirect(url_for('auth.login', next=next_url))

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=5000)