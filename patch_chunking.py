#!/usr/bin/env python3
"""Patch story2audio/main.py with chunking improvements."""

import re

FILE = "/home/z/my-project/story2audio/main.py"

with open(FILE, "r", encoding="utf-8") as f:
    content = f.read()

# =====================================================================
# 1. Add Vietnamese abbreviation protection + update SOFT_SPLIT_RE
# =====================================================================

# Replace SOFT_SPLIT_RE line: add … – — to soft split characters
old_soft = r'''SOFT_SPLIT_RE = re.compile(r"(?<=[,;:，、；：])")'''
new_soft = r'''SOFT_SPLIT_RE = re.compile(r"(?<=[,;:…–—，、；：])")'''
content = content.replace(old_soft, new_soft)

# Find the line after SENTENCE_END_RE and add abbreviation protection block
old_sent_end = '''SENTENCE_END_RE = re.compile(r"[.!?…。！？]["'"'»」』）】]*$")'''

abbrev_block = '''SENTENCE_END_RE = re.compile(r"[.!?…。！？]["'"'»」』）】]*$")

# ---------------------------------------------------------------------------
# Vietnamese abbreviation protection
# ---------------------------------------------------------------------------
# These patterns match Vietnamese abbreviations where a period should NOT
# be treated as a sentence boundary. We temporarily replace the period with
# a null byte (\\x00) before sentence-splitting, then restore after.
VI_ABBREV_PATTERNS = [
    # Compound titles: PGS.TS.  GS.TSKH.  etc.
    # Match: (WORD1).(WORD2).  where each word is 2-5 uppercase letters
    (re.compile(r"\\b([A-ZĐ]{2,5})\\.([A-ZĐ]{2,5})\\."), r"\\1\\x00\\2\\x00"),
    # Single abbreviation + period + space + capital letter (likely a name)
    # e.g. "TS. Nguyễn", "Tp. Hồ", "ThS. Lê"
    (re.compile(r"\\b([A-ZĐ]{2,5})\\.\\s+(?=[A-ZĐÀ-Ỹ])"), r"\\1\\x00 "),
    # Single abbreviation + period + comma/semicolon/newline
    # e.g. "TS., ", "PGS.\\n"
    (re.compile(r"\\b([A-ZĐ]{2,5})\\.(?=[,;\\n])"), r"\\1\\x00"),
]

# Restore pattern: turn \\x00 back into period
_ABBREV_RESTORE_RE = re.compile(r"\\x00")'''

content = content.replace(old_sent_end, abbrev_block)

# =====================================================================
# 2. Update split_sentences_multilang to use abbreviation protection
# =====================================================================

old_split_fn = '''def split_sentences_multilang(text: str) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    matches = [m.group().strip() for m in MULTILANG_SENTENCE_RE.finditer(text)]
    sentences = [s for s in matches if s]
    return sentences or [text]'''

new_split_fn = '''def _protect_abbreviations(text: str) -> str:
    """Replace periods in Vietnamese abbreviations with null byte to prevent
    sentence splitting at abbreviation boundaries."""
    for pattern, replacement in VI_ABBREV_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _restore_abbreviations(text: str) -> str:
    """Restore null bytes back to periods after sentence splitting."""
    return _ABBREV_RESTORE_RE.sub(".", text)


def split_sentences_multilang(text: str) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    # Protect abbreviation periods before splitting
    text = _protect_abbreviations(text)
    matches = [m.group().strip() for m in MULTILANG_SENTENCE_RE.finditer(text)]
    sentences = [_restore_abbreviations(s) for s in matches if s]
    return sentences or [_restore_abbreviations(text)]'''

content = content.replace(old_split_fn, new_split_fn)

with open(FILE, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Patch applied successfully!")
print(f"   - SOFT_SPLIT_RE: added … – —")
print(f"   - VI_ABBREV_PATTERNS: added abbreviation protection")
print(f"   - split_sentences_multilang: added protect/restore")
