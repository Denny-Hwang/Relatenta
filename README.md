# 🔬 Reatenta

**Research Relationship Visualization Platform** — 학술 연구자 간 관계를 인터랙티브 네트워크 그래프로 시각화하는 플랫폼

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Overview

OpenAlex API(2억 5천만+ 학술 레코드)와 CSV 데이터를 기반으로 연구자, 키워드, 기관, 국가 간 협력 관계를 **4-Layer 네트워크 그래프**와 **히트맵**으로 시각화합니다.

### 핵심 기능
- 🔍 **OpenAlex 연구자 검색 & 데이터 수집** — 향상된 저자 동명이인 구별 (H-index, i10-index, 인용수, ORCID 등)
- 🌐 **4-Layer 네트워크 시각화** — 공저자, 키워드 동시출현, 기관 협력, 국가 협력
- 📊 **히트맵 분석** — 저자-키워드, 국가-국가 협력 매트릭스
- 🎭 **Multi-Actor 아키텍처** — 독립된 데이터베이스로 다수의 분석 프로젝트 병렬 관리
- 📁 **CSV Import/Export** — 논문, 저자, 소속, 키워드 데이터 일괄 처리
- 🔗 **포커스 필터링** — 특정 노드 중심의 Ego Network 분석

---

## 📂 Folder Structure

```
reatenta/
├── README.md                    # 이 파일
├── requirements.txt             # Python 의존성
├── .env.example                 # 환경변수 템플릿
├── .gitignore                   # Git 제외 파일
├── streamlit_app.py             # 🖥️  Streamlit 프론트엔드 (1,800+ lines)
├── app/                         # 🔧 FastAPI 백엔드 패키지
│   ├── __init__.py
│   ├── main.py                  # FastAPI 앱 & 16개 API 엔드포인트
│   ├── models.py                # SQLAlchemy ORM 모델 (12 테이블)
│   ├── db.py                    # 데이터베이스 엔진 & 세션 관리
│   ├── schemas.py               # Pydantic 요청/응답 스키마
│   ├── crud.py                  # CRUD 연산 & 엣지 재계산
│   ├── connectors_openalex.py   # OpenAlex API 커넥터
│   ├── services_graph.py        # 네트워크 그래프 빌더
│   ├── services_heatmap.py      # 히트맵 데이터 생성
│   └── services_export.py       # CSV/ZIP 내보내기 서비스
├── databases/                   # 📦 SQLite DB 파일 저장 (자동생성)
│   └── .gitkeep
└── docs/                        # 📖 문서
    ├── Implementation_Guide.md  # 구현 가이드
    ├── User_manual.md           # 사용자 매뉴얼
    └── Research_Viz_SW개발문서.docx  # 소프트웨어 개발 문서
```

---

## 🏗️ Architecture

```
┌─────────────────────┐     HTTP/REST      ┌─────────────────────┐
│   Streamlit Frontend │ ◄──────────────► │   FastAPI Backend    │
│   (streamlit_app.py) │                   │   (app/main.py)      │
│                      │                   │                      │
│  • Actor 관리 UI      │                   │  • 16 API Endpoints  │
│  • 검색 & Ingest      │                   │  • CRUD Operations   │
│  • PyVis 그래프 렌더링 │                   │  • Graph Builder     │
│  • Plotly 히트맵      │                   │  • Heatmap Engine    │
│  • CSV Import/Export  │                   │  • Export Service    │
└─────────────────────┘                   └──────────┬──────────┘
                                                      │
                              ┌────────────────────────┼─────────────────┐
                              │                        │                 │
                    ┌─────────▼──────┐     ┌──────────▼──────┐  ┌──────▼───────┐
                    │  SQLite (per   │     │  OpenAlex API   │  │  CSV Files   │
                    │  Actor DB)     │     │  (250M+ records)│  │  (Import)    │
                    └────────────────┘     └─────────────────┘  └──────────────┘
```

---

## ⚡ Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/your-username/reatenta.git
cd reatenta

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# 필요시 .env 파일 편집
```

### 3. 서버 실행

**터미널 1 — FastAPI 백엔드:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**터미널 2 — Streamlit 프론트엔드:**
```bash
streamlit run streamlit_app.py --server.port 8501
```

### 4. 브라우저 접속

- **Frontend:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | 서버 상태 확인 |
| `GET` | `/actors` | Actor 목록 조회 |
| `POST` | `/actors/{name}/init` | 새 Actor DB 초기화 |
| `DELETE` | `/actors/{name}` | Actor DB 삭제 |
| `GET` | `/actors/{name}/stats` | Actor 통계 조회 |
| `GET` | `/actors/{name}/export` | Actor 데이터 CSV 내보내기 |
| `GET` | `/search-authors` | OpenAlex 저자 검색 |
| `GET` | `/{actor}/search-local-authors` | 로컬 저자 검색 |
| `GET` | `/{actor}/search-local-keywords` | 로컬 키워드 검색 |
| `GET` | `/{actor}/search-local-orgs` | 로컬 기관 검색 |
| `POST` | `/{actor}/validate-authors` | 저자 ID 검증 |
| `POST` | `/{actor}/validate-keywords` | 키워드 ID 검증 |
| `POST` | `/{actor}/validate-orgs` | 기관 ID 검증 |
| `POST` | `/{actor}/ingest/openalex` | OpenAlex 데이터 수집 |
| `POST` | `/{actor}/graph` | 네트워크 그래프 생성 |
| `POST` | `/{actor}/heatmap` | 히트맵 데이터 생성 |
| `POST` | `/{actor}/import/csv` | CSV 데이터 가져오기 |

---

## 🗄️ Database Schema

12개 테이블로 구성된 관계형 데이터베이스:

| Table | Description |
|-------|-------------|
| `authors` | 연구자 정보 (이름, ORCID) |
| `author_aliases` | 저자 이름 변형 (동명이인 처리) |
| `organizations` | 기관/대학 정보 |
| `venues` | 학술지/컨퍼런스 |
| `works` | 논문 메타데이터 |
| `work_authors` | 논문-저자 연결 |
| `work_affiliations` | 논문-저자-기관 연결 |
| `keywords` | 키워드/개념 |
| `work_keywords` | 논문-키워드 연결 |
| `coauthor_edges` | 공저자 네트워크 엣지 |
| `org_edges` | 기관 협력 엣지 |
| `nation_edges` | 국가 협력 엣지 |
| `merges` | 엔티티 병합 로그 |

---

## 📊 Visualization Layers

| Layer | Nodes | Edges | Use Case |
|-------|-------|-------|----------|
| **Co-authorship** | 연구자 | 공동 논문 수 | 연구 협력 네트워크 분석 |
| **Keyword Co-occurrence** | 키워드 | 동시 출현 빈도 | 연구 주제 관계 파악 |
| **Institutional** | 기관 | 기관간 공동 연구 | 산학 협력 분석 |
| **National** | 국가 | 국제 공동 연구 | 글로벌 협력 패턴 |

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit, PyVis, Plotly
- **Backend:** FastAPI, Uvicorn
- **Database:** SQLite + SQLAlchemy ORM
- **Data Source:** OpenAlex API
- **Language:** Python 3.10+

---

## 📖 Documentation

자세한 문서는 `docs/` 폴더를 참조하세요:
- [Implementation Guide](docs/Implementation_Guide.md) — 구현 상세 가이드
- [User Manual](docs/User_manual.md) — 사용자 매뉴얼

---

## 🤝 Contributing

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
