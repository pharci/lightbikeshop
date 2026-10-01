import re


def normalize_brand_title(value: str) -> str:
    """Return the catalog spelling for known brand aliases."""
    title = re.sub(r"\s+", " ", (value or "").strip())
    if re.sub(r"[\s_-]+", "", title).casefold() == "nkbmx":
        return "NKBMX"
    return title
