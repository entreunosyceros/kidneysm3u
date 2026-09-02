"""Tests del modo ligero automático."""

import app_config
import light_mode_auto


def _isolate_config(tmp_path, monkeypatch):
    """Uso interno: config aislada."""
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    light_mode_auto.reset_auto_light_mode()
    return previous


def test_auto_light_mode_off_by_default(tmp_path, monkeypatch):
    """Sin lista grande ni CPU alta no activa el modo automático."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.save({'light_mode_auto': True, 'light_mode': False})
        active, reasons, changed = light_mode_auto.update_auto_light_mode(100, 20)
        assert active is False
        assert reasons == set()
        assert changed is False
        assert app_config.effective_light_mode() is False
    finally:
        app_config._cache = previous
        light_mode_auto.reset_auto_light_mode()


def test_auto_light_mode_large_list(tmp_path, monkeypatch):
    """Listas enormes activan el modo ligero automático."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.save({
            'light_mode_auto': True,
            'light_mode_auto_channels': 1500,
            'light_mode': False,
            'show_channel_logos': True,
        })
        active, reasons, changed = light_mode_auto.update_auto_light_mode(2000, None)
        assert active is True
        assert reasons == {'channels'}
        assert changed is True
        assert app_config.effective_light_mode() is True
        assert app_config.effective_show_channel_logos() is False
        assert app_config.epg_reload_interval_ms() == 0
    finally:
        app_config._cache = previous
        light_mode_auto.reset_auto_light_mode()


def test_auto_light_mode_cpu_hysteresis(tmp_path, monkeypatch):
    """La CPU alta requiere varias muestras seguidas."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.save({
            'light_mode_auto': True,
            'light_mode_auto_cpu': True,
            'light_mode_auto_cpu_percent': 85,
            'light_mode': False,
        })
        assert light_mode_auto.update_auto_light_mode(10, 90)[0] is False
        active, reasons, _changed = light_mode_auto.update_auto_light_mode(10, 90)
        assert active is True
        assert reasons == {'cpu'}
        assert 'CPU' in light_mode_auto.status_message(reasons)
    finally:
        app_config._cache = previous
        light_mode_auto.reset_auto_light_mode()


def test_manual_light_mode_disables_auto(tmp_path, monkeypatch):
    """El modo ligero manual anula el automático."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.save({'light_mode_auto': True, 'light_mode': False})
        light_mode_auto.update_auto_light_mode(5000, None)
        assert light_mode_auto.is_auto_light_mode_active() is True
        app_config.set_light_mode(True)
        active, reasons, changed = light_mode_auto.update_auto_light_mode(5000, 99)
        assert active is False
        assert changed is True
        assert app_config.effective_light_mode() is True
    finally:
        app_config._cache = previous
        light_mode_auto.reset_auto_light_mode()
