# -*- coding: utf-8 -*-
# 여성복 의류 도매 재고 관리 및 판매 분석 시스템

from flask import Flask
from service.db import init_db
from route.dashboard import dashboard_bp
from route.admin import admin_bp
from route.api import api_bp

# Flask 앱 생성
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Blueprint 등록
app.register_blueprint(dashboard_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000) 