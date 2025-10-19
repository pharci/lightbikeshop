# core/sanitize.py
import nh3

ALLOWED_TAGS = {"p", "br"}          # только абзацы и переносы
ALLOWED_ATTRS: dict[str, set[str]] = {}

def clean_html(html: str) -> str:
    return nh3.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        url_schemes={"http", "https", "mailto"},
    )