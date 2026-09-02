"""Caché de VLC para IPTV: tamaño según el tipo de stream y si aún llegan datos."""

import sys

PROFILES = ('fast', 'balanced', 'stable')
PROFILE_LABELS = {
    'fast': 'rápido',
    'balanced': 'equilibrado',
    'stable': 'estable',
}

_CACHE_MS = {
    'fast': {
        'mpegts': 2000,
        'hls': 5000,
        'container': 3000,
        'local': 1000,
    },
    'balanced': {
        'mpegts': 5000,
        'hls': 8000,
        'container': 4000,
        'local': 1500,
    },
    'stable': {
        'mpegts': 8000,
        'hls': 12000,
        'container': 6000,
        'local': 2000,
    },
}

CACHE_MS_MAX = 15000
SOFT_REBUFFER_NEED = 3
SOFT_REBUFFER_WINDOW_S = 30
SOFT_REBUFFER_EXTRA_MS = 3000

_OVERLAY_MESSAGES = {
    'connecting': (
        'Conectando…',
        'Esperando imagen del canal.',
    ),
    'buffering': (
        'Bufferizando…',
        'Recuperando el directo.',
    ),
    'reconnect': (
        'Reconectando…',
        'El directo se ha quedado sin datos; volvemos a abrir el enlace.',
    ),
    'buffer_bump': (
        'Ampliando buffer…',
        'Varios microcortes; subimos la caché de reproducción.',
    ),
    'retry_ts': (
        'Reintentando…',
        'Probando como MPEG-TS.',
    ),
}


def iptv_overlay_message(event):
    """Título y detalle breves para el overlay de reintento IPTV."""
    return _OVERLAY_MESSAGES.get(str(event or '').strip(), _OVERLAY_MESSAGES['reconnect'])

_PROFILE_ALIASES = {
    'rapido': 'fast',
    'rápido': 'fast',
    'low': 'fast',
    'bajo': 'fast',
    'equilibrado': 'balanced',
    'normal': 'balanced',
    'medio': 'balanced',
    'default': 'balanced',
    'estable': 'stable',
    'high': 'stable',
    'alto': 'stable',
}


def normalize_iptv_buffer_profile(value):
    """Normaliza IPTV buffer profile."""
    text = str(value or '').strip().lower()
    if text in PROFILES:
        return text
    return _PROFILE_ALIASES.get(text, 'balanced')


def vlc_aout_option(force_pulse=False, prefix=':'):
    """Salida de audio de VLC en Linux. En Windows/macOS VLC usa la del sistema."""
    if not sys.platform.startswith('linux'):
        return None
    name = 'pulse' if force_pulse else 'alsa'
    return f'{prefix}aout={name}'


def vlc_aout_instance_args():
    """Vlc aout instance args."""
    option = vlc_aout_option(force_pulse=False, prefix='')
    return [f'--{option}'] if option else []


def iptv_cache_ms(kind, *, vod=False, local=False, profile='balanced', force_ts=False, extra_ms=0):
    """Milisegundos de network/live/file-caching para este enlace."""
    table = _CACHE_MS[normalize_iptv_buffer_profile(profile)]
    if local:
        base = table['local']
    elif force_ts:
        base = table['mpegts']
    elif vod or kind == 'container':
        base = table['container']
    elif kind == 'hls':
        base = table['hls']
    else:
        base = table['mpegts']
    try:
        extra = max(0, int(extra_ms or 0))
    except (TypeError, ValueError):
        extra = 0
    return min(CACHE_MS_MAX, base + extra)


def iptv_is_live(kind, *, vod=False, force_ts=False):
    """Iptv is live."""
    if vod:
        return False
    if force_ts:
        return True
    return kind in ('mpegts', 'hls')


def iptv_vlc_buffer_options(
    kind,
    *,
    vod=False,
    local=False,
    profile='balanced',
    force_ts=False,
    extra_ms=0,
    prefix=':',
):
    """Opciones de media de VLC (caché y reloj). No incluye la URL."""
    cache = iptv_cache_ms(
        kind,
        vod=vod,
        local=local,
        profile=profile,
        force_ts=force_ts,
        extra_ms=extra_ms,
    )
    options = [
        f'{prefix}network-caching={cache}',
        f'{prefix}live-caching={cache}',
        f'{prefix}file-caching={cache}',
        f'{prefix}sout-mux-caching={cache}',
    ]
    if iptv_is_live(kind, vod=vod, force_ts=force_ts):
        # PCR irregular de IPTV, con margen de jitter igual a la caché (no 0).
        options.extend([
            f'{prefix}clock-synchro=0',
            f'{prefix}clock-jitter={cache}',
        ])
    return options


