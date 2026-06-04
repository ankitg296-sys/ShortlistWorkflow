import re
import unicodedata


def normalise(raw: str) -> str:
    """
    Clean raw extracted CV text:
    - Remove null bytes and non-printable control characters (newlines/tabs kept)
    - Normalise line endings to \\n
    - Strip trailing whitespace from each line
    - Collapse 3+ consecutive blank lines → 1 blank line
    - Strip leading/trailing whitespace from the whole string
    """
    if not raw:
        return ""

    # Remove control characters except newline, carriage return, tab
    cleaned = "".join(
        ch for ch in raw
        if ch in ("\n", "\r", "\t") or not unicodedata.category(ch).startswith("C")
    )

    # Normalise line endings
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    # Strip trailing whitespace from each line (preserve leading — some CVs use indentation)
    lines = [line.rstrip() for line in cleaned.split("\n")]

    # Collapse 3+ blank lines → 1 blank line
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))

    return result.strip()
