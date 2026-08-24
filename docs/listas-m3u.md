# Listas M3U / M3U8

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

## Carga y filtrado

La ventana principal puede leer listas locales o por URL, también si son muy grandes (se ha probado con más de dos millones de líneas). El filtrado corre en segundo plano: la ventana sigue respondiendo, puedes pulsar **Parar** y la barra de progreso se actualiza sin congelar el programa.

- Escribe un **patrón** (nombre, país, `tvg-name`, etc.).
- Puedes **sustituir** el archivo de salida o **añadir** la nueva búsqueda al final del existente.
- Los comentarios entre `#EXTINF` y la URL se ignoran; no se tratan como canales las imágenes sueltas.

Después abre el [reproductor](reproductor.md) con esa lista. También puedes cargar un M3U directo desde **Reproducir → Cargar archivo local** o **Cargar URL**. Leer y parsear el archivo va en segundo plano; pintar una lista enorme en la barra lateral aún puede tardar un momento. En el reproductor, `group-title` se ve como pestañas o un desplegable **Grupo**: primero las categorías y, al entrar, los canales.

Si el M3U trae `tvg-id` y una URL XMLTV (`url-tvg`, `x-tvg-url` o `tvg-url` en `#EXTM3U`), el reproductor descarga esa guía en segundo plano. Si no hay `tvg-id`, se intenta asociar por `tvg-name` o por el nombre del canal y el `<display-name>` del XMLTV (típico en paneles IPTV). En la lista se ve el programa en curso; al pasar el ratón o al elegir un canal, **ahora / a continuación**. **Guía** abre una parrilla de ahora + 6 horas. Si el M3U trae `tvg-logo` (o el XMLTV trae `<icon>`), se muestra una miniatura desde un caché local. No se inventan URLs de EPG: una dirección tipo `http://panel.ejemplo.cc:80/get.php?username=…&password=…` se pide tal cual (el panel suele devolver el XMLTV). Si la lista no trae guía, en el reproductor **Reproducir → Guía EPG → Desde URL…** (o **Desde archivo…**) puedes indicar una XMLTV. Esa dirección se recuerda. Al filtrar desde la ventana principal se conserva el encabezado `#EXTM3U` (incluida la URL de la guía).

Los enlaces que guardes en el gestor de enlaces quedan en `enlaces.json` dentro de la carpeta del programa.

## Reproducción IPTV

El reproductor abre la **URL que viene en el M3U** con VLC. El tipo se deduce de la extensión:

| Extensión | Tratamiento |
| --- | --- |
| `.m3u` / `.m3u8` | HLS |
| `.mkv` / `.mp4` / `.avi` / audio | Contenedor |
| `.ts` o sin extensión | Flujo (MPEG-TS u otro que detecte VLC) |

Si un `.mkv` o `.mp4` del panel IPTV se corta al abrir (el servidor redirige a otro formato), se reintenta como MPEG-TS.

Que el enlace esté bien formado no garantiza imagen: si el servidor de vídeo no entrega el archivo, VLC se quedará en negro igual que si pegas la URL en VLC a pelo. En [notas](notas.md#problemas-conocidos) hay más contexto.

## Ordenar listas desde la interfaz

<p align="center">
<img width="1922" height="1049" alt="ordenar-listas-m3u" src="https://github.com/user-attachments/assets/32d0139b-0b27-4794-8588-8fc6cd2f680c" />
</p>

Utilidad gráfica para organizar un M3U sin terminal.

### Qué puedes hacer

- Reordenar con arrastrar y soltar
- Buscar por nombre
- Editar nombre, metadatos o URL
- Cortar, copiar, pegar y eliminar (`Ctrl+X`, `Ctrl+C`, `Ctrl+V`, `Supr`)
- Cambiar el grupo de uno o varios canales
- Guardar la lista resultante en un M3U nuevo

### Cómo usarla

1. Ábrela desde la aplicación principal (menú o contextual, según la versión).
2. Elige el archivo M3U.
3. Busca, edita y reordena.
4. Guarda y usa ese archivo en el reproductor.

No hace falta la consola: es una ventana visual.

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
