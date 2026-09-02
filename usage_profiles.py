"""Perfiles de uso: presets de preferencias para distintos escenarios."""

from iptv_buffer import normalize_iptv_buffer_profile

PROFILE_CUSTOM = 'custom'
PROFILE_LIVE_TV = 'live_tv'
PROFILE_CINEMA_VOD = 'cinema_vod'
PROFILE_LOW_END_PC = 'low_end_pc'

PROFILE_ORDER = (
    PROFILE_CUSTOM,
    PROFILE_LIVE_TV,
    PROFILE_CINEMA_VOD,
    PROFILE_LOW_END_PC,
)

_PROFILES = {
    PROFILE_CUSTOM: {
        'label': 'Personalizado',
        'description': 'Mantiene los ajustes actuales. Cambia solo si modificas las opciones a mano.',
        'settings': {},
    },
    PROFILE_LIVE_TV: {
        'label': 'TV en directo',
        'description': (
            'Buffer IPTV estable y sin logos en la lista para sintonizar directos '
            'con menos carga gráfica.'
        ),
        'settings': {
            'iptv_buffer': 'stable',
            'show_channel_logos': False,
            'light_mode': False,
            'remember_last_list': True,
        },
    },
    PROFILE_CINEMA_VOD: {
        'label': 'Cine / VOD',
        'description': (
            'Buffer amplio, logos activos y recordar lista y posición al reanudar '
            'películas o series.'
        ),
        'settings': {
            'iptv_buffer': 'stable',
            'show_channel_logos': True,
            'light_mode': False,
            'remember_last_list': True,
            'youtube_quality': 720,
            'twitch_quality': 720,
        },
    },
    PROFILE_LOW_END_PC: {
        'label': 'PC débil',
        'description': (
            'Modo ligero, YouTube y Twitch a 360p y buffer IPTV rápido para equipos justos.'
        ),
        'settings': {
            'light_mode': True,
            'light_mode_hw_decode': True,
            'show_channel_logos': False,
            'youtube_quality': 360,
            'twitch_quality': 360,
            'iptv_buffer': 'fast',
            'remember_last_list': True,
        },
    },
}

_PROFILE_KEYS = (
    'iptv_buffer',
    'show_channel_logos',
    'light_mode',
    'light_mode_hw_decode',
    'remember_last_list',
    'youtube_quality',
    'twitch_quality',
)


def normalize_usage_profile(value):
    """Devuelve un id de perfil válido."""
    key = str(value or PROFILE_CUSTOM).strip().lower()
    return key if key in _PROFILES else PROFILE_CUSTOM


def profile_choices():
    """Lista (id, etiqueta) para la interfaz."""
    return [(key, _PROFILES[key]['label']) for key in PROFILE_ORDER]


def profile_description(profile_id):
    """Texto de ayuda del perfil."""
    return _PROFILES.get(normalize_usage_profile(profile_id), _PROFILES[PROFILE_CUSTOM])['description']


def profile_settings(profile_id):
    """Ajustes que aplica un perfil (vacío para personalizado)."""
    return dict(_PROFILES.get(normalize_usage_profile(profile_id), _PROFILES[PROFILE_CUSTOM])['settings'])


def apply_profile_settings(profile_id):
    """Devuelve el bloque de config listo para app_config.save()."""
    settings = profile_settings(profile_id)
    if not settings:
        return {'usage_profile': PROFILE_CUSTOM}
    payload = dict(settings)
    if 'iptv_buffer' in payload:
        payload['iptv_buffer'] = normalize_iptv_buffer_profile(payload['iptv_buffer'])
    payload['usage_profile'] = normalize_usage_profile(profile_id)
    return payload


def detect_usage_profile(config=None):
    """Infiera el perfil activo comparando ajustes clave (o custom)."""
    if config is None:
        import app_config
        config = app_config.load()
    stored = normalize_usage_profile(config.get('usage_profile', PROFILE_CUSTOM))
    if stored != PROFILE_CUSTOM:
        return stored
    for profile_id in PROFILE_ORDER:
        if profile_id == PROFILE_CUSTOM:
            continue
        expected = profile_settings(profile_id)
        if expected and all(config.get(key) == value for key, value in expected.items()):
            return profile_id
    return PROFILE_CUSTOM