def vlc_state_name(state):
    """Vlc state name."""
    if state is None:
        return ''
    name = getattr(state, 'name', None)
    if name:
        return str(name)
    text = str(state)
    return text.rsplit('.', 1)[-1]


def iptv_bytes_progress(stats):
    """Iptv bytes progress."""
    if stats is None:
        return 0
    best = 0
    for field in ('demux_read_bytes', 'read_bytes'):
        try:
            value = int(getattr(stats, field, 0) or 0)
        except (TypeError, ValueError):
            continue
        if value > best:
            best = value
    return best


def iptv_startup_decision(
    *,
    state,
    decoded,
    bytes_now,
    bytes_prev,
    ticks,
    kind='mpegts',
    already_retried_ts=False,
):
    """ready | wait | fail | retry_ts al abrir un canal."""
    name = vlc_state_name(state)
    if decoded:
        return 'ready'
    if kind == 'container' and not already_retried_ts and name in ('Ended', 'Error', 'Stopped'):
        return 'retry_ts'
    if name == 'Error':
        return 'fail'
    if name == 'Ended' and ticks >= 1:
        return 'fail'
    growing = bytes_now > bytes_prev
    if kind == 'hls':
        no_data_ticks = 6
        max_ticks = 14 if growing else 8
    else:
        no_data_ticks = 4
        max_ticks = 10 if growing else 6
    if ticks >= max_ticks:
        return 'fail'
    if ticks >= no_data_ticks and bytes_now <= 0:
        return 'fail'
    if ticks >= 5 and not growing and bytes_now > 0:
        return 'fail'
    return 'wait'


def iptv_deadman_should_fail(
    *,
    decoded,
    bytes_now,
    bytes_prev,
    elapsed_s,
    kind='mpegts',
):
    """Tras el primer plazo: fallar solo si no hay imagen ni datos nuevos."""
    if decoded:
        return False
    growing = bytes_now > bytes_prev
    limit = 24 if kind == 'hls' else 16
    if growing and elapsed_s < limit:
        return False
    return elapsed_s >= 12


def iptv_rebuffer_decision(
    *,
    started,
    state,
    stall_ticks,
    bytes_now,
    bytes_prev,
    reconnects,
    vod=False,
):
    """ok | wait | reconnect | fail cuando el directo ya había arrancado."""
    if not started:
        return 'ok'
    name = vlc_state_name(state)
    if name in ('Playing', 'Paused'):
        return 'ok'
    if vod and name == 'Ended':
        return 'ok'
    if name == 'Error':
        return 'fail'
    if name == 'Ended':
        return 'fail'
    if name != 'Buffering':
        return 'ok'
    if bytes_now > bytes_prev:
        return 'wait'
    if stall_ticks >= 4 and reconnects < 1:
        return 'reconnect'
    if stall_ticks >= 8:
        return 'fail'
    return 'wait'


def iptv_soft_rebuffer_note(times, now, window_s=SOFT_REBUFFER_WINDOW_S, is_new_event=True):
    """Marcas de microcorte (Buffering con bytes llegando) dentro de la ventana."""
    kept = []
    try:
        stamp = float(now)
        window = float(window_s)
    except (TypeError, ValueError):
        return list(times or [])
    for item in times or ():
        try:
            when = float(item)
        except (TypeError, ValueError):
            continue
        if stamp - when <= window:
            kept.append(when)
    if is_new_event:
        kept.append(stamp)
    return kept


def iptv_soft_rebuffer_should_bump(soft_count, already_bumped, need=SOFT_REBUFFER_NEED):
    """Tras varios microcortes con datos, subir caché una vez (no cambia Preferencias)."""
    if already_bumped:
        return False
    try:
        count = int(soft_count or 0)
    except (TypeError, ValueError):
        count = 0
    try:
        threshold = int(need)
    except (TypeError, ValueError):
        threshold = SOFT_REBUFFER_NEED
    return count >= threshold
