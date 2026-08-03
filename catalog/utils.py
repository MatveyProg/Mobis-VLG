import re


def normalize_code(value: str) -> str:
    """Remove spaces, hyphens and lowercase for SKU / cross-number search."""
    if not value:
        return ''
    return re.sub(r'[\s\-]+', '', value).lower()
