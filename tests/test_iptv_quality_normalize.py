"""Tests de normalize_iptv_quality."""

from iptv_quality import normalize_iptv_quality


def test_normalize_iptv_quality_snaps_to_known_heights():
    """Valores intermedios se redondean a resoluciones IPTV estándar."""
    assert normalize_iptv_quality(0) == 0
    assert normalize_iptv_quality('mejor') == 0
    assert normalize_iptv_quality(400) == 480
    assert normalize_iptv_quality(900) == 1080
    assert normalize_iptv_quality(1500) == 2160
