# Riñones M3U - Filtrado y reproducción M3U/Youtube

![about-kidneys](https://github.com/user-attachments/assets/2f7e3bf4-5180-4e19-9358-297ab4ea9bf0)

Aplicación de escritorio en Python/Tkinter para filtrar, reproducir y gestionar listas M3U/M3U8, vídeos de YouTube y canales, con soporte avanzado para archivos grandes, compatibilidad multiplataforma y manejo de errores.

> [!WARNING]  
> Este programa no incluye enlaces a ningún canal. Aun que si incluye enlaces a listas gratuitas y legales que se pueden
> encontrar en internet.

## Características principales

- **Carga y filtrado eficiente de listas M3U/M3U8 locales o por URL** (con soporte para archivos grandes y barra de búsqueda). Se pueden añadir nuevas búsquedas y sustituir o añadir el filtrado a un archivo. Si se añade la nueva búsqueda, esta se añadirá al final del archivo existente. 
- **Reproducción fluida de canales IPTV y vídeos directos** usando VLC embebido.
- **Reproducción de vídeos de YouTube** (URL directa, búsqueda, playlists, canales) con selección automática del mejor stream compatible (audio+vídeo juntos, sin DASH/HLS).
- **Búsqueda avanzada en YouTube**: permite buscar vídeos, listas de reproducción o canales, y reproducirlos o cargarlos en la lista.

![gestion-enlaces](https://github.com/user-attachments/assets/404a2382-e528-46fb-b8bc-e3a632daa0ed)

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
- `Esc`: Salir de pantalla completa
- `m`: Mute
- `Ctrl+S`: Añadir a favoritos
- `←/→`: Retroceder/Avanzar 2 segundos

## Notas técnicas

- El reproductor usa VLC embebido y fuerza la decodificación por software y salida de audio compatible (alsa/pulse).
- Para vídeos de YouTube, se selecciona automáticamente el mejor stream compatible (audio+vídeo juntos, sin DASH/HLS, preferentemente MP4/AVC1 ≤720p).
- El filtrado y carga de listas M3U es eficiente y soporta archivos grandes. Lo he probado con una lista de más de dos millones de líneas con buenos resultados.
- El sistema de favoritos se guarda en `favoritos.json` dentro de la carpeta del programa.
- Los enlaces que se añadan al programa, también se guardaran en el archivo `enlaces.json` dentro de la carpeta del programa.
- El soporte de cookies para YouTube es opcional, pero recomendable para vídeos restringidos.

## Problemas conocidos

> [!IMPORTANT]  
> Quiero aclarar que esto lo he desarrollado en su totalidad desde Linux, por lo que he podido probarlo poco en Windows. Así que es posible que puedan aparecer errores que desconozca.

- Algunos vídeos de YouTube pueden no estar disponibles si no hay streams compatibles (por restricciones de YouTube).
- En Linux, asegúrate de tener los paquetes de VLC y python-vlc correctamente instalados.
- Si el audio de YouTube no funciona, revisa la salida de audio del sistema y prueba con pulse/alsa.
- Al reproducir canales de IPTV, puede retrasarse un poco el inicio debido a la calidad de la señal del servidor al que se conecta
- La búsqueda de listas de reproducción en Youtube, no funcionan como deben. Si quieres reproducir listas de reproducción, por el momento debes acceder a Youtube, buscar la lista de reproducción, copiar la URL de la lista y pegarla en el campo destinado a cargar las listas de reproducción en el reproductor.

## Utilidad extra: Ordenar listas M3U desde la interfaz gráfica

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

[MIT License](./LICENSE)

---

Desarrollado con Python, ☕ y cada vez menos 🚬 por entreunosyceros. ¡Disfruta de tu IPTV y YouTube (sin molestias!!) desde el escritorio!
