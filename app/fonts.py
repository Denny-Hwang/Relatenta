"""Matplotlib font helper for CJK-safe PDF output.

Matplotlib defaults to DejaVu Sans, which does not contain Hangul, CJK
ideographs, or many other non-Latin glyphs — every such character is then
rendered as the dreaded tofu (☐). This module scans the system font cache
once and, if it finds a font with broad CJK coverage, points matplotlib at
it via ``rcParams``.

We deliberately do NOT bundle a font file in the repo. Linux deployments
should install ``fonts-noto-cjk`` (Debian/Ubuntu) or equivalent; macOS and
Windows already ship CJK-capable fonts out of the box. If nothing is found
the function logs once and returns ``False`` so the caller can decide
whether to warn the user.
"""
from __future__ import annotations

from functools import lru_cache

# Ordered by preference: Noto is the most widely available cross-platform CJK
# font; the next entries cover macOS/Windows/Korean-specific defaults.
_CJK_CANDIDATES = (
    "Noto Sans CJK KR",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans KR",
    "Source Han Sans KR",
    "NanumGothic",
    "NanumBarunGothic",
    "Apple SD Gothic Neo",
    "AppleGothic",
    "Malgun Gothic",
    "Yu Gothic",
    "MS Gothic",
)


@lru_cache(maxsize=1)
def configure_matplotlib() -> str | None:
    """Pick the best available CJK font and apply it to matplotlib.

    Returns the chosen font family name, or ``None`` when no candidate is
    installed. The result is cached so multiple PDF exports in the same
    process don't re-scan the font directory.
    """
    try:
        import matplotlib
        from matplotlib import font_manager
    except Exception:
        return None

    installed = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((name for name in _CJK_CANDIDATES if name in installed), None)
    if not chosen:
        return None

    matplotlib.rcParams["font.family"] = [chosen, "DejaVu Sans"]
    # Minus sign would otherwise render as a Unicode minus that some CJK fonts
    # lack a glyph for; ASCII hyphen is a safer fallback.
    matplotlib.rcParams["axes.unicode_minus"] = False
    return chosen
