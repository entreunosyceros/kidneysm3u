"""Caché de VLC para IPTV: tamaño según el tipo de stream y si aún llegan datos."""

PROFILES = ('fast', 'balanced', 'stable')
PROFILE_LABELS = {
    'fast': 'rápido',
    'balanced': 'equilibrado',
    'stable': 'estable',
}

_CACHE_MS = {
    'fast': {
        'mpegts': 1000,
        'hls': 2500,
        'container': 2000,
        'local': 800,
    },
    'balanced': {
        'mpegts': 2000,
        'hls': 4000,
        'container': 3000,
        'local': 1200,
    },
    'stable': {
        'mpegts': 3500,
        'hls': 6000,
        'container': 4000,
        'local': 1800,
    },
}

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
    text = str(value or '').strip().lower()
    if text in PROFILES:
        return text
    return _PROFILE_ALIASES.get(text, 'balanced')


def iptv_cache_ms(kind, *, vod=False, local=False, profile='balanced', force_ts=False):
    """Milisegundos de network/live/file-caching para este enlace."""
    table = _CACHE_MS[normalize_iptv_buffer_profile(profile)]
    if local:
        return table['local']
    if force_ts:
        return table['mpegts']
    if vod or kind == 'container':
        return table['container']
    if kind == 'hls':
        return table['hls']
    return table['mpegts']


def iptv_is_live(kind, *, vod=False, force_ts=False):
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
    prefix=':',
):
    """Opciones de media de VLC (caché y reloj). No incluye la URL."""
    cache = iptv_cache_ms(
        kind, vod=vod, local=local, profile=profile, force_ts=force_ts,
    )
    options = [
        f'{prefix}network-caching={cache}',
        f'{prefix}live-caching={cache}',
        f'{prefix}file-caching={cache}',
        f'{prefix}sout-mux-caching={cache}',
    ]
    if iptv_is_live(kind, vod=vod, force_ts=force_ts):
        # PCR irregular de IPTV: no detener el vídeo para resincronizar el reloj.
        options.extend([
            f'{prefix}clock-synchro=0',
            f'{prefix}clock-jitter=0',
        ])
    return options


def vlc_state_name(state):
    if state is None:
        return ''
    name = getattr(state, 'name', None)
    if name:
        return str(name)
    text = str(state)
    return text.rsplit('.', 1)[-1]


def iptv_bytes_progress(stats):
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
