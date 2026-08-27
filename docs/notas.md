# Notas técnicas y problemas conocidos

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

## Cómo reproduce

- **VLC embebido** (`python-vlc`): decodificación por software (`avcodec-hw=none`) para evitar ruido de VA-API en NVIDIA. Audio en Linux: ALSA en IPTV, Pulse en YouTube cuando hace falta. En Windows y macOS no se fuerza módulo: VLC usa DirectSound/Wasapi o Core Audio.
- **YouTube**: [yt-dlp](https://github.com/yt-dlp/yt-dlp) elige un stream que VLC pueda abrir (audio+vídeo juntos si existe; se evitan DASH/HLS difíciles). La calidad se pide en **Calidad / audio** (360p, 720p, 1080p o mejor disponible). Si falla, hay un relevo local o un archivo de caché jugable (tope ~500 MB, sin remux si ya es MP4/MKV/WebM).
- **IPTV**: se usa la URL del M3U. No se inventan rutas Xtream. Un 302 del panel lo sigue VLC; si el nodo de vídeo cierra la conexión, no hay imagen. El buffer de VLC depende del tipo (MPEG-TS / HLS / VOD) y del perfil de **Preferencias** (`iptv_buffer.py`). Si aún llegan bytes, no se da el canal por muerto; si el directo ya había arrancado y el buffer se queda seco, se reconecta una vez el mismo enlace. Si un FHD sigue microcortando con datos llegando, se sube la caché una vez en esa sintonía. Ver [listas M3U](listas-m3u.md#buffer-iptv).
- **Listas grandes**: el filtrado de la ventana principal y la carga/parseo del M3U van en segundo plano. La barra lateral agrupa por `group-title`: pestañas si hay pocos grupos, desplegable si hay muchos; un clic entra en la categoría. Sin grupos y con miles de entradas, solo se dibujan las filas visibles. Pintar o filtrar una lista enorme en la lateral aún puede congelar un momento.
- **EPG**: XMLTV (en el M3U o en **Reproducir → Guía EPG**, por URL o archivo). Se asocia por `tvg-id`, `tvg-name` o el nombre del canal frente a `<display-name>`. Hay parrilla, programa actual en la fila y ahora / a continuación al pasar el ratón. La guía se pide en segundo plano (timeout 90 s), se recarga cada 30 min y no se registran las URLs (pueden llevar token). Una URL `get.php` o `xmltv.php` se usa tal cual; no se reescribe a otra ruta Xtream. Miniaturas: `tvg-logo` / `<icon>` en `epg_cache/` (no va al git); se pueden apagar en **Preferencias** o en **Guía EPG → Mostrar logos de canal**.
- **Historial IPTV y YouTube**: últimos canales (hasta 25), posición de VOD y últimos vídeos de YouTube en `config.json`, igual que la sesión. La misma ventana **Historial** muestra las dos. No se escriben las URLs en el registro.
- **Audio y subtítulos**: VLC lista las pistas del stream (típico en IPTV/HLS) en **Calidad / audio**. YouTube: transcripción ASR, pistas del autor y traducción automática (VTT con `tlang`; el json3 traducido suele seguir en inglés). No hay cambio de idioma de audio.
- No se usa `--no-hw-dec`: en VLC 3.0.20 esa opción puede hacer que `vlc.Instance()` falle.

El reproductor está partido en `video_player.py` más mixins: `player_iptv.py` (apertura VLC y stream muerto), `iptv_buffer.py` (caché según tipo/perfil y reconexión), `player_overlay.py` (aviso en pantalla), `player_controls.py` (barra, volumen, pantalla completa) y `player_pip.py` (recuadro PiP y siempre encima). Los menús de **calidad / audio** y **subtítulos** se colocan para que quepan en la ventana (`popup_menu_origin` en `video_player.py`): si no hay sitio debajo del botón, se abren hacia arriba. La grabación del stream actual está en `iptv_record.py`: `ffmpeg -c copy` a un `.ts`/`.mkv` local (carpeta de descargas de Preferencias). No sube nada ni descifra DRM.

Caché de red de VLC con el perfil **Equilibrado** (ms): MPEG-TS 5000, HLS 8000, VOD/contenedor 4000, relevo local 1500. **Rápido** baja esos valores (MPEG-TS 2000, HLS 5000); **Estable** los sube (MPEG-TS 8000, HLS 12000). Tope 15000 ms. En directo se envía `clock-synchro=0` y `clock-jitter` igual a la caché (no 0). En VOD no se toca el reloj. Si hay varios microcortes con bytes llegando (~3 en 30 s), se reabre una vez con +3000 ms.

## Tests

El parseo de M3U (`#EXTINF`, `tvg-id`, `tvg-logo`, encabezado `#EXTM3U` con `url-tvg`), la guía XMLTV (ahora/siguiente, parrilla, iconos), el buffer IPTV (`tests/test_iptv_buffer.py`) y los mixins del reproductor (menús emergentes, PiP) tienen pruebas en `tests/`. No van en el `.deb`; son para desarrollo:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

## Archivos en la carpeta del programa

`favoritos.json` lo crea el reproductor en tu equipo y **no se publica** (está en `.gitignore`, igual que `config.json` y las cookies). Si no existe, se usa una lista vacía. Con el `.deb`, esos archivos viven en `~/.local/share/kidneysm3u`, no en `/usr/share/kidneysm3u`. Desinstalar el paquete **no borra** esa carpeta; hay que hacerlo a mano. Detalle en [instalación](instalacion.md#desinstalar).

| Archivo | Uso | Si no existe |
| --- | --- | --- |
| `favoritos.json` | Favoritos del reproductor | Se crea al guardar el primer favorito. Si falta, el reproductor usa una lista vacía |
| `enlaces.json` | Enlaces guardados en el gestor | Se crea vacío al arrancar |
| `config.json` | Preferencias (tema, logos de canal, volumen, carpeta de descargas, abrir gestor de archivos al descargar, navegador de cookies, calidad YouTube, buffer IPTV, recordar última lista, URL de guía EPG), geometría de ventanas, última lista lateral y canal (sin autoplay), segundo de YouTube, cola de YouTube, historial IPTV / YouTube y últimas URLs de **Archivo → Descargar** | Se crea con valores por defecto al arrancar. Se edita en **Archivo → Preferencias** |
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
![documentacion](https://github.com/user-attachments/assets/4a6ae87c-8b96-4c63-930a-ec1b22d8382b)

> [!IMPORTANT]
> El desarrollo y las pruebas se hacen sobre todo en Linux. En Windows puede haber fallos no vistos. El reproductor usa `trace_add` (Tcl 8.7 / Python 3.13) y no fuerza ALSA, que no existe en Windows. El instalador de Windows se genera con `bash build-windows.sh` (Docker: PyInstaller/Wine + Inno Setup).

- En **Windows**, Chrome, Brave y Edge cifran las cookies de YouTube y el programa no puede leerlas. Preferencias solo ofrece **Automático** y **Firefox**. Inicia sesión en Firefox, ciérralo y pulsa **Reexportar cookies**. Detalle en [YouTube](youtube.md#cookies).
- Algunos vídeos de YouTube no tienen stream compatible o están restringidos. Si de pronto no extrae ninguno, actualiza yt-dlp en **Preferencias** (o **Youtube → Actualizar yt-dlp**) y reinicia.
- En Linux hacen falta VLC y, si aplica, `python3-vlc` del sistema.
- Si YouTube no tiene audio, prueba la salida Pulse/ALSA del sistema.
- Un canal IPTV puede tardar en arrancar o no arrancar: depende del servidor de la lista, no solo del programa. Si no hay vídeo (también con pantalla negra), el reproductor muestra que ese canal por el momento no funciona. Si el mismo enlace falla en VLC, el archivo no está disponible desde esta red. Si un FHD se corta cada pocos segundos, **Equilibrado** ya usa ~5 s de caché en MPEG-TS; el programa puede subirla una vez. Si sigue igual, prueba **Preferencias → Buffer IPTV → Estable**.
- En GNOME, la bandeja necesita AppIndicator. Ver [reproductor](reproductor.md#ubuntu--gnome). El lanzador y la ventana usan el mismo `WM_CLASS` (`Kidneysm3u`) para que no aparezca un segundo icono en el dock; detalle en [instalación](instalacion.md#instalación-en-ubuntu-paquete-deb).
- La búsqueda de Shorts usa la pestaña de hashtag de YouTube; un término sin hashtag equivalente puede devolver pocos resultados.

## Siguiente

- [Instalación](instalacion.md)
- [Inicio](../README.md)

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
