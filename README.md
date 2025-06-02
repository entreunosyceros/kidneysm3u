# Kidneysm3u - Filtrado y reproducción M3U/Youtube

![about-kidneys](https://github.com/user-attachments/assets/2a90ab24-4402-42cb-8c85-5c98be00c1b2)

Esta es una aplicación de escritorio creada con Python/Tkinter para filtrar, reproducir y gestionar listas M3U/M3U8, vídeos de YouTube y canales, con soporte avanzado para archivos grandes, compatibilidad multiplataforma y manejo de errores.

> [!WARNING]  
> Este programa no incluye enlaces a ningún canal. Aun que si incluye enlaces a listas gratuitas y legales que se pueden
> encontrar en internet.

## Características principales

- **Carga y filtrado eficiente de listas M3U/M3U8 locales o por URL** (con soporte para archivos grandes y barra de búsqueda). Se pueden añadir nuevas búsquedas y sustituir o añadir el filtrado a un archivo. Si se añade la nueva búsqueda, esta se añadirá al final del archivo existente. 
- **Reproducción fluida de canales IPTV y vídeos directos** usando VLC embebido.

![descarga-youtube](https://github.com/user-attachments/assets/5a3592f5-3ef4-46a1-a996-be542638515e)

- **Reproducción de vídeos de YouTube** (URL directa, búsqueda, playlists, canales) con selección automática del mejor stream compatible (audio+vídeo juntos, sin DASH/HLS).
- **Búsqueda avanzada en YouTube**: permite buscar vídeos, listas de reproducción o canales, y reproducirlos o cargarlos en la lista. Barra de progreso de búsqueda.

![gestion-enlaces](https://github.com/user-attachments/assets/404a2382-e528-46fb-b8bc-e3a632daa0ed)

- **Gestión de favoritos**: añade, elimina y visualiza canales favoritos.
- **Descarga de vídeos** de YouTube o enlaces directos.
- **Opciones para descargar** de YouTube vídeos con audio o solo el audio de los vídeos. Para ello es necesario tener instalado ffmpeg en el equipo y añadido al PATH correctamente para que se pueda extraer el audio de los vídeos.
- **Controles multimedia completos**: play/pause, stop, avance/retroceso, volumen, mute, pantalla completa.

![reproduccion-youtube](https://github.com/user-attachments/assets/bc84bf95-b03a-4959-a8cc-ccbfeb04df32)

- **Scroll vertical en la lista de canales/vídeos**.
- **Compatibilidad multiplataforma**: Windows, Gnu/Linux.
- **Manejo de errores y dependencias**.
- **Soporte para cookies de navegador en YouTube** (para vídeos restringidos).
- **Monitor de uso de CPU** (opcional).
- **Opción Descargas**: Pequeño programa para descargar paquetes desde URL. Compatible con formatos multimedia, de imagen, de texto, etc ...

## Requisitos

- Python 3.8 o superior
- VLC Media Player instalado (y su librería python-vlc)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [tkinter](https://docs.python.org/3/library/tkinter.html) (incluido en la mayoría de instalaciones de Python)
- [psutil](https://pypi.org/project/psutil/) (opcional, para monitor de CPU)
- [browser-cookie3](https://pypi.org/project/browser-cookie3/) (opcional, para cookies de YouTube)
- [ffmpeg](https://ffmpeg.org/download.html) (opcional, para descargar solo el audio de los vídeos de YouTube)

Instala las dependencias con:

```bash
python3 -m pip install -r requirements.txt
```

> **Nota:** En Linux, asegúrate de tener instalado VLC y sus bindings para Python:
> ```bash
> sudo apt install vlc python3-vlc
> ```

Para iniciar la aplicación en linux ejecuta:
```bash
python3 run_app.py
```

## Instalación en Windows

1. Descarga e instala [VLC Media Player](https://www.videolan.org/vlc/).
   - Asegúrate de que la opción "Add to PATH" esté seleccionada durante la instalación, o añade manualmente la carpeta de VLC (`C:\Program Files\VideoLAN\VLC`) a la variable de entorno PATH.
2. Instala Python 3.8 o superior desde [python.org](https://www.python.org/downloads/).
   - Durante la instalación, marca la casilla "Add Python to PATH".
3. Abre una terminal (CMD o PowerShell) en la carpeta del proyecto y ejecuta:
   ```bash
   python -m pip install -r requirements.txt
   ```
4. Ejecuta el programa con:
   ```bash
   python main.py
   ```
   o si quieres que se cree el entorno virtual, se instalen las dependencias automáticamente y se ejecute el programa en el entorno virtual, basta con ejecutar: 

   ```bash
   python run_app.py
   ```

> **Nota:** Si tienes problemas con la reproducción de audio/vídeo en Windows, asegúrate de que VLC esté correctamente instalado y en el PATH, y que la versión de python-vlc sea compatible con tu versión de VLC.

## Uso básico

![reproduccion-m3u](https://github.com/user-attachments/assets/fa30375b-b0bf-4468-857c-07bd939968dd)

- **Cargar lista M3U/M3U8**: desde menú "Reproducir" > "Cargar URL" o "Cargar Archivo Local".
- **Buscar y reproducir vídeos/canales de YouTube**: menú "YouTube" > "Buscar en YouTube".
- **Cargar playlist de YouTube**: menú "YouTube" > "Cargar URL Playlist de YouTube".
- **Añadir/eliminar favoritos**: clic derecho sobre un canal/vídeo.
- **Descargar vídeo**: clic derecho > "Descargar".
- **Controles multimedia**: barra inferior y atajos de teclado (espacio, f, m, flechas, etc).

## Atajos de teclado

![buscar-youtube](https://github.com/user-attachments/assets/5f6f3597-b09e-4574-bb67-afdf5d8b4fe4)

- `Espacio`: Play/Pause
- `F1`: Pantalla completa
- `Esc`: Salir de pantalla completa
- `m`: Mute
- `Ctrl+S`: Añadir a favoritos
- `←/→`: Retroceder/Avanzar 2 segundos

![kidneys-help](https://github.com/user-attachments/assets/8d40f720-c424-4e1b-a965-d0796f1a93af)

Todos los atajos de telcado y una explicación básica de los controladores del reproductor, aparecen explicados en la opción de Ayuda que se puede encontrar en la ventana principal de la aplicación.

## Notas técnicas

- El reproductor usa VLC embebido y fuerza la decodificación por software y salida de audio compatible (alsa/pulse).
- Para vídeos de YouTube, se selecciona automáticamente el mejor stream compatible (audio+vídeo juntos, sin DASH/HLS, preferentemente MP4/AVC1 ≤720p).
- El filtrado y carga de listas M3U es eficiente y soporta archivos grandes. Lo he probado con una lista de más de dos millones de líneas con buenos resultados.
- El sistema de favoritos se guarda en `favoritos.json` dentro de la carpeta del programa.
- Los enlaces que se añadan al programa, también se guardaran en el archivo `enlaces.json` dentro de la carpeta del programa.
- El soporte de cookies para YouTube es opcional, pero recomendable para vídeos restringidos.

![icono_bandeja_sistema](https://github.com/user-attachments/assets/b18d710f-3f96-42ef-9032-2012f87216a3)

- El icono de la bandeja del sistema sirve para saber que el programa está abierto. Pulsar la X en la ventana principal del programa, los minimiza a la bandeja del sistema. Para cerrar el programa hay que utilizar la opción `Salir` del menú principal.

## Ordenar listas M3U desde la interfaz gráfica

![ordenar-canales](https://github.com/user-attachments/assets/24d8924d-7b99-42c0-b96a-b0172aeb65c0)

La aplicación incluye una utilidad gráfica avanzada para ordenar y gestionar listas M3U. Esta herramienta se integra en la interfaz y permite organizar, editar y personalizar tus listas de canales de forma visual e interactiva.

### ¿Qué puedes hacer con la utilidad de ordenación?

- **Ordenar canales manualmente**: arrastra y suelta (drag & drop) para reordenar los canales a tu gusto.
- **Ordenar alfabéticamente**: selecciona y mueve canales para agruparlos o reordenarlos fácilmente.
- **Buscar canales**: filtra la lista escribiendo en la barra de búsqueda.
- **Editar información**: modifica el nombre, metadatos o URL de cualquier canal.
- **Cortar, copiar, pegar y eliminar**: gestiona canales como en un editor de texto (atajos Ctrl+X, Ctrl+C, Ctrl+V, Supr).
- **Cambiar grupo**: selecciona uno o varios canales y asígnales un nuevo grupo (útil para organizar por país, temática, etc).
- **Guardar la lista ordenada**: exporta tu lista personalizada a un nuevo archivo M3U listo para usar en el reproductor.

### ¿Cómo acceder y usar la utilidad?

1. Desde la aplicación principal, busca la opción para ordenar la lista M3U (puede estar en el menú contextual o en el menú principal, según la versión).
2. Selecciona el archivo M3U que deseas organizar.
3. Se abrirá la ventana de ordenación, donde podrás:
   - Buscar canales por nombre.
   - Seleccionar uno o varios canales y moverlos con drag & drop.
   - Editar, cortar, copiar, pegar, eliminar o cambiar el grupo de los canales seleccionados.
   - Guardar la lista ordenada en un nuevo archivo M3U.

> **Nota:** Esta utilidad es completamente visual y no requiere usar la terminal. Es ideal para quienes prefieren gestionar sus listas IPTV de forma cómoda y personalizada.

### Ejemplo de uso

1. Abre la utilidad de ordenación desde la aplicación.
2. Carga tu archivo M3U original.
3. Usa la búsqueda, edición y drag & drop para dejar la lista a tu gusto.
4. Haz clic en "Guardar" y elige el nombre del nuevo archivo M3U ordenado.
5. Usa ese archivo en el reproductor para una experiencia más organizada.

Así, puedes mantener tus listas siempre ordenadas y personalizadas, sin complicaciones técnicas ni scripts de consola.

## Monitor de CPU (opcional)

Si tienes instalado el módulo `psutil`, puedes activar el monitor de uso de CPU en la interfaz del reproductor. Esto te permite ver en tiempo real el consumo de CPU del sistema mientras usas la aplicación.

### Cómo activarlo

1. Asegúrate de tener instalado `psutil` (se va a instalar automáticamente al ejecutar `run_app.py`):
   ```bash
   python -m pip install psutil
   ```
2. Si quieres ver el monitor de CPU, descomenta la línea correspondiente en el archivo `video_player.py` dentro del método `create_window`:
   ```python
   # self.setup_performance_monitoring()
   ```
   y déjala así:
   ```python
   self.setup_performance_monitoring()
   ```
3. Al iniciar el reproductor, verás una etiqueta en la parte inferior derecha con el porcentaje de uso de CPU actualizado cada segundo.

> Por defecto, el monitor está desactivado para no recargar la interfaz, pero puedes activarlo fácilmente siguiendo estos pasos.

## Problemas conocidos de la aplicación

> [!IMPORTANT]  
> Quiero aclarar que esto lo he desarrollado en su totalidad desde Linux, por lo que he podido probarlo poco en Windows. Así que es posible que puedan aparecer errores que desconozca.

- Algunos vídeos de YouTube pueden no estar disponibles si no hay streams compatibles (por restricciones de YouTube).
- En Linux, asegúrate de tener los paquetes de VLC y python-vlc correctamente instalados.
- Si el audio de YouTube no funciona, revisa la salida de audio del sistema y prueba con pulse/alsa.
- Al reproducir canales de IPTV, puede retrasarse un poco el inicio debido a la calidad de la señal del servidor al que se conecta.
- Si se está reproduciendo un vídeo, y se mueve el ratón por encima de la pantalla, por el momento parpadea. Esto deja de suceder si no mueves el ratón por encima de la pantalla del reproductor.

## Licencia

[MIT License](./LICENSE)

---

Desarrollado con Python, ☕ y cada vez menos 🚬 por entreunosyceros. ¡Disfruta de tu IPTV y YouTube (sin molestias!!) desde el escritorio!
