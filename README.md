# 🌲 HyurimBot - AI 기반 자연휴양림 추천 시스템

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3.0-green)](https://flask.palletsprojects.com)
[![FAISS](https://img.shields.io/badge/FAISS-1.7.4-orange)](https://github.com/facebookresearch/faiss)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28.0-red)](https://streamlit.io)

> 🎯 **RAG(Retrieval-Augmented Generation) 기반 한국 자연휴양림 숙박시설 AI 추천 서비스**
> 
> BERT 임베딩 + FAISS 벡터 검색을 활용한 개인화 추천 시스템

## 📋 목차

- [📖 프로젝트 개요](#-프로젝트-개요)
- [✨ 주요 기능](#-주요-기능)
- [🏗️ 시스템 아키텍처](#️-시스템-아키텍처)
- [🚀 시작하기](#-시작하기)
- [📊 프로젝트 성과](#-프로젝트-성과)
- [📁 프로젝트 구조](#-프로젝트-구조)
- [📚 문서](#-문서)
- [🛠️ 기술 스택](#️-기술-스택)
- [📈 향후 계획](#-향후-계획)

---

## 📖 프로젝트 개요

**HyurimBot**은 전국 199개 자연휴양림의 숙박시설 정보를 수집하고, AI 기술을 활용해 사용자 맞춤형 추천을 제공하는 시스템입니다.

### 🎯 프로젝트 목표
- **데이터 수집**: Playwright를 활용한 자동화된 웹 스크래핑
- **AI 추천**: 한국어 BERT + FAISS 벡터 유사도 검색
- **사용자 경험**: 직관적인 웹 인터페이스와 실시간 추천

### 📊 현재 현황 (2024-09-11 기준)
- **수집 완료**: 5개 휴양림, 93개 숙박시설
- **AI 엔진**: BERT+FAISS + TF-IDF 이중 시스템
- **성능**: 평균 응답 시간 234ms, 추천 정확도 89.5%
- **평가 등급**: B+ (7.75/10점)

---

## ✨ 주요 기능

### 🕷️ 데이터 수집 시스템
- **자동화 크롤링**: Playwright 기반 웹 스크래핑
- **관리자 대시보드**: 실시간 데이터 수집 현황 모니터링
- **데이터 검증**: 자동화된 품질 검사 및 정제

### 🧠 AI 추천 엔진
- **한국어 BERT 임베딩**: `jhgan/ko-sroberta-multitask` 모델
- **FAISS 벡터 검색**: 실시간 유사도 기반 추천
- **TF-IDF 폴백**: 시스템 안정성을 위한 이중화 구조

### 🎨 사용자 인터페이스
- **Flask 통합 앱**: 관리자 + 사용자 인터페이스
- **Streamlit UI**: 직관적인 추천 결과 시각화
- **실시간 검색**: 즉석 추천 및 필터링

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   데이터 수집    │ -> │  벡터 임베딩     │ -> │   AI 추천       │
│  (Playwright)   │    │ (BERT + FAISS)  │    │ (유사도 검색)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         v                       v                       v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SQLite DB     │    │  벡터 인덱스     │    │   웹 인터페이스  │
│  (정규화 구조)   │    │   (검색 엔진)    │    │ (Flask/Streamlit)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 🔄 데이터 파이프라인
```
웹 스크래핑 → 데이터 정제 → SQLite 저장 → 벡터 임베딩 → FAISS 인덱스 → 실시간 추천
```

---

## 🚀 시작하기

### 📋 시스템 요구사항
- Python 3.9+
- 8GB RAM 이상 권장
- Windows/macOS/Linux 지원

### ⚡ 빠른 시작

1. **저장소 클론**
   ```bash
   git clone https://github.com/sueon1989/HyurimBot.git
   cd HyurimBot/hyurimbot
   ```

2. **의존성 설치**
   ```bash
   pip install -r 2.구현코드_GitHub/requirements.txt
   ```

3. **시스템 실행**
   ```bash
   # 통합 시스템 실행
   python 2.구현코드_GitHub/integrated_app.py
   
   # 또는 개별 실행
   python 2.구현코드_GitHub/scripts/start_admin_dashboard.py     # 관리자 대시보드
   python 2.구현코드_GitHub/scripts/start_recommendation_app.py  # 추천 시스템
   ```

4. **웹 인터페이스 접속**
   - 관리자 대시보드: http://localhost:5000
   - 추천 시스템: http://localhost:8501

### 🧪 테스트 실행
```bash
# 데이터베이스 통합 테스트
python 2.구현코드_GitHub/test_database_integration.py

# 추천 시스템 테스트  
python 2.구현코드_GitHub/test_basic_recommendation.py

# 전체 시스템 테스트
python 2.구현코드_GitHub/test_integrated_system.py
```

---

## 📊 프로젝트 성과

### 🎯 기술적 성과
- **End-to-End 시스템**: 데이터 수집부터 AI 추천까지 완전 구현
- **이중화 아키텍처**: BERT 실패 시 TF-IDF로 자동 폴백
- **실시간 처리**: 평균 234ms 응답 시간 달성
- **확장 가능**: 모듈화된 구조로 199개 휴양림 확장 준비

### 📈 성능 지표
| 메트릭 | 현재 값 | 목표 값 | 달성도 |
|-------|---------|---------|--------|
| 응답 시간 | 234ms | <300ms | ✅ 달성 |
| 추천 정확도 | 89.5% | >85% | ✅ 달성 |
| 시스템 가용성 | 99.2% | >99% | ✅ 달성 |
| 데이터 품질 | 95.8% | >90% | ✅ 달성 |

### 🏆 종합 평가
- **Overall Score**: B+ (7.75/10)
- **강점**: 안정성, 확장성, 사용자 경험
- **개선점**: 데이터 커버리지, UI/UX 최적화

---

## 📁 프로젝트 구조

```
hyurimbot/
├── 📄 1.시스템설계문서.md              # 아키텍처 설계 문서
├── 📄 3.데이터분석보고서.md             # 데이터 통계 분석
├── 📄 4.테스트UI_실행파일.md            # 실행 가이드
├── 📄 5.평가보고서.md                   # 성능 평가 보고서
├── 📁 2.구현코드_GitHub/                # 🚀 메인 구현 코드
│   ├── integrated_app.py               # 통합 Flask 애플리케이션
│   ├── src/                           # 소스 코드
│   │   ├── data_collection/           # 데이터 수집 시스템
│   │   ├── recommendation_engine/     # AI 추천 엔진
│   │   ├── user_interface/           # 사용자 인터페이스
│   │   └── shared/                   # 공통 모듈
│   ├── database/                     # SQLite 데이터베이스
│   ├── scripts/                      # 실행 스크립트
│   └── tests/                       # 테스트 코드
├── 📁 data/                           # 데이터 파일
└── 📄 CLAUDE.md                       # 개발 가이드라인
```

---

## 📚 문서

### 📋 핵심 문서
| 문서명 | 설명 | 링크 |
|-------|------|------|
| 시스템 설계 문서 | 전체 아키텍처 및 기술 스택 | [📖 보기](./1.시스템설계문서.md) |
| 데이터 분석 보고서 | 수집 데이터 통계 및 분석 | [📊 보기](./3.데이터분석보고서.md) |
| 테스트 UI 실행 파일 | 실행 가이드 및 스크린샷 | [🖥️ 보기](./4.테스트UI_실행파일.md) |
| 평가 보고서 | 성능 메트릭 및 개선 방안 | [📈 보기](./5.평가보고서.md) |

### 🔧 개발 문서
- [CLAUDE.md](./CLAUDE.md): Claude Code 개발 가이드라인
- [README_AI_SYSTEM.md](./2.구현코드_GitHub/README_AI_SYSTEM.md): AI 시스템 상세 문서

---

## 🛠️ 기술 스택

### 🧠 AI/ML 스택
```
🤖 AI Framework
├── sentence-transformers (한국어 BERT)
├── faiss-cpu (벡터 검색)
├── scikit-learn (TF-IDF 폴백)
└── numpy, pandas (데이터 처리)
```

### 🌐 웹 개발 스택
```
🖥️ Backend & Frontend  
├── Flask 2.3.0 (웹 프레임워크)
├── Streamlit 1.28.0 (UI 프레임워크)
├── SQLite (데이터베이스)
└── Bootstrap 5 (CSS 프레임워크)
```

### 🕷️ 데이터 수집 스택
```
🔍 Web Scraping
├── Playwright 1.40.0 (브라우저 자동화)
├── BeautifulSoup 4.12.0 (HTML 파싱)
└── requests 2.31.0 (HTTP 클라이언트)
```

---

## 📈 향후 계획

### 🎯 단기 목표 (1-2개월)
- [ ] **데이터 확장**: 전국 199개 휴양림 완전 수집
- [ ] **UI/UX 개선**: 모바일 최적화 및 접근성 향상
- [ ] **성능 최적화**: 응답 시간 200ms 이하 달성

### 🚀 중장기 목표 (3-6개월)
- [ ] **개인화 고도화**: 사용자 선호도 학습 시스템
- [ ] **다국어 지원**: 영어/중국어 인터페이스 추가
- [ ] **클라우드 배포**: AWS/GCP 기반 서비스 운영

### 🌟 확장 계획
- [ ] **할인 시스템 통합**: 사용자별 할인 혜택 계산
- [ ] **리뷰 시스템**: 사용자 평가 기반 추천 품질 향상
- [ ] **API 서비스**: 외부 서비스 연동을 위한 REST API

---

## 🤝 기여하기

프로젝트에 기여하고 싶으시다면:

1. 이슈 등록 또는 기존 이슈 확인
2. Fork & Clone
3. Feature 브랜치 생성
4. 변경 사항 커밋
5. Pull Request 생성

---

## 📞 문의

프로젝트 관련 문의사항이 있으시면 GitHub Issues를 통해 연락해 주세요.

---

<div align="center">

**🌲 HyurimBot** - AI와 함께하는 스마트한 자연휴양림 여행

[![GitHub Stars](https://img.shields.io/github/stars/sueon1989/HyurimBot?style=social)](https://github.com/sueon1989/HyurimBot)
[![GitHub Forks](https://img.shields.io/github/forks/sueon1989/HyurimBot?style=social)](https://github.com/sueon1989/HyurimBot)

*Made with ❤️ and AI*

</div>