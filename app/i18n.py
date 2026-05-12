"""Minimal i18n for Relatenta.

Goal: translate the entry-point strings a first-time user sees (tabs,
sidebar headers, primary CTAs, empty states, warnings) into Korean while
leaving algorithm descriptions and table headers in English — those follow
established academic vocabulary, so translating them adds friction instead
of removing it.

Usage:

    from app.i18n import t, set_language

    st.title(t("app.title"))

The active language is stored in ``st.session_state["language"]`` and defaults
to ``"en"``. ``t(key)`` returns the English string when no translation is
found, so it is safe to introduce new keys without breaking other languages.
"""
from __future__ import annotations

SUPPORTED_LANGUAGES = ("en", "ko")
DEFAULT_LANGUAGE = "en"

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app.title": "Relatenta",
        "app.subtitle": "Research Relationship Visualization",
        "lang.label": "Language",

        # Tabs
        "tabs.graph": "Graph",
        "tabs.heatmaps": "Heatmaps",
        "tabs.report": "Report",
        "tabs.insights": "Insights",
        "tabs.how_to_use": "How to Use",

        # Sidebar
        "sidebar.database": "Database",
        "sidebar.search": "Search",
        "sidebar.csv_import": "CSV Import",
        "sidebar.restore": "Restore from Export",

        # Buttons
        "btn.search": "Search",
        "btn.ingest_selected": "Ingest Selected",
        "btn.import_csv": "Import CSV",
        "btn.restore": "Restore Data",
        "btn.export_csv": "Export CSV",
        "btn.clear_all": "Clear All",
        "btn.start_fresh": "Start Fresh",
        "btn.build_graph": "Build Graph",
        "btn.compute_heatmap": "Compute Heatmap",
        "btn.generate_report": "Generate Report",
        "btn.generate_pdf": "Generate PDF",
        "btn.download_pdf": "Download PDF",

        # Empty state
        "empty.title": "Nothing to show yet",
        "empty.body": (
            "Pick a starting point below or use the **Search** field in the sidebar "
            "to enter your own researcher, ORCID, or Google Scholar URL."
        ),
        "empty.tip": (
            "Tip: refine with year range, edge weight, and Focus filters once data is loaded."
        ),

        # Warning banner
        "warn.in_memory_title": "Data is held in memory only.",
        "warn.in_memory_body": (
            "Click **Export CSV** below before closing the tab — a browser refresh "
            "or session timeout will erase everything."
        ),
    },
    "ko": {
        "app.title": "Relatenta",
        "app.subtitle": "연구 관계 시각화",
        "lang.label": "언어",

        # Tabs
        "tabs.graph": "그래프",
        "tabs.heatmaps": "히트맵",
        "tabs.report": "리포트",
        "tabs.insights": "인사이트",
        "tabs.how_to_use": "사용 안내",

        # Sidebar
        "sidebar.database": "데이터베이스",
        "sidebar.search": "검색",
        "sidebar.csv_import": "CSV 가져오기",
        "sidebar.restore": "백업 복원",

        # Buttons
        "btn.search": "검색",
        "btn.ingest_selected": "선택 항목 수집",
        "btn.import_csv": "CSV 불러오기",
        "btn.restore": "데이터 복원",
        "btn.export_csv": "CSV 내보내기",
        "btn.clear_all": "전체 삭제",
        "btn.start_fresh": "새로 시작",
        "btn.build_graph": "그래프 생성",
        "btn.compute_heatmap": "히트맵 계산",
        "btn.generate_report": "리포트 생성",
        "btn.generate_pdf": "PDF 만들기",
        "btn.download_pdf": "PDF 다운로드",

        # Empty state
        "empty.title": "아직 표시할 데이터가 없습니다",
        "empty.body": (
            "아래에서 시작점을 고르거나, 사이드바 **검색** 입력란에 직접 연구자 이름, "
            "ORCID, 또는 Google Scholar URL을 입력하세요."
        ),
        "empty.tip": (
            "데이터를 불러온 뒤 연도 범위, 엣지 가중치, Focus 필터로 더 세밀하게 조정할 수 있습니다."
        ),

        # Warning banner
        "warn.in_memory_title": "데이터는 메모리에만 저장됩니다.",
        "warn.in_memory_body": (
            "탭을 닫기 전에 아래 **CSV 내보내기**를 눌러 저장하세요. "
            "브라우저를 새로고침하거나 세션이 만료되면 모든 데이터가 사라집니다."
        ),
    },
}


def _current_language() -> str:
    try:
        import streamlit as st
        lang = st.session_state.get("language", DEFAULT_LANGUAGE)
        return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    except Exception:
        return DEFAULT_LANGUAGE


def set_language(lang: str) -> None:
    if lang not in SUPPORTED_LANGUAGES:
        return
    try:
        import streamlit as st
        st.session_state["language"] = lang
    except Exception:
        pass


def t(key: str, lang: str | None = None) -> str:
    """Translate ``key`` to the active language, falling back to English."""
    lang = lang or _current_language()
    table = _TRANSLATIONS.get(lang) or _TRANSLATIONS[DEFAULT_LANGUAGE]
    if key in table:
        return table[key]
    # Fallback: English text or the raw key for missing translations.
    return _TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
