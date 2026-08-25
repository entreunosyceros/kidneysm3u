# Reproductor

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

![descarga-youtube](https://github.com/user-attachments/assets/5a3592f5-3ef4-46a1-a996-be542638515e)

El reproductor es una ventana aparte: lista a la izquierda, vídeo a la derecha, controles abajo.

## Lista lateral

- **★ Favoritos** / **Todos** — filtra o restaura el listado.
- **Limpiar** — vacía la lista de esta sesión (pide confirmación). El aviso queda sobre esta ventana; no pasa al frente la principal. Si en **Preferencias** está activa «recordar última lista», al volver a abrir el programa se restaura lo último que había; si no había lista, no se muestra nada. No reproduce solo.
- Cuadro de **búsqueda** — filtra por nombre o grupo.
- Si el M3U trae `group-title`, arriba aparecen **pestañas** (pocos grupos) o un desplegable **Grupo** (muchos). En **Todos** ves las categorías (Deportes, Películas, España…); un clic entra en ese grupo. **← Grupos** o la pestaña **Todos** vuelve al listado de categorías.
- Abajo: **Sesión YouTube: OK / caducada** y **Reexportar cookies** (también en el menú **Youtube**). Si YouTube pide login o un bot-check, el indicador pasa a caducada.
- Al pasar el ratón por un título se ve el nombre completo; si hay EPG (`tvg-id` + XMLTV), también **ahora / a continuación**. Al seleccionar un canal, lo mismo aparece bajo la búsqueda. En la fila se ve el programa en curso y, si el M3U trae `tvg-logo`, una miniatura (caché local `epg_cache/`). Los logos se activan o desactivan en **Reproducir → Guía EPG → Mostrar logos de canal** o en **Preferencias**; en listas grandes conviene apagarlos para que la lista no se retrase. **Guía** o **Reproducir → Guía EPG → Parrilla…** (tecla `G`) abre una parrilla de ahora + 6 horas del grupo visible. La guía se recarga sola cada 30 minutos. Si la lista no trae URL de guía, **Desde URL…** o **Desde archivo…**. Vale una dirección tipo `get.php?username=…&password=…` que devuelva XMLTV; se usa tal cual, sin inventar otras rutas, y no se escribe en el registro.
- Si no hay `group-title` y hay miles de canales, la lista es virtual: solo se pintan las filas visibles.
- Cargar un M3U o una playlist de YouTube no bloquea la ventana: se leen en segundo plano. El cuadro de búsqueda de una lista enorme recorre los nombres fuera del hilo de la interfaz; al aplicar el resultado, pintar miles de filas aún puede congelar un instante.
- Doble clic — reproduce un canal. Un clic en una categoría abre ese grupo.
- Clic derecho — reproducir desde aquí, favoritos, descargar, eliminar un ítem o vaciar la lista.

Desde **Youtube → Buscar en YouTube** puedes **añadir a la cola**: los vídeos van a **Youtube → Cola de YouTube** (siguiente, quitar, reordenar), no a esta lista. Al terminar el vídeo en curso se reproduce el primero de esa cola.

**Reproducir → Limpiar lista lateral** hace lo mismo que el botón. No detiene el vídeo en curso. **Reproducir → Historial** lista los últimos canales IPTV, las películas a medio ver y los últimos vídeos de YouTube; **Ver historial…** abre la ventana. **Reproducir → Guía EPG → Parrilla…** abre la parrilla; **Desde URL…** / **Desde archivo…** indican el XMLTV. **Reproducir → Preferencias** abre la misma ventana que **Archivo → Preferencias** en la principal.

Los favoritos se guardan en `favoritos.json` en la carpeta del programa.

## Controles

Play/pausa (también **un clic en el vídeo** o `Espacio`), stop, **grabar** (círculo; se pone rojo mientras copia), salto atrás/adelante, **calidad / audio**, **subtítulos**, volumen, silencio, **PiP**, pantalla completa y mostrar/ocultar la lista (`≡`).

**Grabar** copia el stream actual a un fichero local con `ffmpeg -c copy` (no captura la pantalla ni descifra DRM). Un clic guarda en la **carpeta de descargas** de Preferencias, con nombre `Canal_AAAAMMDD-HHMMSS.ts`. Otro clic detiene y muestra la ruta. En **Reproducir → Grabar en…** eliges carpeta y extensión (`.ts` o `.mkv`). **Reproducir → Grabaciones…** lista lo guardado y permite reproducirlo. Hace falta `ffmpeg` en el PATH.

**PiP** (botón de la barra o **Reproducir → Ventana PiP**) pasa el vídeo a un recuadro 480×270 siempre encima, para seguir viéndolo mientras usas otra ventana. El vídeo sigue en VLC; solo cambia el recuadro. `Esc` o doble clic lo cierra. **Reproducir → Siempre encima** deja la ventana del reproductor sobre las demás. Al entrar en pantalla completa el PiP se cierra.

**Calidad / audio** (botón y menú): en YouTube eliges **360p**, **720p**, **1080p** o **mejor disponible** (también en **Preferencias**; si cambias con el vídeo en marcha, se recarga desde el segundo actual). En IPTV, si el stream trae varias pistas de audio, aparecen debajo para cambiar de idioma. YouTube solo trae una pista de audio (no hay doblajes).

Los **subtítulos** listan las pistas cuando el stream las tiene. En IPTV y VOD son las pistas embebidas que ve VLC. En YouTube el menú pone el español primero: **auto** (transcribe el audio), los del autor, o **traducción automática** (YouTube traduce; no es un doblaje). Se descarga el idioma elegido, no un archivo en caché de otro idioma.

En **pantalla completa**, menú y controles se ocultan a los 3 segundos sin usarlos. Los botones de la barra siguen sirviendo para cambiar pista: **calidad / audio** y **subtítulos** abren el menú hacia arriba para que no se salga de la pantalla.

La barra de progreso aparece en YouTube y en VOD; no en un canal en directo. Los botones de ±2 s / ±10 s y el arrastre de la barra saltan a ese punto. En YouTube retransmitido (MPEG-TS local) un salto lejano puede tardar un momento: se reinicia el vídeo desde ahí.

Al abrir un vídeo de YouTube, el área de vídeo muestra el título, la miniatura y una barra mientras se obtiene el stream, para que no parezca que se ha colgado. Si ya lo habías visto, se reanuda en el segundo guardado al cerrar o al cambiar de vídeo. En IPTV, **Historial** guarda los últimos canales. En VOD (`.mkv`/`.mp4` o rutas `movie`/`series`) también se guarda el segundo, como en YouTube; al volver a abrirlo continúa. Cerca del final se considera terminado. Los últimos vídeos de YouTube salen en esa misma ventana de historial. Las URLs no se escriben en el registro.

Si un canal IPTV no arranca (error de VLC, pantalla negra o el servidor no entrega vídeo), en unos segundos aparece el nombre y **Este canal por el momento no funciona**. No es un fallo del programa: el enlace de esa lista no está disponible ahora.

## Atajos de teclado
<p align="center">
<img width="768" height="916" alt="atajo-teclado" src="https://github.com/user-attachments/assets/5e9f075c-2e89-4e44-ae4b-76b6f96619b9" />
</p>

| Tecla | Acción |
| --- | --- |
| `Espacio` | Play / pausa |
| Clic en el vídeo | Play / pausa |
| `F1` | Pantalla completa |
| `Esc` | Salir de pantalla completa |
| `M` | Silencio |
| `←` / `→` | Retroceder / avanzar 2 s |
| `Ctrl+S` | Añadir a favoritos |
| `Ctrl+D` | Quitar de favoritos |
| `G` | Parrilla EPG (si el foco no está en un cuadro de texto) |
| `Alt+F4` | Cerrar la ventana del reproductor |

La ventana principal tiene **Ayuda → Atajos de teclado** (esta tabla) y **Ayuda → Documentación** (el manual en `docs/`).

## Bandeja del sistema

![icono_bandeja_sistema](https://github.com/user-attachments/assets/b18d710f-3f96-42ef-9032-2012f87216a3)

El icono indica que el programa sigue abierto. La X de la ventana principal **minimiza a la bandeja**. Para cerrar del todo: **Salir** en el menú.

### Ubuntu / GNOME

GNOME no muestra bien la bandeja ni su menú si no está la extensión AppIndicator:

```bash
sudo apt install gnome-shell-extension-appindicator
```

Cierra sesión y entra otra vez (o `Alt+F2`, `r`, Enter). En XFCE, MATE, Cinnamon o KDE no suele hacer falta.

## Siguiente

- [YouTube](youtube.md)
- [Listas M3U / IPTV](listas-m3u.md)
- [Notas técnicas](notas.md)

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
