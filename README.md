# Kidneysm3u
![about-kidneysm3u](https://github.com/user-attachments/assets/1ded588f-0fed-4432-afcd-7e00f782fcae)

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![VLC](https://img.shields.io/badge/VLC-Embedded-orange?logo=vlc)


Aplicación de escritorio en Python/Tkinter para filtrar, reproducir y gestionar listas M3U/M3U8, IPTV y YouTube (vídeos, Shorts, listas y canales).

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
| [Uso](docs/uso.md) | Cómo empezar: cargar una lista, reproducir y preferencias |
| [Listas M3U](docs/listas-m3u.md) | Carga, filtro y ordenación de listas |
| [YouTube](docs/youtube.md) | Búsqueda, Shorts, playlists, cookies, yt-dlp y descargas |
| [Reproductor](docs/reproductor.md) | Controles, atajos, PiP, grabación, lista lateral y bandeja |
| [Notas](docs/notas.md) | Detalles técnicos, tests, monitor de CPU y problemas conocidos |

Cada página enlaza al resto y vuelve a este inicio. En el programa: **Ayuda → Documentación** (se lee en la propia ventana).

## Qué puedes hacer

- Cargar y filtrar listas M3U/M3U8 locales o por URL (archivos grandes incluidos).
- Reproducir IPTV y ficheros directos con VLC embebido (zap por número de la lista).
- Buscar y reproducir YouTube: vídeos, **Shorts**, listas y canales.
- Ver la guía EPG en parrilla (ahora + unas horas), con logos de canal y recarga automática.
- Historial de canales IPTV y seguir viendo películas/VOD desde el segundo guardado.
- Ventana PiP y reproductor siempre encima.
- Ajustar el buffer de los canales IPTV (rápido, equilibrado o estable).
- Gestionar la lista lateral (favoritos, exportar/importar, limpiar, reproducir desde aquí).
- Grabar el canal o vídeo en reproducción a un fichero local (hace falta [ffmpeg](https://ffmpeg.org/download.html)).
- Descargar vídeos o solo audio (también hace falta ffmpeg).
- Ordenar listas M3U desde la interfaz.
- Ajustar tema, volumen, descargas, cookies, calidad de YouTube, buffer IPTV, estilo de subtítulos y avisos de versión nueva en **Preferencias**.
- Comprobar si hay una versión nueva (**Ayuda → Buscar actualizaciones**) e instalar el `.exe` o el `.deb` desde GitHub Releases.

Más detalle en las páginas de [uso](docs/uso.md), [listas M3U](docs/listas-m3u.md) y [YouTube](docs/youtube.md).

## Contribuir

Issues y pull requests son bienvenidos. Lee [CONTRIBUTING.md](CONTRIBUTING.md), el [código de conducta](CODE_OF_CONDUCT.md) y [SECURITY.md](SECURITY.md) para vulnerabilidades.

## Licencia

[MIT License](./LICENSE)

---

Desarrollado con Python, ☕ y cada vez menos 🚬 por entreunosyceros.
