# Reproductor

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

![descarga-youtube](https://github.com/user-attachments/assets/5a3592f5-3ef4-46a1-a996-be542638515e)

El reproductor es una ventana aparte: lista a la izquierda, vídeo a la derecha, controles abajo.

## Lista lateral

- **★ Favoritos** / **Todos** — filtra o restaura el listado.
- **Limpiar** — vacía la lista de esta sesión (pide confirmación). El aviso queda sobre esta ventana; no pasa al frente la principal. Al volver a abrir el programa se restaura lo último que había; si no había lista, no se muestra nada. No reproduce solo.
- Cuadro de **búsqueda** — filtra por nombre.
- Doble clic — reproduce.
- Clic derecho — reproducir desde aquí, favoritos, descargar, eliminar un ítem o vaciar la lista.

**Reproducir → Limpiar lista lateral** hace lo mismo que el botón. No detiene el vídeo en curso.

Los favoritos se guardan en `favoritos.json` en la carpeta del programa.

## Controles

Play/pausa, stop, salto atrás/adelante, **audio**, **subtítulos**, volumen, silencio, pantalla completa y mostrar/ocultar la lista (`≡`).

Los botones de audio y subtítulos (y los menús **Audio** / **Subtítulos**) listan las pistas cuando el stream las tiene. En IPTV y VOD son las pistas embebidas que ve VLC (hace falta más de una de audio para poder elegir). En YouTube los subtítulos oficiales o automáticos se descargan al elegirlos; el audio extra (doblajes) no está, porque el vídeo llega en una sola pista.

En **pantalla completa**, menú y controles se ocultan a los 3 segundos sin usarlos. Los botones de la barra siguen sirviendo para cambiar pista.

La barra de progreso aparece en YouTube y en VOD; no en un canal en directo. Los botones de ±2 s / ±10 s y el arrastre de la barra saltan a ese punto. En YouTube retransmitido (MPEG-TS local) un salto lejano puede tardar un momento: se reinicia el vídeo desde ahí.

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
