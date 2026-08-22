# Notas técnicas y problemas conocidos

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

## Cómo reproduce

- **VLC embebido** (`python-vlc`): decodificación por software (`avcodec-hw=none`) para evitar ruido de VA-API en NVIDIA. Audio: ALSA en IPTV, Pulse en YouTube cuando hace falta.
- **YouTube**: [yt-dlp](https://github.com/yt-dlp/yt-dlp) elige un stream que VLC pueda abrir (audio+vídeo juntos si existe; se evitan DASH/HLS difíciles). Preferencia habitual: MP4/AVC1 hasta 720p. Si falla, hay un relevo local.
- **IPTV**: se usa la URL del M3U. No se inventan rutas Xtream. Un 302 del panel lo sigue VLC; si el nodo de vídeo cierra la conexión, no hay imagen. Ver [listas M3U](listas-m3u.md#reproducción-iptv).
- No se usa `--no-hw-dec`: en VLC 3.0.20 esa opción puede hacer que `vlc.Instance()` falle.

## Archivos en la carpeta del programa

| Archivo | Uso |
| --- | --- |
| `favoritos.json` | Favoritos del reproductor |
| `enlaces.json` | Enlaces guardados en el gestor |
| `config.json` | Volumen, geometría de ventanas, última lista y canal (sin autoplay) |
| `cookies.txt` | Cookies de YouTube (opcional; también se leen del navegador) |
| `.venv/` | Entorno Python; si lo borras, `run_app.py` lo recrea ([instalación](instalacion.md)) |

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
- Un canal IPTV puede tardar en arrancar o no arrancar: depende del servidor de la lista, no solo del programa. Si el mismo enlace falla en VLC, el archivo no está disponible desde esta red.
- En GNOME, la bandeja necesita AppIndicator. Ver [reproductor](reproductor.md#ubuntu--gnome).
- La búsqueda de Shorts usa la pestaña de hashtag de YouTube; un término sin hashtag equivalente puede devolver pocos resultados.

## Siguiente

- [Instalación](instalacion.md)
- [Inicio](../README.md)

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
