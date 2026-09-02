"""Módulo de test subtitle style."""

from subtitle_style import (
    delay_label,
    hex_to_vlc_color,
    nearest_vlc_palette_color,
    normalize_hex_color,
    normalize_subtitle_style,
    opacity_percent,
    percent_to_opacity,
    vlc_instance_args,
    vlc_media_options,
    vlc_outline_thickness,
    vlc_rel_fontsize,
    vlc_text_scale,
)


def test_normalize_hex_color_short_and_invalid():
    """Prueba normalize hex color short and invalid."""
    assert normalize_hex_color('#abc') == '#AABBCC'
    assert normalize_hex_color('fff') == '#FFFFFF'
    assert normalize_hex_color('nope', '#123456') == '#123456'


def test_hex_to_vlc_white_and_red():
    """Prueba hex to VLC white and red."""
    assert hex_to_vlc_color('#FFFFFF') == 16777215
    assert hex_to_vlc_color('#FF0000') == 16711680


def test_normalize_snaps_size_and_clamps_delay():
    """Prueba normalize snaps size and clamps delay."""
    style = normalize_subtitle_style({
        'subtitle_size': 20,
        'subtitle_delay_ds': 99,
        'subtitle_bg_opacity': -3,
        'subtitle_opacity': 10,
    })
    assert style['subtitle_size'] == 18
    assert style['subtitle_delay_ds'] == 50
    assert style['subtitle_bg_opacity'] == 0
    assert style['subtitle_opacity'] == 40


def test_vlc_media_options_use_vlc3_freetype_names():
    """El estilo freetype va en libvlc_new; sub-text-scale complementa el tamaño."""
    style = normalize_subtitle_style({
        'subtitle_size': 32,
        'subtitle_color': '#FFFF00',
        'subtitle_bg_opacity': 128,
        'subtitle_outline': 2,
        'subtitle_margin': 20,
    })
    assert vlc_media_options(style) == []
    instance = vlc_instance_args(style)
    assert '--freetype-rel-fontsize=12' in instance
    assert '--sub-text-scale=130' in instance
    assert '--freetype-color=16776960' in instance
    assert '--freetype-background-opacity=128' in instance
    assert '--freetype-outline-thickness=6' in instance


def test_vlc_rel_fontsize_and_outline_mapping():
    """Prueba VLC rel fontsize and outline mapping."""
    assert vlc_rel_fontsize(0) == 0
    assert vlc_rel_fontsize(18) == 18
    assert vlc_rel_fontsize(24) == 16
    assert vlc_rel_fontsize(32) == 12
    assert vlc_rel_fontsize(44) == 6
    assert vlc_outline_thickness(0) == 0
    assert vlc_outline_thickness(1) == 2
    assert vlc_outline_thickness(2) == 6
    assert vlc_text_scale(32) == 130
    assert vlc_text_scale(0) == 0


def test_nearest_vlc_palette_color():
    """Prueba nearest VLC palette color."""
    assert nearest_vlc_palette_color('#FFFFFF') == 16777215
    assert nearest_vlc_palette_color('#FF0000') == 16711680
    assert nearest_vlc_palette_color('#00FF00') == 65280


def test_fingerprint_changes_with_size():
    """Prueba fingerprint changes with size."""
    from subtitle_style import fingerprint, normalize_subtitle_style
    a = fingerprint(normalize_subtitle_style({'subtitle_size': 0}))
    b = fingerprint(normalize_subtitle_style({'subtitle_size': 32}))
    assert a != b
    assert opacity_percent(255) == 100
    assert opacity_percent(0) == 0
    assert percent_to_opacity(100) == 255
    assert delay_label(0) == '0,0 s'
    assert delay_label(12) == '+1,2 s'
    assert delay_label(-8) == '-0,8 s'
