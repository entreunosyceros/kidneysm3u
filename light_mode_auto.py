"""Modo ligero automático: listas grandes o CPU alta (sesión, no persiste)."""

import app_config

CPU_HIGH_SAMPLES = 2
CPU_LOW_SAMPLES = 3

_state = {
    'active': False,
    'reasons': set(),
    'channel_latch': False,
    'cpu_high_streak': 0,
    'cpu_low_streak': 0,
}


def reset_auto_light_mode():
    """Reinicia el estado de sesión del modo ligero automático."""
    _state['active'] = False
    _state['reasons'] = set()
    _state['channel_latch'] = False
    _state['cpu_high_streak'] = 0
    _state['cpu_low_streak'] = 0


def is_auto_light_mode_active():
    """True si el modo ligero automático está activo en esta sesión."""
    return bool(_state['active'])


def auto_light_mode_reasons():
    """Conjunto de motivos activos: channels, cpu."""
    return set(_state['reasons'])


def status_message(reasons=None):
    """Texto breve para la barra de estado del reproductor."""
    reasons = set(reasons if reasons is not None else _state['reasons'])
    if 'channels' in reasons and 'cpu' in reasons:
        return 'Modo ligero automático (lista grande y CPU alta)'
    if 'channels' in reasons:
        threshold = app_config.get_light_mode_auto_channels()
        return f'Modo ligero automático (más de {threshold} canales)'
    if 'cpu' in reasons:
        return f'Modo ligero automático (CPU ≥ {app_config.get_light_mode_auto_cpu_percent()} %)'
    return 'Modo ligero automático'


def _channel_auto_active(channel_count, threshold):
    """Histéresis: activa al superar el umbral; desactiva al bajar del 80 %."""
    count = max(0, int(channel_count or 0))
    threshold = max(1, int(threshold or app_config.LIGHT_MODE_SESSION_MAX))
    release = max(1, int(threshold * 0.8))
    if count >= threshold:
        _state['channel_latch'] = True
    elif count < release:
        _state['channel_latch'] = False
    return bool(_state['channel_latch'])


def _cpu_auto_active(cpu_percent):
    """CPU alta durante varias muestras seguidas; baja tras varias lecturas normales."""
    if cpu_percent is None:
        return 'cpu' in _state['reasons']
    try:
        sample = float(cpu_percent)
    except (TypeError, ValueError):
        return 'cpu' in _state['reasons']
    limit = app_config.get_light_mode_auto_cpu_percent()
    if sample >= limit:
        _state['cpu_high_streak'] += 1
        _state['cpu_low_streak'] = 0
    else:
        _state['cpu_low_streak'] += 1
        _state['cpu_high_streak'] = 0
    if _state['cpu_high_streak'] >= CPU_HIGH_SAMPLES:
        return True
    if 'cpu' in _state['reasons'] and _state['cpu_low_streak'] < CPU_LOW_SAMPLES:
        return True
    return False


def update_auto_light_mode(channel_count=0, cpu_percent=None):
    """Actualiza el modo ligero automático. Devuelve (activo, motivos, cambió)."""
    if not app_config.get_light_mode_auto() or app_config.get_light_mode():
        previous = bool(_state['active'])
        reset_auto_light_mode()
        return False, set(), previous

    reasons = set()
    threshold = app_config.get_light_mode_auto_channels()
    if _channel_auto_active(channel_count, threshold):
        reasons.add('channels')
    if app_config.get_light_mode_auto_cpu():
        if _cpu_auto_active(cpu_percent):
            reasons.add('cpu')

    new_active = bool(reasons)
    changed = new_active != bool(_state['active']) or reasons != set(_state['reasons'])
    _state['active'] = new_active
    _state['reasons'] = reasons
    if not new_active:
        _state['channel_latch'] = False
    return new_active, set(reasons), changed
