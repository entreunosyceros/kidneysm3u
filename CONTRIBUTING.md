# Guía de contribución

¡Gracias por interesarte en **[Kidneysm3u](https://github.com/sapoclay/kidneysm3u)**! Este proyecto es una aplicación de escritorio en **Python** y **Tkinter** para listas M3U/IPTV y YouTube, publicada bajo [MIT](LICENSE). Cualquier mejora bien planteada es bienvenida.

## Antes de empezar

- Lee el [README](README.md) y el [índice de documentación](docs/README.md) para entender el alcance del proyecto.
- Revisa las [issues abiertas](https://github.com/sapoclay/kidneysm3u/issues) por si alguien ya trabaja en lo mismo.
- Para el comportamiento en la comunidad, consulta el [Código de conducta](CODE_OF_CONDUCT.md).
- Para vulnerabilidades, sigue [SECURITY.md](SECURITY.md) (no abras issues públicas con detalles de explotación).

## Cómo puedes ayudar

- **Reportar errores** con pasos claros (sistema, VLC, si usas código fuente o el `.deb`).
- **Proponer mejoras** explicando el problema que resuelven.
- **Enviar pull requests** con cambios acotados y probados.
- **Mejorar documentación** (README, `docs/`, comentarios en el código).
- **Añadir o ajustar pruebas** en `tests/` (parseo M3U, EPG, buffer IPTV, descargas).

## Entorno de desarrollo

Requisitos: **Python 3.8+**, [VLC](https://www.videolan.org/vlc/) y `python3-tk`. Opcional: `ffmpeg` (grabar / extraer audio) y Node o Deno (yt-dlp).

```bash
git clone https://github.com/sapoclay/kidneysm3u.git
cd kidneysm3u
python3 run_app.py
```

`run_app.py` crea el entorno virtual (`.venv`), instala dependencias desde `requirements.txt` y arranca la aplicación. No uses `python3 main.py` a pelo si acabas de borrar `.venv`.

### Arranque manual (opcional)

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 run_app.py
```

### Pruebas

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

### Paquete `.deb` (opcional)

```bash
bash packaging/build-deb.sh
```

El resultado queda en `debian-package/`. Detalle en [docs/instalacion.md](docs/instalacion.md).

### Instalador de Windows (opcional)

```bash
bash build-windows.sh
```

Queda `dist/Kidneysm3u-Setup-*.exe` (asistente de instalación). Detalle en [docs/instalacion.md](docs/instalacion.md#instalador-de-windows).

## Estructura del código

| Ruta | Contenido |
|------|-----------|
| `main.py` | Ventana principal: filtro M3U, menús, lanzamiento del reproductor |
| `video_player.py` | Reproductor (lista lateral, menús, carga M3U/YouTube) |
| `player_iptv.py`, `iptv_buffer.py` | Apertura VLC, caché y reconexión IPTV |
| `subtitle_style.py` | Estilo de subtítulos de texto (VLC freetype) |
| `player_controls.py`, `player_pip.py`, `player_overlay.py` | Barra, PiP, avisos en pantalla |
| `youtube_player.py`, `youtube_search.py` | Reproducción y búsqueda de YouTube (yt-dlp) |
| `m3u_parse.py`, `epg.py` | Parseo M3U y guía XMLTV |
| `descargas.py` | Ventana **Archivo → Descargar** |
| `app_config.py` | Preferencias y sesión (`config.json`) |
| `docs/` | Manual de usuario |
| `kidneysm3u.spec`, `kidneysm3u.iss`, `build-windows.sh` | Instalador de Windows (Inno Setup) |
| `packaging/` | Empaquetado Debian |
| `tests/` | Pruebas (no van en el `.deb`) |
| `run_app.py` | Lanzador recomendado |

Más detalle en [docs/notas.md](docs/notas.md).

## Estilo de código

- Sigue el estilo del código existente (nombres, imports, nivel de comentarios).
- Cambios **mínimos y enfocados**: no mezcles varias funcionalidades en un mismo PR.
- Los textos visibles para el usuario van en **español**.
- No incluyas secretos, `cookies.txt`, `config.json`, listas M3U con usuario/contraseña ni capturas con tokens.
- No registres URLs completas de IPTV, EPG o YouTube (pueden llevar credenciales).
- No inventes rutas Xtream: una URL de guía o de lista se usa tal cual.
- No uses `--no-hw-dec` en VLC: en 3.0.20 puede hacer que `vlc.Instance()` falle.
- Los datos de usuario (`config.json`, `cookies.txt`, `favoritos.json`, `enlaces.json`, `epg_cache/`) no van al git.

## Pull requests

1. Crea una rama descriptiva desde `main` (por ejemplo `fix/iptv-buffer` o `feat/download-history`).
2. Describe **qué** cambias y **por qué**.
3. Indica cómo lo has probado (pasos manuales, `pytest`, capturas si aplica).
4. Si tocas IPTV, YouTube o EPG, no pegues URLs reales con credenciales en el PR.
5. Actualiza `docs/` o el README solo si el cambio lo requiere.

Usa la [plantilla de pull request](.github/pull_request_template.md) al abrir el PR.

## Reportar problemas de seguridad

No abras issues públicas para vulnerabilidades. Sigue la [política de seguridad](SECURITY.md).

## Licencia

Al contribuir, aceptas que tu aportación se publique bajo la misma licencia del proyecto: [MIT](LICENSE).
