# Notas técnicas y problemas conocidos

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

## Cómo reproduce

- **VLC embebido** (`python-vlc`): decodificación por software (`avcodec-hw=none`) para evitar ruido de VA-API en NVIDIA. Audio: ALSA en IPTV, Pulse en YouTube cuando hace falta.
- **YouTube**: [yt-dlp](https://github.com/yt-dlp/yt-dlp) elige un stream que VLC pueda abrir (audio+vídeo juntos si existe; se evitan DASH/HLS difíciles). La calidad se pide en **Calidad / audio** (360p o 720p). Si falla, hay un relevo local o un archivo de caché jugable (tope ~500 MB, sin remux si ya es MP4/MKV/WebM).
- **IPTV**: se usa la URL del M3U. No se inventan rutas Xtream. Un 302 del panel lo sigue VLC; si el nodo de vídeo cierra la conexión, no hay imagen. Ver [listas M3U](listas-m3u.md#reproducción-iptv).
- **Listas grandes**: el filtrado de la ventana principal y la carga/parseo del M3U van en segundo plano. La barra lateral agrupa por `group-title`: pestañas si hay pocos grupos, desplegable si hay muchos; un clic entra en la categoría. Sin grupos y con miles de entradas, solo se dibujan las filas visibles. Pintar o filtrar una lista enorme en la lateral aún puede congelar un momento.
- **EPG**: XMLTV (en el M3U o en **Reproducir → Guía EPG**, por URL o archivo). Se asocia por `tvg-id`, `tvg-name` o el nombre del canal frente a `<display-name>`. Hay parrilla, programa actual en la fila y ahora / a continuación al pasar el ratón. La guía se pide en segundo plano (timeout 90 s), se recarga cada 30 min y no se registran las URLs (pueden llevar token). Una URL `get.php` o `xmltv.php` se usa tal cual; no se reescribe a otra ruta Xtream. Miniaturas: `tvg-logo` / `<icon>` en `epg_cache/` (no va al git); se pueden apagar en **Preferencias** o en **Guía EPG → Mostrar logos de canal**.
- **Historial IPTV**: últimos canales (hasta 25) y posición de VOD en `config.json`, igual que la sesión. No se escriben las URLs en el registro. YouTube sigue usando `youtube_resume`.
- **Audio y subtítulos**: VLC lista las pistas del stream (típico en IPTV/HLS) en **Calidad / audio**. YouTube aporta subtítulos descargados (oficiales o auto); no hay cambio de idioma de audio.
- No se usa `--no-hw-dec`: en VLC 3.0.20 esa opción puede hacer que `vlc.Instance()` falle.

El reproductor está partido en `video_player.py` más mixins: `player_iptv.py` (apertura VLC y stream muerto), `player_overlay.py` (aviso en pantalla) y `player_controls.py` (barra, volumen, pantalla completa).

## Tests

El parseo de M3U (`#EXTINF`, `tvg-id`, `tvg-logo`, encabezado `#EXTM3U` con `url-tvg`) y la guía XMLTV (ahora/siguiente, parrilla, iconos) tienen pruebas en `tests/`. No van en el `.deb`; son para desarrollo:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

## Archivos en la carpeta del programa

`favoritos.json` sí va en el repositorio (lista vacía). El resto los crea o actualiza el programa en tu equipo y **no se publican** (están en `.gitignore`).

| Archivo | Uso | Si no existe |
| --- | --- | --- |
| `favoritos.json` | Favoritos del reproductor | Viene en el repo; si falta, el reproductor usa una lista vacía |
| `enlaces.json` | Enlaces guardados en el gestor | Se crea vacío al arrancar |
| `config.json` | Preferencias (tema, logos de canal, volumen, carpeta de descargas, navegador de cookies, calidad YouTube, recordar última lista, URL de guía EPG), geometría de ventanas, última lista lateral y canal (sin autoplay), segundo de YouTube y historial IPTV / seguir viendo VOD | Se crea con valores por defecto al arrancar. Se edita en **Archivo → Preferencias** |
| `cookies.txt` | Cookies de YouTube | Se escribe al reproducir YouTube o al pulsar **Reexportar cookies**, solo si hay login vigente en el navegador. El indicador **Sesión YouTube: OK / caducada** avisa si hace falta reexportar. Detalle en [YouTube](youtube.md#cookies) |
| `.venv/` | Entorno Python | `run_app.py` lo recrea ([instalación](instalacion.md)) |
| `epg_cache/` | Miniaturas de logos EPG / `tvg-logo` | Se crea al pintar logos; no va al git |

## Monitor de CPU

Si está `psutil` (lo instala `run_app.py`), puedes ver el uso de CPU en el reproductor. Va **desactivado** para no recargar la interfaz.

En `video_player.py`, método `create_window`, descomenta:

```python
# self.setup_performance_monitoring()
```

y déjala así:

```python
self.setup_performance_monitoring()
```

Aparecerá el porcentaje abajo a la derecha, actualizado cada segundo.

## Problemas conocidos

> [!IMPORTANT]
> El desarrollo y las pruebas se hacen sobre todo en Linux. En Windows puede haber fallos no vistos.

- Algunos vídeos de YouTube no tienen stream compatible o están restringidos.
- En Linux hacen falta VLC y, si aplica, `python3-vlc` del sistema.
- Si YouTube no tiene audio, prueba la salida Pulse/ALSA del sistema.
- Un canal IPTV puede tardar en arrancar o no arrancar: depende del servidor de la lista, no solo del programa. Si no hay vídeo (también con pantalla negra), el reproductor muestra que ese canal por el momento no funciona. Si el mismo enlace falla en VLC, el archivo no está disponible desde esta red.
- En GNOME, la bandeja necesita AppIndicator. Ver [reproductor](reproductor.md#ubuntu--gnome).
- La búsqueda de Shorts usa la pestaña de hashtag de YouTube; un término sin hashtag equivalente puede devolver pocos resultados.

## Siguiente

- [Instalación](instalacion.md)
- [Inicio](../README.md)

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
