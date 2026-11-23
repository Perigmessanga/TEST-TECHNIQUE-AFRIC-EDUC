from app.main import fallback_summary, validate_summary


def test_fallback_uses_only_calculated_counts():
    counts = {"eleves": 18, "present": 16, "retards": 2, "sorties_hors_plage": 1}
    text = fallback_summary(counts)
    assert "18" in text and "16" in text and "2" in text and "1" in text
    assert validate_summary(text, counts)


def test_summary_rejects_unexpected_numbers():
    counts = {"eleves": 5, "present": 4, "retards": 1, "sorties_hors_plage": 0}
    assert not validate_summary("12 élèves sont présents", counts)
