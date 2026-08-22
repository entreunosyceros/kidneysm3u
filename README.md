# Kidneysm3u

![about-kidneys](https://github.com/user-attachments/assets/2a90ab24-4402-42cb-8c85-5c98be00c1b2)

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
| [Uso](docs/uso.md) | Cómo empezar: cargar una lista y reproducir |
| [Listas M3U](docs/listas-m3u.md) | Carga, filtro y ordenación de listas |
| [YouTube](docs/youtube.md) | Búsqueda, Shorts, playlists, cookies y descargas |
| [Reproductor](docs/reproductor.md) | Controles, atajos, favoritos, lista lateral y bandeja |
| [Notas](docs/notas.md) | Detalles técnicos, monitor de CPU y problemas conocidos |

Cada página enlaza al resto y vuelve a este inicio. En el programa: **Ayuda → Documentación** (se lee en la propia ventana).

## Qué puedes hacer

- Cargar y filtrar listas M3U/M3U8 locales o por URL (archivos grandes incluidos).
- Reproducir IPTV y ficheros directos con VLC embebido.
- Buscar y reproducir YouTube: vídeos, **Shorts**, listas y canales.
- Gestionar la lista lateral (favoritos, limpiar, reproducir desde aquí).
- Descargar vídeos o solo audio (hace falta [ffmpeg](https://ffmpeg.org/download.html)).
- Ordenar listas M3U desde la interfaz.

Más detalle en las páginas de [uso](docs/uso.md), [listas M3U](docs/listas-m3u.md) y [YouTube](docs/youtube.md).

## Licencia

[MIT License](./LICENSE)

---

Desarrollado con Python, ☕ y cada vez menos 🚬 por entreunosyceros.
