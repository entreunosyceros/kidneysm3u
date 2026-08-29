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
)


def test_normalize_hex_color_short_and_invalid():
    assert normalize_hex_color('#abc') == '#AABBCC'
    assert normalize_hex_color('fff') == '#FFFFFF'
    assert normalize_hex_color('nope', '#123456') == '#123456'


def test_hex_to_vlc_white_and_red():
    assert hex_to_vlc_color('#FFFFFF') == 16777215
    assert hex_to_vlc_color('#FF0000') == 16711680


def test_normalize_snaps_size_and_clamps_delay():
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
    style = normalize_subtitle_style({
        'subtitle_size': 32,
        'subtitle_color': '#FFFF00',
        'subtitle_bg_opacity': 128,
        'subtitle_outline': 2,
        'subtitle_margin': 20,
    })
    options = vlc_media_options(style)
    assert ':freetype-rel-fontsize=12' in options
    assert ':freetype-color=16776960' in options
    assert ':freetype-background-opacity=128' in options
    assert ':freetype-outline-thickness=6' in options
    assert ':sub-margin=' not in ' '.join(options)
    assert ':sub-delay=' not in ' '.join(options)
    instance = vlc_instance_args(style)
    assert '--freetype-rel-fontsize=12' in instance
    local = vlc_media_options(style, prefix='')
    assert 'freetype-rel-fontsize=12' in local


def test_vlc_rel_fontsize_and_outline_mapping():
    assert vlc_rel_fontsize(0) == 0
    assert vlc_rel_fontsize(18) == 18
    assert vlc_rel_fontsize(24) == 16
    assert vlc_rel_fontsize(32) == 12
    assert vlc_rel_fontsize(44) == 6
    assert vlc_outline_thickness(0) == 0
    assert vlc_outline_thickness(1) == 2
    assert vlc_outline_thickness(2) == 6


def test_nearest_vlc_palette_color():
    assert nearest_vlc_palette_color('#FFFFFF') == 16777215
    assert nearest_vlc_palette_color('#FF0000') == 16711680
    assert nearest_vlc_palette_color('#00FF00') == 65280


def test_fingerprint_changes_with_size():
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
