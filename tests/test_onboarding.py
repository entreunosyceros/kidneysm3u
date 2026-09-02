"""Pruebas del asistente de primer arranque."""

import json

import app_config
import onboarding


def _isolate_config(tmp_path, monkeypatch):
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    return previous


def test_needs_onboarding_without_config(tmp_path, monkeypatch):
    """Sin config.json debe pedir el asistente."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.needs_onboarding() is True
    finally:
        app_config._cache = previous


def test_needs_onboarding_legacy_config_without_flag(tmp_path, monkeypatch):
    """Config antigua sin la clave no debe forzar el asistente."""
    previous = _isolate_config(tmp_path, monkeypatch)
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps({'theme': 'dark'}), encoding='utf-8')
    try:
        assert app_config.needs_onboarding() is False
    finally:
        app_config._cache = previous


def test_needs_onboarding_explicit_false(tmp_path, monkeypatch):
    """onboarding_completed=false debe mostrar el asistente."""
    previous = _isolate_config(tmp_path, monkeypatch)
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps({'onboarding_completed': False}), encoding='utf-8')
    try:
        assert app_config.needs_onboarding() is True
    finally:
        app_config._cache = previous


def test_set_onboarding_completed(tmp_path, monkeypatch):
    """Marcar completado debe persistir en config.json."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.set_onboarding_completed(True)
        raw = json.loads((tmp_path / 'config.json').read_text(encoding='utf-8'))
        assert raw['onboarding_completed'] is True
        assert app_config.needs_onboarding() is False
    finally:
        app_config._cache = previous


def test_check_data_directory_ok(tmp_path, monkeypatch):
    """Carpeta escribible debe reportar OK."""
    monkeypatch.setattr(onboarding, 'data_dir', lambda: str(tmp_path))
    result = onboarding.check_data_directory()
    assert result['status'] == 'ok'
    assert str(tmp_path) in result['detail']


def test_check_ffmpeg_missing(monkeypatch):
    """Sin ffmpeg en PATH debe ser aviso."""
    monkeypatch.setattr(onboarding, 'find_executable', lambda name: None)
    result = onboarding.check_ffmpeg()
    assert result['status'] == 'warn'


def test_check_ffmpeg_present(monkeypatch):
    """Con ffmpeg disponible debe ser OK."""
    monkeypatch.setattr(onboarding, 'find_executable', lambda name: '/usr/bin/ffmpeg')
    result = onboarding.check_ffmpeg()
    assert result['status'] == 'ok'


def test_find_executable_windows_path(monkeypatch, tmp_path):
    """En Windows busca ffmpeg.exe en rutas habituales."""
    ffmpeg_dir = tmp_path / 'ffmpeg' / 'bin'
    ffmpeg_dir.mkdir(parents=True)
    ffmpeg_exe = ffmpeg_dir / 'ffmpeg.exe'
    ffmpeg_exe.write_text('', encoding='utf-8')

    monkeypatch.setattr(onboarding.sys, 'platform', 'win32')
    monkeypatch.setattr(onboarding.shutil, 'which', lambda name: None)
    monkeypatch.setattr(onboarding, '_windows_program_dirs', lambda: [str(tmp_path)])

    assert onboarding.find_executable('ffmpeg') == str(ffmpeg_exe)


def test_platform_install_hint_windows(monkeypatch):
    """Las pistas de instalación mencionan PATH en Windows."""
    monkeypatch.setattr(onboarding.sys, 'platform', 'win32')
    hint = onboarding._platform_install_hint('vlc')
    assert 'PATH' in hint
    assert 'VideoLAN' in hint


def test_platform_install_hint_linux(monkeypatch):
    """Las pistas de instalación mencionan apt en Linux."""
    monkeypatch.setattr(onboarding.sys, 'platform', 'linux')
    hint = onboarding._platform_install_hint('vlc')
    assert 'apt install' in hint


def test_session_cookie_hint_windows(monkeypatch):
    """En Windows advierte sobre Chrome/Edge."""
    monkeypatch.setattr(onboarding.sys, 'platform', 'win32')
    hint = onboarding._session_cookie_hint()
    assert 'Firefox' in hint
    assert 'Chrome' in hint or 'Edge' in hint


def test_check_twitch_chat_windows(monkeypatch):
    """En Windows se comprueba pywebview, no WebKitGTK."""
    monkeypatch.setattr(onboarding.sys, 'platform', 'win32')
    monkeypatch.setattr(onboarding, 'platform_name', lambda: 'Windows')
    result = onboarding.check_twitch_chat()
    assert result is not None
    assert result['title'] == 'Chat Twitch'


def test_run_environment_checks_includes_core(monkeypatch):
    """Las comprobaciones básicas incluyen plataforma, datos, VLC, ffmpeg y yt-dlp."""
    monkeypatch.setattr(onboarding, 'check_platform', lambda: {'status': 'ok', 'title': 'platform'})
    monkeypatch.setattr(onboarding, 'check_data_directory', lambda: {'status': 'ok', 'title': 'data'})
    monkeypatch.setattr(onboarding, 'check_vlc', lambda: {'status': 'ok', 'title': 'vlc'})
    monkeypatch.setattr(onboarding, 'check_ffmpeg', lambda: {'status': 'warn', 'title': 'ffmpeg'})
    monkeypatch.setattr(onboarding, 'check_yt_dlp', lambda: {'status': 'ok', 'title': 'yt-dlp'})
    monkeypatch.setattr(onboarding, 'check_twitch_chat', lambda: None)
    checks = onboarding.run_environment_checks(include_sessions=False)
    titles = [c['title'] for c in checks]
    assert titles == ['platform', 'data', 'vlc', 'ffmpeg', 'yt-dlp']
