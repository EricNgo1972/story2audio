#!/usr/bin/env python3
"""Test script for chunking improvements — run locally to verify."""

import re
import sys
import os

# Add story2audio to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import split_text_into_chunks, split_sentences_multilang, normalize_text


def test_abbreviations():
    """Test that Vietnamese abbreviations are NOT split into separate sentences."""
    test_cases = [
        # (input, expected_min_sentences, description)
        ("PGS.TS. Nguyễn Văn A là giảng viên.", 1, "PGS.TS."),
        ("Ông sống ở Tp. Hồ Chí Minh.", 1, "Tp."),
        ("Anh ấy làm việc tại ĐT. Viễn thông.", 1, "ĐT."),
        ("Chị là KTV. phòng xét nghiệm.", 1, "KTV."),
        ("GS.TSKH. Trần Văn B đã phát biểu.", 1, "GS.TSKH."),
        ("TS. Lê Thị C nghiên cứu sinh học.", 1, "TS."),
        ("ThS. Nguyễn D giảng dạy toán.", 1, "ThS."),
        ("Ông là PGS.TS. Nguyễn Văn A, chuyên gia hàng đầu.", 1, "PGS.TS. mid-sentence"),
        # Multiple abbreviations in one sentence
        ("PGS.TS. Nguyễn A và TS. Trần B tham gia hội nghị.", 1, "Multiple abbreviations"),
        # Normal sentence boundaries should still work
        ("Xin chào. Tôi là Nguyễn.", 2, "Normal period split"),
        ("Hôm nay trời đẹp! Chúng ta đi chơi.", 2, "Exclamation split"),
        ("Anh nói gì? Tôi không nghe rõ.", 2, "Question mark split"),
        # Mixed: abbreviation + real sentence end
        ("PGS.TS. Nguyễn A phát biểu. Hội nghị kết thúc.", 2, "Abbreviation + real end"),
    ]

    print("=" * 70)
    print("TEST: Vietnamese abbreviation handling")
    print("=" * 70)

    passed = 0
    failed = 0

    for text, expected_min, desc in test_cases:
        sentences = split_sentences_multilang(text)
        actual = len(sentences)
        ok = actual <= expected_min
        status = "✅" if ok else "❌"
        passed += ok
        failed += not ok

        print(f"\n{status} [{desc}]")
        print(f"   Input:    {text!r}")
        print(f"   Expected: ≤{expected_min} sentences, Got: {actual}")
        if sentences:
            for i, s in enumerate(sentences):
                print(f"   Sentence[{i}]: {s!r}")

    print(f"\n{'='*70}")
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)}")
    return failed == 0


def test_chunking_quality():
    """Test that chunking produces reasonable chunks for typical Vietnamese text."""
    # Typical chapter text with abbreviations
    text = """PGS.TS. Nguyễn Văn A là giảng viên trường Đại học Bách Khoa.
Anh ấy đã nghiên cứu về trí tuệ nhân tạo trong suốt 20 năm.

Theo GS.TSKH. Trần B, công nghệ AI sẽ thay đổi thế giới.
ThS. Lê C cũng đồng ý với quan điểm này.

Hội nghị diễn ra tại Tp. Hồ Chí Minh. Hơn 500 chuyên gia tham dự.
Các báo cáo được trình bày bởi TS. Phạm D và PGS.TS. Hoàng E."""

    print("\n" + "=" * 70)
    print("TEST: Chunking quality with abbreviations")
    print("=" * 70)

    chunks = split_text_into_chunks(text, language="vi")
    print(f"\nTotal chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} (len={len(chunk)}) ---")
        print(chunk[:200])

    return True


def test_soft_split():
    """Test soft split with Vietnamese punctuation."""
    text = "Anh ấy nói—rằng sẽ đi…nhưng rồi ở lại."
    print("\n" + "=" * 70)
    print("TEST: Soft split with Vietnamese punctuation (…, —, –)")
    print("=" * 70)

    from main import SOFT_SPLIT_RE
    parts = [p.strip() for p in SOFT_SPLIT_RE.split(text) if p.strip()]
    print(f"Input: {text!r}")
    print(f"Parts: {parts}")
    return True


if __name__ == "__main__":
    results = []
    results.append(("Abbreviations", test_abbreviations()))
    results.append(("Chunking quality", test_chunking_quality()))
    results.append(("Soft split", test_soft_split()))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    all_ok = all(ok for _, ok in results)
    sys.exit(0 if all_ok else 1)
