# Reproductor

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

![descarga-youtube](https://github.com/user-attachments/assets/5a3592f5-3ef4-46a1-a996-be542638515e)

El reproductor es una ventana aparte: lista a la izquierda, vídeo a la derecha, controles abajo.

## Lista lateral

- **★ Favoritos** / **Todos** — filtra o restaura el listado.
- **Limpiar** — vacía la lista de esta sesión (pide confirmación). El aviso queda sobre esta ventana; no pasa al frente la principal. Si en **Preferencias** está activa «recordar última lista», al volver a abrir el programa se restaura lo último que había; si no había lista, no se muestra nada. No reproduce solo.
- Cuadro de **búsqueda** — filtra por nombre.
- Abajo: **Sesión YouTube: OK / caducada** y **Reexportar cookies** (también en el menú **Youtube**). Si YouTube pide login o un bot-check, el indicador pasa a caducada.
- Al pasar el ratón por un título se ve el nombre completo; al salir, el aviso desaparece.
- Las listas grandes se agrupan por `group-title` y cada grupo se rellena al abrirlo. Si no hay grupos y hay miles de canales, la lista es virtual: solo se pintan las filas visibles.
- Doble clic — reproduce un canal. Los grupos se abren con el triángulo; cada uno carga sus canales en ese momento.
- Clic derecho — reproducir desde aquí, favoritos, descargar, eliminar un ítem o vaciar la lista.

Desde **Youtube → Buscar en YouTube** puedes **añadir a la cola**: los vídeos se concatenan a esta lista sin cerrar la búsqueda.

**Reproducir → Limpiar lista lateral** hace lo mismo que el botón. No detiene el vídeo en curso. **Reproducir → Preferencias** abre la misma ventana que **Archivo → Preferencias** en la principal.

Los favoritos se guardan en `favoritos.json` en la carpeta del programa.

## Controles

Play/pausa, stop, salto atrás/adelante, **calidad / audio**, **subtítulos**, volumen, silencio, pantalla completa y mostrar/ocultar la lista (`≡`).

**Calidad / audio** (botón y menú): en YouTube eliges **360p** o **720p** (también en **Preferencias**; si cambias con el vídeo en marcha, se recarga desde el segundo actual). En IPTV, si el stream trae varias pistas de audio, aparecen debajo para cambiar de idioma. YouTube solo trae una pista de audio (no hay doblajes).

Los **subtítulos** listan las pistas cuando el stream las tiene. En IPTV y VOD son las pistas embebidas que ve VLC. En YouTube los subtítulos oficiales o automáticos se descargan al elegirlos.

En **pantalla completa**, menú y controles se ocultan a los 3 segundos sin usarlos. Los botones de la barra siguen sirviendo para cambiar pista.

La barra de progreso aparece en YouTube y en VOD; no en un canal en directo. Los botones de ±2 s / ±10 s y el arrastre de la barra saltan a ese punto. En YouTube retransmitido (MPEG-TS local) un salto lejano puede tardar un momento: se reinicia el vídeo desde ahí.

Al abrir un vídeo de YouTube, el área de vídeo muestra el título, la miniatura y una barra mientras se obtiene el stream, para que no parezca que se ha colgado. Si ya lo habías visto, se reanuda en el segundo guardado al cerrar o al cambiar de vídeo.

## Atajos de teclado

![kidneys-help](https://github.com/user-attachments/assets/8d40f720-c424-4e1b-a965-d0796f1a93af)

| Tecla | Acción |
| --- | --- |
| `Espacio` | Play / pausa |
| `F1` | Pantalla completa |
| `Esc` | Salir de pantalla completa |
| `M` | Silencio |
| `←` / `→` | Retroceder / avanzar 2 s |
| `Ctrl+S` | Añadir a favoritos |
| `Ctrl+D` | Quitar de favoritos |
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
