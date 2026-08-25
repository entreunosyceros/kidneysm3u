# Uso básico

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

![reproduccion-m3u](https://github.com/user-attachments/assets/fa30375b-b0bf-4468-857c-07bd939968dd)

## Arrancar

En Linux (y en Windows si usas el entorno del proyecto):

```bash
python3 run_app.py
```

En Ubuntu con el `.deb`, el comando es `kidneysm3u`.

## Ventana principal

Desde aquí filtras o abres listas y lanzas el reproductor. El flujo habitual:

1. Indica un patrón de búsqueda (por ejemplo un país o un nombre).
2. Carga un archivo M3U local o una URL de lista.
3. Elige si **sustituyes** el archivo de salida o **añades** los resultados al final.
4. Abre el [reproductor](reproductor.md) con la lista resultante.

El filtrado no bloquea la ventana: puedes moverla o pulsar **Parar** mientras corre.

En **Archivo → Preferencias** (también **Reproducir → Preferencias** en el reproductor) unificas tema, logos de canal, volumen por defecto, carpeta de descargas, navegador de cookies, calidad de YouTube y si se recuerda la última lista. El botón **Tema claro/oscuro** de la cabecera sigue sirviendo para cambiar solo el tema.

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
- **Limpiar lista lateral** — vacía el listado de la izquierda (pide confirmación).

Doble clic en un canal para reproducirlo. Clic derecho: favoritos, descarga, eliminar o **Reproducir desde aquí** (sigue la lista hasta el final, sin repetir).

La sesión puede recordar la última lista lateral y el último canal **seleccionado**, no lo reproduce solo al abrir. Eso se activa o desactiva en **Preferencias**. **Limpiar** solo vacía la lista en esta sesión; si «recordar última lista» está activo, al arrancar de nuevo se muestra lo último que había. Si no había lista, no muestra nada.

## YouTube

Menú **Youtube**:

- Buscar vídeos, Shorts, listas o canales (un canal lista subidas recientes)
- Pegar una URL (también `youtube.com/shorts/...`)
- Cola de YouTube (siguiente, quitar, reordenar)
- Cargar una playlist como lista lateral

Guía completa: [YouTube](youtube.md).

## Ayuda

En el menú **Ayuda** de la ventana principal:

- **Atajos de teclado** — teclas y botones del reproductor.
- **Documentación** — este manual se lee dentro de la propia ventana (temas a la izquierda y enlaces entre páginas).

## Cerrar el programa

La X de la ventana principal **minimiza a la bandeja**, no cierra. Para salir usa **Salir** en el menú. Más en [reproductor (bandeja)](reproductor.md#bandeja-del-sistema).

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
