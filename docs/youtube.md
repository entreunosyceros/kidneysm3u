# YouTube

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

![reproduccion-youtube](https://github.com/user-attachments/assets/bc84bf95-b03a-4959-a8cc-ccbfeb04df32)

Desde el menú **Youtube** del [reproductor](reproductor.md) puedes pegar una URL, buscar, cargar una playlist o descargar.

## Cookies

Para buscar, ver y descargar hace falta estar **logueado en YouTube**. El programa lee la sesión del navegador o, si existe, de `cookies.txt` en la carpeta del proyecto.

`cookies.txt` **no viene en el repositorio** (es tu sesión; no lo subas a GitHub). Tampoco hace falta crearlo a mano:

1. Inicia sesión en YouTube en el navegador (el flujo más fiable es **Firefox**, con [browser-cookie3](https://pypi.org/project/browser-cookie3/)).
2. Reproduce un vídeo desde el programa. Si hay cookies válidas, se escriben solas en `cookies.txt`.
3. A partir de ahí se reutiliza ese archivo. Si no existe, se sigue leyendo el navegador.

No dejes un `cookies.txt` vacío: yt-dlp lo usaría y YouTube fallaría. Si YouTube bloquea la extracción, instala **Node** o **Deno**: yt-dlp los usa para los retos de la web.

## Búsqueda

![buscar-youtube](https://github.com/user-attachments/assets/5f6f3597-b09e-4574-bb67-afdf5d8b4fe4)

**Youtube → Buscar en YouTube**. Filtros:

| Tipo | Qué lista |
| --- | --- |
| Vídeos | Resultados normales |
| **Shorts** | Solo URLs `/shorts/` (hashtag + filtro de YouTube) |
| Listas de reproducción | Playlists |
| Canales | Canales (se abren en el navegador) |

También puedes filtrar por fecha, duración (no aplica a Shorts) y número de resultados.

- Doble clic o **Reproducir** añade el vídeo a la lista lateral y lo pone en marcha.
- Una **lista** se carga entera en la barra lateral.
- Un **canal** se abre en el navegador.

Las URLs `youtube.com/shorts/...` se reconocen al pegarlas o al elegir un Short de la búsqueda.

## Playlists

**Youtube → Cargar Playlist de YouTube** (o desde el resultado de una lista). Los vídeos pasan a la lista de la izquierda y se pueden seguir con **Reproducir desde aquí**.

## Descargas

![descarga-youtube](https://github.com/user-attachments/assets/5a3592f5-3ef4-46a1-a996-be542638515e)

- Vídeo + audio, o **solo audio** (hace falta `ffmpeg` en el PATH).
- Desde la búsqueda, el menú contextual o **Youtube → Descargar vídeo de YouTube**.
- En la ventana principal, **Descargas** sirve para bajar cualquier URL (vídeo, imagen, texto, etc.).

## Cómo se reproduce

yt-dlp elige un stream que VLC pueda abrir (audio y vídeo juntos cuando es posible). Si el directo falla, se retransmite por un servidor local. La barra de progreso es para YouTube y VOD, no para un directo IPTV.

Si el vídeo tiene subtítulos, el reproductor los ofrece en **Subtítulos** (oficiales primero; los automáticos llevan «auto»). Los doblajes de YouTube no se pueden elegir: el stream solo trae una pista de audio. Detalle en [reproductor](reproductor.md#controles).

Si un vídeo no está disponible (restricción de YouTube o sin stream compatible), no hay alternativa dentro del programa. Ver [notas](notas.md#problemas-conocidos).

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
