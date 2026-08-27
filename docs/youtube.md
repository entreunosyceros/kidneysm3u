# YouTube

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

![cargando-video-youtube](https://github.com/user-attachments/assets/a9405356-8fa6-456e-8e65-f14326124ead)

Desde el menú **Youtube** del [reproductor](reproductor.md) puedes pegar una URL, buscar, cargar una playlist o descargar.

## Cookies

Para buscar, ver y descargar hace falta estar **logueado en YouTube**. El programa lee la sesión del navegador o, si existe, de `cookies.txt` en la carpeta del proyecto.

`cookies.txt` **no viene en el repositorio** (es tu sesión; no lo subas a GitHub). Tampoco hace falta crearlo a mano:

1. Inicia sesión en YouTube en **Firefox** (con [browser-cookie3](https://pypi.org/project/browser-cookie3/)). En Preferencias el navegador de cookies es **Automático** o **Firefox**.
2. Reproduce un vídeo desde el programa, o pulsa **Reexportar cookies**. Si hay login vigente, se escribe `cookies.txt`.
3. A partir de ahí se reutiliza ese archivo. Si no existe, se sigue leyendo el navegador. El programa recorta tokens `ST-` caducados (muy habituales en Firefox): si se envían todos, YouTube responde **413 Request Entity Too Large** y la búsqueda falla.

### Windows: Firefox, no Chrome, Brave ni Edge

En Windows, Chrome, Brave, Chromium y Edge cifran las cookies (App-Bound Encryption) y el programa no puede leerlas. Preferencias no ofrece esos navegadores: solo **Automático** y **Firefox**. Automático sigue intentando leer otros perfiles por si el sistema lo permite (en Linux a veces sí); en Windows lo fiable es Firefox.

Pasos:

1. Abre **Firefox**, entra en youtube.com e inicia sesión.
2. Cierra Firefox (si queda abierto, el archivo de cookies puede estar bloqueado).
3. En el programa: **Youtube → Reexportar cookies**.

En el reproductor (abajo a la izquierda) y en la búsqueda verás **Sesión YouTube: OK** o **caducada**. Lo mismo aparece en el menú **Youtube**. Si YouTube pide captcha o «confirma que no eres un robot», el indicador pasa a caducada y puedes reexportar; no se traga el fallo en silencio.

No se escribe un `cookies.txt` vacío ni uno sin cookies de login: yt-dlp lo usaría y YouTube fallaría. Si YouTube bloquea la extracción, instala **Node** o **Deno**: yt-dlp los usa para los retos de la web.

## Actualizar yt-dlp

YouTube cambia el extractor a menudo. Si deja de reproducir, buscar o descargar y las cookies están bien, actualiza yt-dlp:

- **Archivo → Preferencias** (o **Reproducir → Preferencias**) → **Actualizar yt-dlp**
- En el reproductor: **Youtube → Actualizar yt-dlp**

Usa el mismo Python del programa (`python -m pip install --upgrade yt-dlp[default]`). Después **cierra y vuelve a abrir** el programa: el módulo ya cargado no cambia hasta entonces. No sustituye a **Reexportar cookies**.

Si arrancas el Python del sistema (sin `.venv`), Ubuntu puede bloquear `pip` (PEP 668). En ese caso usa `python3 run_app.py`.

## Búsqueda

![buscar-listas-youtube](https://github.com/user-attachments/assets/b5563240-7b57-4f70-8591-21a77dd01852)

**Youtube → Buscar en YouTube**. Filtros:

| Tipo | Qué lista |
| --- | --- |
| Vídeos | Resultados normales |
| **Shorts** | Pestaña Shorts del canal (si el nombre o `@handle` coincide) o búsqueda `/shorts/` |
| Listas de reproducción | Playlists |
| Canales | Canales (doble clic: vídeos recientes en esta ventana) |

También puedes filtrar por fecha, duración (no aplica a Shorts) y número de resultados. **Ordenar por Fecha** muestra primero lo más reciente: si buscas un canal (`@nombre` o el nombre exacto), abre su pestaña de vídeos o Shorts; si no, ordena los resultados de búsqueda. Debajo del campo aparecen las **5 últimas búsquedas** (con tipo y filtros): un clic en cualquiera las vuelve a lanzar. Si no cabe todo, la ventana tiene **barra de desplazamiento** vertical (la rueda del ratón también).

- Doble clic o **Reproducir** añade el vídeo a la lista lateral y lo pone en marcha (cierra la búsqueda). Al terminar un vídeo suelto, el reproductor pregunta si quieres **volver a verlo**. Si hay cola, una playlist o **Reproducir desde aquí**, pasa al siguiente y no pregunta.
- **Añadir a la cola** (o clic derecho) lo deja en la **cola de YouTube**, una lista aparte (**Youtube → Cola de YouTube**): siguiente, quitar, subir/bajar. No se mezcla con la lista IPTV. Puedes marcar varios con Ctrl o Mayús. `Ctrl+Enter` hace lo mismo.
- **Añadir a favoritos**: pulsa **☆** al inicio de la fila (pasa a **★**; otro clic lo quita), el botón de abajo, clic derecho o `Ctrl+S`. Quedan en ★ Favoritos del reproductor.
- Una **lista**: **Cargar lista** sustituye la barra lateral; **Añadir lista a la cola** mete esos vídeos en la cola.
- Un **canal**: doble clic o **Ver vídeos recientes** lista las subidas nuevas aquí mismo (no solo abre el navegador). **Añadir recientes a la cola** encola esos vídeos. Pulsa **☆** en el nombre para guardarlo. Desde **★ Favoritos**, un canal abre sus vídeos recientes y reproduce el primero (no es un ID de vídeo). El navegador sigue disponible en el menú contextual.

Las URLs `youtube.com/shorts/...` se reconocen al pegarlas o al elegir un Short de la búsqueda.

## Playlists
![reproduciendo-lista](https://github.com/user-attachments/assets/dee90af9-0002-4c7b-990f-04c2f5781817)

**Youtube → Cargar Playlist de YouTube** (o desde el resultado de una lista). Los vídeos pasan a la lista de la izquierda y se pueden seguir con **Reproducir desde aquí**.

## Descargas

![descarga-youtube](https://github.com/user-attachments/assets/e60eefc5-4765-420f-a282-b44c1c096e8a)

- Vídeo + audio, o **solo audio** (hace falta `ffmpeg` en el PATH).
- Desde la búsqueda, el menú contextual o **Youtube → Descargar vídeo de YouTube**.
- En la ventana principal, **Archivo → Descargar** sirve para bajar cualquier URL (vídeo, imagen, texto, etc.). Puedes marcar **abrir el gestor de archivos al terminar** para que muestre el fichero guardado; esa casilla se recuerda. Las últimas URLs usadas aparecen en esa misma ventana: un clic las pone en el campo, **doble clic** las vuelve a descargar, y **Ctrl+C** o clic derecho copia la URL (Ctrl+V la pega).
- La carpeta inicial se elige en **Archivo → Preferencias**. Los botones de la ventana de descarga quedan fijos abajo.

## Cómo se reproduce

yt-dlp elige un stream que VLC pueda abrir (audio y vídeo juntos cuando es posible). Mientras carga, el reproductor muestra el título, la miniatura y una barra para que no parezca colgado. Extraer el stream y las playlists no bloquea la interfaz.

Si el directo falla, se usa un archivo de la caché si ya es jugable (MP4, MKV, WebM, etc.) **sin remuxear** a MPEG-TS. Solo si hace falta se retransmite por un servidor local. La caché vive en el directorio temporal del sistema (`kidneysm3u_yt_cache`), se recorta a unos **500 MB** (borra lo más antiguo) y no se vacía al cerrar. Los temporales de retransmisión (`kidneys_yt_*`) sí se borran al cerrar o al cambiar de vídeo. La barra de progreso es para YouTube y VOD, no para un directo IPTV.

Si cierras el reproductor o cambias de vídeo, se guarda el segundo. Al volver a abrirlo (también en una lista o desde **Historial**) continúa desde ahí, salvo que estuvieras al principio o casi al final. No se reproduce solo al restaurar la sesión. Los últimos vídeos de YouTube aparecen en la misma ventana de **Historial** que el IPTV.

Si el vídeo tiene subtítulos, el menú **Subtítulos** pone el español primero: transcripción automática (**auto**) si el vídeo está en español, los del autor, y **traducción automática** si el audio es de otro idioma. Esa última pide el VTT con `tlang` (el json3 de YouTube a menudo se queda en inglés). El archivo se convierte a SRT de una línea, anclado abajo, para que VLC aplique el estilo de **Preferencias → Subtítulos** sin ir subiendo por la pantalla. En **Calidad / audio** puedes pedir 360p, 720p, 1080p o **mejor disponible**; los doblajes de YouTube no se pueden elegir (el stream solo trae una pista de audio). Detalle en [reproductor](reproductor.md#controles).

Si un vídeo no está disponible (restricción de YouTube o sin stream compatible), no hay alternativa dentro del programa. Ver [notas](notas.md#problemas-conocidos).

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
