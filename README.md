# Riñones M3U - Filtrado y reproducción M3U/Youtube

![about-kidneys](https://github.com/user-attachments/assets/2f7e3bf4-5180-4e19-9358-297ab4ea9bf0)

Aplicación de escritorio en Python/Tkinter para filtrar, reproducir y gestionar listas M3U/M3U8, vídeos de YouTube y canales, con soporte avanzado para archivos grandes, compatibilidad multiplataforma y manejo de errores.

## Características principales

- **Carga y filtrado eficiente de listas M3U/M3U8 locales o por URL** (con soporte para archivos grandes y barra de búsqueda).
- **Reproducción fluida de canales IPTV y vídeos directos** usando VLC embebido.
- **Reproducción de vídeos de YouTube** (URL directa, búsqueda, playlists, canales) con selección automática del mejor stream compatible (audio+vídeo juntos, sin DASH/HLS).
- **Búsqueda avanzada en YouTube**: permite buscar vídeos, listas de reproducción o canales, y reproducirlos o cargarlos en la lista.
- **Gestión de favoritos**: añade, elimina y visualiza canales favoritos.
- **Descarga de vídeos** de YouTube o enlaces directos.
- **Controles multimedia completos**: play/pause, stop, avance/retroceso, volumen, mute, pantalla completa.

![reproducir-youtube](https://github.com/user-attachments/assets/c40091d3-ab90-4c0f-b942-574dbc563a8d)

- **Scroll vertical en la lista de canales/vídeos**.
- **Compatibilidad multiplataforma**: Windows, Gnu/Linux.
- **Manejo de errores y dependencias**.
- **Soporte para cookies de navegador en YouTube** (para vídeos restringidos).
- **Monitor de uso de CPU** (opcional).

## Requisitos

- Python 3.8 o superior
- VLC Media Player instalado (y su librería python-vlc)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [tkinter](https://docs.python.org/3/library/tkinter.html) (incluido en la mayoría de instalaciones de Python)
- [psutil](https://pypi.org/project/psutil/) (opcional, para monitor de CPU)
- [browser-cookie3](https://pypi.org/project/browser-cookie3/) (opcional, para cookies de YouTube)

Instala las dependencias con:

```bash
python -m pip install -r requirements.txt
```

> **Nota:** En Linux, asegúrate de tener instalado VLC y sus bindings para Python:
> ```bash
> sudo apt install vlc python3-vlc
> ```

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
   o
   ```bash
   python run_app.py
   ```

> **Nota:** Si tienes problemas con la reproducción de audio/vídeo en Windows, asegúrate de que VLC esté correctamente instalado y en el PATH, y que la versión de python-vlc sea compatible con tu versión de VLC.

## Uso básico

![reproduccion-m3u](https://github.com/user-attachments/assets/fa30375b-b0bf-4468-857c-07bd939968dd)

- **Cargar lista M3U/M3U8**: desde menú "Reproducir" > "Cargar URL" o "Cargar Archivo Local".
- **Buscar y reproducir vídeos/canales de YouTube**: menú "YouTube" > "Buscar en YouTube".
- **Cargar playlist de YouTube**: menú "YouTube" > "Cargar Playlist de YouTube".
- **Añadir/eliminar favoritos**: clic derecho sobre un canal/vídeo.
- **Descargar vídeo**: clic derecho > "Descargar".
- **Controles multimedia**: barra inferior y atajos de teclado (espacio, f, m, flechas, etc).

## Atajos de teclado

![buscar-youtube](https://github.com/user-attachments/assets/5f6f3597-b09e-4574-bb67-afdf5d8b4fe4)

- `Espacio`: Play/Pause
- `f`: Pantalla completa
- `m`: Mute
- `Ctrl+S`: Añadir a favoritos
- `←/→`: Retroceder/Avanzar 2 segundos

## Notas técnicas

- El reproductor usa VLC embebido y fuerza la decodificación por software y salida de audio compatible (alsa/pulse).
- Para vídeos de YouTube, se selecciona automáticamente el mejor stream compatible (audio+vídeo juntos, sin DASH/HLS, preferentemente MP4/AVC1 ≤720p).
- El filtrado y carga de listas M3U es eficiente y soporta archivos grandes.
- El sistema de favoritos se guarda en `favoritos.json`.
- El soporte de cookies para YouTube es opcional, pero recomendable para vídeos restringidos.

## Problemas conocidos

- Algunos vídeos de YouTube pueden no estar disponibles si no hay streams compatibles (por restricciones de YouTube).
- En Linux, asegúrate de tener los paquetes de VLC y python-vlc correctamente instalados.
- Si el audio de YouTube no funciona, revisa la salida de audio del sistema y prueba con pulse/alsa.
- Al reproducir canales de IPTV, puede retrasarse un poco el inicio debido a la calidad de la señal del servidor al que se conecta

## Utilidad extra: Ordenar listas M3U

![ordenar-canales](https://github.com/user-attachments/assets/24d8924d-7b99-42c0-b96a-b0172aeb65c0)

Incluye el script `m3u_sorter.py` para ordenar listas M3U por nombre de canal, facilitando la organización de tus listas IPTV.

### ¿Para qué sirve?

- Si tienes una lista M3U desordenada (por ejemplo, canales mezclados por país, idioma o temática), puedes ordenarla alfabéticamente por el nombre del canal para encontrar más fácilmente lo que buscas en el reproductor.
- El script mantiene la estructura original de cada entrada (incluyendo metadatos como logo, grupo, etc.), solo cambia el orden de aparición y permite gestionar grupos, etc...

### Cómo usarlo paso a paso

1. Coloca tu archivo M3U original (por ejemplo, `mi_lista.m3u`) en la carpeta del proyecto.
2. Abre una terminal en esa carpeta.
3. Ejecuta el siguiente comando:
   ```bash
   python m3u_sorter.py mi_lista.m3u mi_lista_ordenada.m3u
   ```
   - `mi_lista.m3u`: es tu archivo original.
   - `mi_lista_ordenada.m3u`: será el nuevo archivo generado, con los canales ordenados alfabéticamente.
4. Abre el archivo ordenado (`mi_lista_ordenada.m3u`) en el reproductor para disfrutar de una navegación más cómoda.

### Ejemplo

Supón que tienes una lista así:
```
#EXTM3U
#EXTINF:-1 tvg-name="Canal Zeta",...
http://ejemplo.com/zeta
#EXTINF:-1 tvg-name="Canal Alfa",...
http://ejemplo.com/alfa
```

Tras ejecutar el script, obtendrás:
```
#EXTM3U
#EXTINF:-1 tvg-name="Canal Alfa",...
http://ejemplo.com/alfa
#EXTINF:-1 tvg-name="Canal Zeta",...
http://ejemplo.com/zeta
```

Así, la lista queda ordenada por nombre de canal. Además tendremos opciones para editar el grupo al que pertenecen un grupo de canales, etc ...

## Monitor de CPU (opcional)

Si tienes instalado el módulo `psutil`, puedes activar el monitor de uso de CPU en la interfaz del reproductor. Esto te permite ver en tiempo real el consumo de CPU del sistema mientras usas la aplicación.

### Cómo activarlo

1. Asegúrate de tener instalado `psutil`:
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

## Licencia

MIT License

---

Desarrollado con Python, café, tabaco y por entreunosyceros. ¡Disfruta tu IPTV y YouTube desde el escritorio!
