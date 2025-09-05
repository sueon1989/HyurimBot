#!/usr/bin/env python3
"""
HyurimBot 통합 관리자 대시보드 실행 스크립트
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 관리자 대시보드 앱 실행
if __name__ == '__main__':
    from src.data_collection.admin_dashboard.app import app
    
    print("🚀 HyurimBot 통합 관리자 대시보드 시작")
    print("📊 URL: http://localhost:5000")
    print("🔄 포트: 5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)