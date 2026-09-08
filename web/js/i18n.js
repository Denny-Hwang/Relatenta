/** Minimal i18n — port of app/i18n.py plus the extra strings the SPA needs. */

export const SUPPORTED_LANGUAGES = ["en", "ko"];
export const DEFAULT_LANGUAGE = "en";

const T = {
  en: {
    "app.title": "Relatenta",
    "app.subtitle": "Research Relationship Visualization",
    "lang.label": "Language",
    "tabs.graph": "Graph",
    "tabs.heatmaps": "Heatmaps",
    "tabs.report": "Report",
    "tabs.insights": "Insights",
    "tabs.how_to_use": "How to Use",
    "sidebar.database": "Database",
    "sidebar.search": "Search",
    "sidebar.csv_import": "CSV Import",
    "sidebar.restore": "Restore from Export",
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
    "empty.title": "Nothing to show yet",
    "empty.body": "Pick a starting point below or use the <b>Search</b> field in the sidebar to enter your own researcher name or ORCID.",
    "empty.tip": "Tip: refine with year range, edge weight, and Focus filters once data is loaded.",
    "warn.saved_title": "Data is saved in this browser.",
    "warn.saved_body": "Your dataset persists across refreshes (IndexedDB). Use <b>Export CSV</b> to share it or move it to the Streamlit app.",
    "demo.banner": "<b>Example:</b> Geoffrey Hinton's co-authorship network. Use the sidebar to search your own researchers, or click <b>Start Fresh</b> to begin a new analysis.",
    "demo.loading": "Loading example data (Geoffrey Hinton)…",
    "demo.failed": "Could not load example data automatically. Please search and ingest authors from the sidebar.",
    "search.placeholder": "e.g., Geoffrey Hinton / 0000-0001-…",
    "search.label": "Name or ORCID",
    "ingest.max_works": "Max works per author",
    "ingest.progress": "Ingesting data from OpenAlex…",
    "graph.title": "Network Graph",
    "graph.controls": "Graph Controls: hover for details | click a node to highlight its neighbours | scroll to zoom | SPACE toggles physics | F fits the view",
    "confirm.clear": "This will delete all data.",
    "confirm.clear_demo": "Clear example data and start a new analysis?",
    "settings.mailto": "OpenAlex polite-pool email (optional)",
  },
  ko: {
    "app.title": "Relatenta",
    "app.subtitle": "연구 관계 시각화",
    "lang.label": "언어",
    "tabs.graph": "그래프",
    "tabs.heatmaps": "히트맵",
    "tabs.report": "리포트",
    "tabs.insights": "인사이트",
    "tabs.how_to_use": "사용 안내",
    "sidebar.database": "데이터베이스",
    "sidebar.search": "검색",
    "sidebar.csv_import": "CSV 가져오기",
    "sidebar.restore": "백업 복원",
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
    "empty.title": "아직 표시할 데이터가 없습니다",
    "empty.body": "아래에서 시작점을 고르거나, 사이드바 <b>검색</b> 입력란에 직접 연구자 이름 또는 ORCID를 입력하세요.",
    "empty.tip": "데이터를 불러온 뒤 연도 범위, 엣지 가중치, Focus 필터로 더 세밀하게 조정할 수 있습니다.",
    "warn.saved_title": "데이터는 이 브라우저에 저장됩니다.",
    "warn.saved_body": "새로고침해도 데이터가 유지됩니다(IndexedDB). 공유하거나 Streamlit 앱으로 옮기려면 <b>CSV 내보내기</b>를 사용하세요.",
    "demo.banner": "<b>예시:</b> Geoffrey Hinton의 공저자 네트워크입니다. 사이드바에서 원하는 연구자를 검색하거나 <b>새로 시작</b>을 눌러 새 분석을 시작하세요.",
    "demo.loading": "예시 데이터(Geoffrey Hinton)를 불러오는 중…",
    "demo.failed": "예시 데이터를 자동으로 불러오지 못했습니다. 사이드바에서 연구자를 검색해 수집하세요.",
    "search.placeholder": "예: Geoffrey Hinton / 0000-0001-…",
    "search.label": "이름 또는 ORCID",
    "ingest.max_works": "연구자당 최대 논문 수",
    "ingest.progress": "OpenAlex에서 데이터를 수집하는 중…",
    "graph.title": "네트워크 그래프",
    "graph.controls": "조작법: 마우스를 올리면 상세 정보 | 노드를 클릭하면 이웃 강조 | 스크롤로 확대/축소 | SPACE로 물리 시뮬레이션 전환 | F로 화면 맞춤",
    "confirm.clear": "모든 데이터가 삭제됩니다.",
    "confirm.clear_demo": "예시 데이터를 지우고 새 분석을 시작할까요?",
    "settings.mailto": "OpenAlex polite pool 이메일 (선택)",
  },
};

let current = DEFAULT_LANGUAGE;
try {
  const saved = localStorage.getItem("relatenta.lang");
  if (saved && SUPPORTED_LANGUAGES.includes(saved)) current = saved;
} catch (e) { /* storage may be blocked */ }

export function getLanguage() { return current; }
export function setLanguage(lang) {
  if (!SUPPORTED_LANGUAGES.includes(lang)) return;
  current = lang;
  try { localStorage.setItem("relatenta.lang", lang); } catch (e) { /* ignore */ }
}
export function t(key, lang = null) {
  const table = T[lang || current] || T[DEFAULT_LANGUAGE];
  return table[key] ?? T[DEFAULT_LANGUAGE][key] ?? key;
}
/** Apply translations to every element carrying data-i18n / data-i18n-placeholder. */
export function applyTranslations(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => { el.innerHTML = t(el.dataset.i18n); });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
}
