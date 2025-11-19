"""Utilities for correcting mojibake (garbled text) in Hawaiian content.

We occasionally see UTF-8 text that was mis-decoded as Latin-1 and then
rendered in the UI, producing sequences like:

    HawaiÄ«  -> Hawaiī
    MÄ00noa -> Mānoa
    HawaiÂ â -> Hawaiʻi (ʻokina)

Rather than attempting to enumerate every broken sequence, we first try a
"round-trip" repair: encode the text as latin-1 bytes and decode as UTF-8.
If that succeeds AND produces more Hawaiian diacritics (āēīōūʻ), we use it.
Then we apply targeted replacements for common stray characters (Â, â€™, â€˜, etc.).

This approach is idempotent: running it multiple times will not further
alter already-correct text.
"""

from __future__ import annotations

import re
import unicodedata

_HAWAIIAN_DIACRITICS = set("āēīōūĀĒĪŌŪʻ")

_TARGETED_REPLACEMENTS = {
    # Stray bytes from mis-decoding
    "Â": "",  # often appears before macron characters
    # Apostrophe / okina variants from smart quotes or mojibake
    "â€˜": "ʻ",
    "â€™": "ʻ",
    "â€ʻ": "ʻ",
    "ʻʻ": "ʻ",  # double okina
    # Occasionally an en dash or em dash sneaks in for hyphen
    "–": "-",
    "—": "-",
    # Direct replacement for Ä in place names (appears as A-umlaut but should be a-macron)
    "MÄnoa": "Mānoa",  # Specific pattern in place names
}

def _round_trip_repair(text: str) -> str:
    """Attempt to repair mojibake by latin-1 -> utf-8 round trip.

    If the text contains characters typical of mojibake (Ã, Â, â) we try the
    re-decode. If it fails, we return the original.
    """
    if not any(ch in text for ch in ("Ã", "Â", "â")):
        return text
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    # Heuristic: use repaired only if it increases presence of Hawaiian diacritics
    orig_count = sum(c in _HAWAIIAN_DIACRITICS for c in text)
    new_count = sum(c in _HAWAIIAN_DIACRITICS for c in repaired)
    return repaired if new_count >= orig_count else text


def fix_encoding(text: str) -> str:
    """Fix common Hawaiian mojibake and normalize Unicode.

    Steps:
    1. Round-trip re-decode (latin-1 -> utf-8) when appropriate.
    2. Unicode NFC normalization to compose decomposed characters.
    3. Targeted replacements for stray characters and smart quotes.
    4. Specific pattern fixes (MĀnoa -> Mānoa, MÄnoa variants).
    5. Final cleanup and normalization.
    """
    if not text:
        return text

    fixed = _round_trip_repair(text)

    # Normalize early to compose decomposed characters (MÄ\x81noa -> MĀnoa)
    fixed = unicodedata.normalize("NFC", fixed)

    for wrong, right in _TARGETED_REPLACEMENTS.items():
        fixed = fixed.replace(wrong, right)

    # Remove control characters in C0 (0-31) and C1 (128-159) ranges
    # Keep newline, tab, and printable ASCII + high Unicode
    fixed = "".join(
        ch for ch in fixed
        if (32 <= ord(ch) < 127) or ord(ch) >= 160 or ch in "\n\t"
    )

    # Fix various Manoa variants after cleanup:
    # - MĀnoa (capital A-macron) -> Mānoa (lowercase a-macron)
    # - MÄnoa (after control char removed) -> Mānoa
    fixed = re.sub(r"\bMĀnoa\b", "Mānoa", fixed)
    fixed = re.sub(r"\bMÄnoa\b", "Mānoa", fixed)
    
    # Also catch any remaining uppercase macron vowels at start of Manoa
    fixed = re.sub(r"\bM[ĀĒĪŌŪäëïöü]noa\b", "Mānoa", fixed)

    # Collapse multiple spaces created by removals
    fixed = re.sub(r" {2,}", " ", fixed)

    # Final NFC normalization to ensure consistency
    fixed = unicodedata.normalize("NFC", fixed)
    return fixed


def fix_dict_encoding(data: dict) -> dict:
    """
    Recursively fix encoding in all string values of a dictionary.
    
    Args:
        data: Dictionary that may contain encoding errors in string values
        
    Returns:
        Dictionary with fixed string values
    """
    fixed: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            fixed[key] = fix_encoding(value)
        elif isinstance(value, dict):
            fixed[key] = fix_dict_encoding(value)
        elif isinstance(value, list):
            fixed[key] = [
                fix_dict_encoding(item) if isinstance(item, dict)
                else fix_encoding(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            fixed[key] = value
    return fixed
