"""i18n + CJK-font helper unit tests."""
from __future__ import annotations

from app import i18n
from app.fonts import configure_matplotlib


def test_english_is_default():
    assert i18n.t("app.title") == "Relatenta"


def test_korean_translation_present():
    assert i18n.t("tabs.graph", lang="ko") == "그래프"
    assert i18n.t("btn.build_graph", lang="ko") == "그래프 생성"


def test_unknown_key_returns_key_itself():
    # Missing keys should be safe — they fall back to the key string so the
    # UI keeps rendering instead of crashing.
    assert i18n.t("does.not.exist") == "does.not.exist"


def test_unknown_language_falls_back_to_english():
    assert i18n.t("tabs.graph", lang="zz") == "Graph"


def test_every_english_key_has_korean_translation():
    en_keys = set(i18n._TRANSLATIONS["en"].keys())
    ko_keys = set(i18n._TRANSLATIONS["ko"].keys())
    missing = en_keys - ko_keys
    assert not missing, f"Missing Korean translations: {sorted(missing)}"


def test_configure_matplotlib_is_safe_without_cjk_font():
    # In CI most images don't ship CJK fonts. The helper must just return None
    # rather than crashing — that's all we assert here.
    result = configure_matplotlib()
    assert result is None or isinstance(result, str)
