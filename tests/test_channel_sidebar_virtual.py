"""Tests de umbrales de virtualización de la barra lateral."""

from channel_sidebar import VIRTUAL_MIN, VIRTUAL_MIN_WHEN_FILTERED


def test_virtual_thresholds():
    """Con filtro el umbral de virtualización es más bajo."""
    assert VIRTUAL_MIN == 1200
    assert VIRTUAL_MIN_WHEN_FILTERED == 600
    assert VIRTUAL_MIN_WHEN_FILTERED < VIRTUAL_MIN
