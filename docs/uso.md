# Uso básico

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

![reproduccion-m3u](https://github.com/user-attachments/assets/fa30375b-b0bf-4468-857c-07bd939968dd)

## Arrancar

En Linux (y en Windows si usas el entorno del proyecto):

```bash
python3 run_app.py
```

En Ubuntu con el `.deb`, el comando es `kidneysm3u`.

Si GitHub tiene una versión más nueva, al abrir puede salir un aviso. Detalle (aviso al arrancar, **Ayuda → Buscar actualizaciones**, Preferencias y código fuente): [instalación](instalacion.md#actualizar-el-programa).

## Ventana principal

Desde aquí filtras o abres listas y lanzas el reproductor. El flujo habitual:

1. Indica un patrón de búsqueda (por ejemplo un país o un nombre).
2. Carga un archivo M3U local o una URL de lista.
3. Elige si **sustituyes** el archivo de salida o **añades** los resultados al final.
4. Abre el [reproductor](reproductor.md) con la lista resultante.

El filtrado no bloquea la ventana: puedes moverla o pulsar **Parar** mientras corre.

## Preferencias

**Archivo → Preferencias** (también **Reproducir → Preferencias** en el reproductor). La ventana se puede desplazar; **Guardar** y **Cancelar** quedan fijos abajo.

| Apartado | Qué hace |
| --- | --- |
| Tema | Oscuro o claro. El botón **Tema claro/oscuro** de la cabecera solo cambia esto. |
| Logos de canal | Miniaturas `tvg-logo` en la lista y en la parrilla. En listas grandes conviene apagarlos. |
| Volumen por defecto | Al abrir el reproductor. |
| Calidad YouTube | Tope de altura: 360p, 720p, 1080p o **Mejor**. Si cambias con un vídeo en marcha, se recarga desde el segundo actual. |
| Buffer IPTV | **Rápido**, **Equilibrado** (por defecto) o **Estable**. El siguiente canal ya usa el valor. Detalle en [listas M3U](listas-m3u.md#buffer-iptv). |
| Subtítulos | Tamaño, color, opacidad, contorno, caja de fondo (color y transparencia), margen y retraso. Solo afecta a subtítulos de texto (SRT, YouTube). En YouTube se recarga el vídeo al guardar; en IPTV, al siguiente canal. |
| Recordar última lista | Restaura la lista lateral al abrir; no reproduce solo. |
| Avisar de versiones nuevas | Al abrir, si GitHub tiene un paquete más nuevo. Casilla **Actualizaciones**. Se puede apagar. Detalle en [instalación](instalacion.md#actualizar-el-programa). |
| Carpeta de descargas | Destino inicial de vídeos, audio y grabaciones. |
| Navegador de cookies | **Automático** o **Firefox**. Automático prueba Firefox y, si puede, otros navegadores. En Windows, Chrome, Brave y Edge cifran las cookies y no se pueden leer: usa Firefox. Detalle en [YouTube](youtube.md#cookies). |
| yt-dlp | Muestra la versión e **Actualizar yt-dlp**. Después hay que cerrar y abrir el programa. |

Detalle del filtro y de la herramienta de ordenar: [listas M3U](listas-m3u.md).

## Reproductor

En el menú **Reproducir**:

- **Cargar URL** — lista M3U remota o enlace de vídeo.
- **Cargar archivo local** — `.m3u`, `.m3u8` o un fichero de vídeo.
- **Guía EPG → Parrilla…** — parrilla de ahora + unas horas (también el botón **Guía** o la tecla `G`).
- **Guía EPG → Mostrar logos de canal** — miniaturas en la lista y en la parrilla. En listas grandes, desactívalo.
- **Guía EPG → Desde URL…** — guía XMLTV remota (`http`/`https`). Sirve una URL tipo `get.php?username=…&password=…` que devuelva el XMLTV; se usa tal cual.
- **Guía EPG → Desde archivo…** — guía XMLTV local (`.xml`, `.xml.gz`).
- **Historial** — últimos canales IPTV, **seguir viendo** en películas/VOD y últimos vídeos de YouTube. También **Ver historial…**.
- **Grabar / detener**, **Grabar en…**, **Grabaciones…** — copia local del stream en reproducción (hace falta `ffmpeg`). Detalle en [reproductor](reproductor.md).
- **Ventana PiP** / **Siempre encima** — recuadro flotante o ventana del reproductor sobre las demás.
- **Limpiar lista lateral** — vacía el listado de la izquierda (pide confirmación).

Doble clic en un canal para reproducirlo. Clic derecho: favoritos, descarga, eliminar o **Reproducir desde aquí** (sigue la lista hasta el final, sin repetir). En la búsqueda, **★ Añadir** o `Ctrl+S` guarda el resultado en favoritos.

La sesión puede recordar la última lista lateral y el último canal **seleccionado**, no lo reproduce solo al abrir. Eso se activa o desactiva en **Preferencias**. **Limpiar** solo vacía la lista en esta sesión; si «recordar última lista» está activo, al arrancar de nuevo se muestra lo último que había. Si no había lista, no muestra nada.

## YouTube

Menú **Youtube**:

- Buscar vídeos, Shorts, listas o canales (un canal lista subidas recientes)
- Pegar una URL (también `youtube.com/shorts/...`)
- Cola de YouTube (siguiente, quitar, reordenar)
- Cargar una playlist como lista lateral
- Actualizar yt-dlp (también en Preferencias)

En **Windows** las cookies de YouTube hay que sacarlas de **Firefox** (Chrome, Brave y Edge las cifran). En Preferencias deja **Automático** o **Firefox**, inicia sesión en Firefox, ciérralo y pulsa **Reexportar cookies**. Guía: [YouTube](youtube.md#cookies).

## Ayuda

En el menú **Ayuda** de la ventana principal:

- **Atajos de teclado** — teclas y botones del reproductor.
- **Documentación** — este manual se lee dentro de la propia ventana (temas a la izquierda, capturas incluidas). Las imágenes se cargan de GitHub; hace falta red.
- **Buscar actualizaciones** — consulta GitHub Releases **ahora** (aunque el aviso al arrancar falle, esté desactivado o ya se hubiera mirado hoy). La barra de estado indica si busca, si hay versión nueva, si ya estás al día o si falló la red. Si hay paquete para tu sistema, el diálogo **Actualizar** / **Más tarde** / **No avisarme** es el mismo que al abrir. Quien usa el código fuente solo abre la página de lanzamientos. Guía completa: [actualizar el programa](instalacion.md#actualizar-el-programa).

## Cerrar el programa

La X de la ventana principal **minimiza a la bandeja**, no cierra. Para salir usa **Salir** en el menú. Más en [reproductor (bandeja)](reproductor.md#bandeja-del-sistema).

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
