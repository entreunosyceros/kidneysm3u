# Kidneysm3u
<p align="center">
<img width="902" height="693" alt="about-kidneysm3u" src="https://github.com/user-attachments/assets/1ded588f-0fed-4432-afcd-7e00f782fcae" />
</p>
<p align="center">
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![VLC](https://img.shields.io/badge/VLC-Embedded-orange?logo=vlc)
</p>

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
| [Instalación](docs/instalacion.md) | Requisitos, Ubuntu, Windows y entorno virtual |
| [Uso](docs/uso.md) | Cómo empezar: cargar una lista, reproducir y preferencias |
| [Listas M3U](docs/listas-m3u.md) | Carga, filtro y ordenación de listas |
| [YouTube](docs/youtube.md) | Búsqueda, Shorts, playlists, cookies y descargas |
| [Reproductor](docs/reproductor.md) | Controles, atajos, favoritos, lista lateral y bandeja |
| [Notas](docs/notas.md) | Detalles técnicos, tests, monitor de CPU y problemas conocidos |

Cada página enlaza al resto y vuelve a este inicio. En el programa: **Ayuda → Documentación** (se lee en la propia ventana).

## Qué puedes hacer

- Cargar y filtrar listas M3U/M3U8 locales o por URL (archivos grandes incluidos).
- Reproducir IPTV y ficheros directos con VLC embebido.
- Buscar y reproducir YouTube: vídeos, **Shorts**, listas y canales.
- Ver la guía EPG en parrilla (ahora + unas horas), con logos de canal y recarga automática.
- Historial de canales IPTV y seguir viendo películas/VOD desde el segundo guardado.
- Gestionar la lista lateral (favoritos, limpiar, reproducir desde aquí).
- Descargar vídeos o solo audio (hace falta [ffmpeg](https://ffmpeg.org/download.html)).
- Ordenar listas M3U desde la interfaz.
- Ajustar tema, volumen, descargas, cookies y calidad de YouTube en **Preferencias**.

Más detalle en las páginas de [uso](docs/uso.md), [listas M3U](docs/listas-m3u.md) y [YouTube](docs/youtube.md).

## Licencia

[MIT License](./LICENSE)

---

Desarrollado con Python, ☕ y cada vez menos 🚬 por entreunosyceros.
