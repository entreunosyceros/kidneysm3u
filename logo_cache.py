"""Caché local de tvg-logo. No registra las URLs (pueden llevar token)."""

import hashlib
import os
import ssl
import threading
from io import BytesIO
from urllib.request import Request, urlopen

from m3u_parse import IPTV_USER_AGENT

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'epg_cache')
MAX_LOGO_BYTES = 400 * 1024
MAX_FILES = 800
LOGO_PX = 20


def cache_dir():
    """Cache dir."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR


def clear_cache():
    """Borra todas las miniaturas de epg_cache/."""
    folder = cache_dir()
    removed = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0
    for name in names:
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path):
                os.remove(path)
                removed += 1
        except OSError:
            pass
    return removed


def _key(url):
    """Uso interno: key."""
    return hashlib.sha1((url or '').encode('utf-8', errors='replace')).hexdigest()[:20]


def path_for(url):
    """Path for."""
    url = (url or '').strip()
    if not url:
        return ''
    return os.path.join(cache_dir(), _key(url) + '.png')


def _prune():
    """Uso interno: prune."""
    folder = cache_dir()
    try:
        entries = [
            os.path.join(folder, name)
            for name in os.listdir(folder)
            if name.endswith('.png')
        ]
    except OSError:
        return
    if len(entries) <= MAX_FILES:
        return
    entries.sort(key=lambda path: os.path.getmtime(path) if os.path.isfile(path) else 0)
    for path in entries[: len(entries) - MAX_FILES]:
        try:
            os.remove(path)
        except OSError:
            pass


def _fetch_bytes(url):
    """Uso interno: fetch bytes."""
    last_error = None
    for user_agent in (IPTV_USER_AGENT, 'Mozilla/5.0'):
        request = Request(
            url,
            headers={'User-Agent': user_agent, 'Accept': 'image/*,*/*'},
        )
        try:
            with urlopen(request, timeout=12) as response:
                chunk = response.read(MAX_LOGO_BYTES + 1)
        except Exception as exc:
            reason = getattr(exc, 'reason', None)
            if isinstance(exc, ssl.SSLError) or isinstance(reason, ssl.SSLError):
                try:
                    ctx = ssl._create_unverified_context()
                    with urlopen(request, timeout=12, context=ctx) as response:
                        chunk = response.read(MAX_LOGO_BYTES + 1)
                except Exception as inner:
                    last_error = inner
                    continue
            else:
                last_error = exc
                continue
        if chunk and len(chunk) <= MAX_LOGO_BYTES:
            return chunk
    if last_error:
        raise last_error
    return b''


def _to_png(raw):
    """Uso interno: to png."""
    from PIL import Image
    image = Image.open(BytesIO(raw))
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGBA')
    resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.LANCZOS)
    image = image.resize((LOGO_PX, LOGO_PX), resample)
    out = BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def load_photo(url, photos):
    """PhotoImage desde disco. `photos` guarda la referencia para Tk."""
    path = path_for(url)
    if not path or not os.path.isfile(path):
        return None
    key = path
    cached = photos.get(key)
    if cached is not None:
        return cached
    try:
        from PIL import Image, ImageTk
        image = Image.open(path)
        photo = ImageTk.PhotoImage(image)
    except Exception:
        return None
    photos[key] = photo
    return photo


def fetch_one(url):
    """Obtiene one desde la red o el disco."""
    url = (url or '').strip()
    if not url:
        return ''
    path = path_for(url)
    if os.path.isfile(path) and os.path.getsize(path) > 32:
        return path
    try:
        raw = _fetch_bytes(url)
        if not raw:
            return ''
        png = _to_png(raw)
        with open(path, 'wb') as handle:
            handle.write(png)
        _prune()
        return path
    except Exception:
        return ''


def fetch_many(urls, on_done=None):
    """Descarga en segundo plano. on_done() se llama al terminar cada logo (hilo worker)."""
    pending = []
    seen = set()
    for url in urls:
        url = (url or '').strip()
        if not url or url in seen:
            continue
        seen.add(url)
        if os.path.isfile(path_for(url)):
            continue
        pending.append(url)
    if not pending:
        return

    def work():
        """Work."""
        for url in pending[:120]:
            fetch_one(url)
            if on_done:
                on_done()

    threading.Thread(target=work, daemon=True).start()
