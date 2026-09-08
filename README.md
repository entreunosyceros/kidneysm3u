# Kidneysm3u
![about-kidneysm3u](https://github.com/user-attachments/assets/1ded588f-0fed-4432-afcd-7e00f782fcae)

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![VLC](https://img.shields.io/badge/VLC-Embedded-orange?logo=vlc)


Aplicación de escritorio en Python/Tkinter para filtrar, reproducir y gestionar listas M3U/M3U8 e IPTV, además de **YouTube**, **Twitch** y **Kick** (directos, VOD y búsqueda), con VLC embebido y yt-dlp.

> [!WARNING]
> Este programa no incluye enlaces a ningún canal. Sí puede apuntar a listas públicas y legales que se encuentren en internet.

## Inicio rápido

```bash
python3 run_app.py
```

Si no existe `.venv`, se crea solo e instala lo de `requirements.txt`. La primera vez tarda más. Instrucciones por sistema: [instalación](docs/instalacion.md).

## Documentación

| Tema | Contenido |
| --- | --- |
| [Índice](docs/README.md) | Mapa de toda la documentación |
| [Instalación](docs/instalacion.md) | Requisitos, Ubuntu, Windows, entorno virtual y actualizar el programa |
| [Uso](docs/uso.md) | Empezar: M3U, preferencias, YouTube, **Twitch**, **Kick** y biblioteca |
| [Listas M3U](docs/listas-m3u.md) | Carga, filtro y ordenación de listas |
| [YouTube](docs/youtube.md) | Búsqueda, Shorts, playlists, cookies, yt-dlp y descargas |
| [Reproductor](docs/reproductor.md) | Controles, atajos, PiP, grabación, lista lateral, favoritos y bandeja |
| [Notas](docs/notas.md) | Detalles técnicos, tests, monitor de CPU y problemas conocidos |

Cada página enlaza al resto y vuelve a este inicio. En el programa: **Ayuda → Documentación** (se lee en la propia ventana).

## Qué puedes hacer

### IPTV y listas
- Cargar y filtrar listas M3U/M3U8 locales o por URL (archivos grandes incluidos).
- Reproducir IPTV y ficheros directos con VLC embebido (zap por número de la lista).
- Ver la guía EPG en parrilla (ahora + unas horas), con logos de canal y recarga automática.
- Ajustar el buffer IPTV (rápido, equilibrado o estable) y grabar el stream en curso (`ffmpeg`).

### YouTube, Twitch y Kick
- **YouTube** — buscar y reproducir vídeos, Shorts, listas y canales; cola; subtítulos; cookies y actualización de yt-dlp.
- **Twitch** — URL de directo/VOD/clip, búsqueda, VODs del canal, chat en vivo, favoritos, recientes y reanudación de VOD.
- **Kick** — URL de directo/VOD/clip, búsqueda, VODs del canal, favoritos, recientes, cookies y ayuda con Cloudflare (`curl-cffi`).

### Biblioteca y sesión
- **Favoritos → Biblioteca…** — favoritos e historial de IPTV, YouTube, Twitch y Kick en un solo sitio, con filtros por sección y fuente.
- Historial y «seguir viendo» (VOD) desde el menú **Reproducir → Historial**.
- Exportar e importar favoritos; recordar la última lista lateral (sin autoplay).

### Más
- Ventana PiP y reproductor siempre encima.
- Descargar vídeos o solo audio (`ffmpeg`).
- Ordenar listas M3U desde la interfaz.
- Preferencias: tema, volumen, descargas, cookies (YouTube/Twitch/Kick), calidad por plataforma, buffer IPTV, subtítulos, modo ligero y avisos de versión.
- Comprobar actualizaciones (**Ayuda → Buscar actualizaciones**) e instalar el `.exe` o el `.deb` desde GitHub Releases.

Guía rápida: [uso](docs/uso.md). Detalle de listas: [listas M3U](docs/listas-m3u.md). YouTube a fondo: [YouTube](docs/youtube.md).

## Contribuir

Issues y pull requests son bienvenidos. Lee [CONTRIBUTING.md](CONTRIBUTING.md), el [código de conducta](CODE_OF_CONDUCT.md) y [SECURITY.md](SECURITY.md) para vulnerabilidades.

## Licencia

[MIT License](./LICENSE)

---

Desarrollado con Python, ☕ y cada vez menos 🚬 por entreunosyceros.
