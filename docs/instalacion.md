# Instalación

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

## Requisitos

- Python 3.8 o superior
- [VLC Media Player](https://www.videolan.org/vlc/) (el reproductor embebido usa `python-vlc`)
- [tkinter](https://docs.python.org/3/library/tkinter.html) (suele venir con Python; en Ubuntu: `python3-tk`)
- Las librerías de `requirements.txt` (las instala `run_app.py`)
- [ffmpeg](https://ffmpeg.org/download.html) — opcional, para grabar el stream en reproducción y para extraer solo el audio de YouTube
- [WebKitGTK](https://webkitgtk.org/) — en Linux, chat de Twitch integrado: `python3-gi`, `gir1.2-gtk-3.0` y `gir1.2-webkit2-4.1` (ver abajo)
- Node o Deno — recomendable; [yt-dlp](https://github.com/yt-dlp/yt-dlp) lo usa si YouTube pide un runtime JavaScript
- [psutil](https://pypi.org/project/psutil/) — opcional, solo si activas el [monitor de CPU](notas.md#monitor-de-cpu)

En Linux instala VLC (y el binding del sistema si lo necesitas):

```bash
sudo apt install vlc python3-vlc
```

Para el **chat de Twitch** en ventana integrada instala los bindings de Python y WebKitGTK:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

`python3-gi` es imprescindible: `gir1.2-webkit2-4.1` solo aporta datos de introspección; sin `gi` en tu Python, pywebview no puede abrir la ventana. La librería `pywebview` se instala en el `.venv` con `run_app.py`. Si el entorno virtual se creó con otro Python (Conda, 3.13…), borra `.venv` y arranca con `/usr/bin/python3 run_app.py`.

## Cómo se instalan las dependencias de Python

Desde la carpeta del proyecto:

```bash
python3 run_app.py
```

`run_app.py` hace lo siguiente:

1. Si no existe `.venv`, lo crea.
2. Actualiza `setuptools`.
3. Instala todo lo de `requirements.txt`.
4. Arranca `main.py` con el Python de ese entorno.

Si **borras `.venv`**, el siguiente `python3 run_app.py` lo vuelve a crear e instala otra vez las librerías de Python. No reinstala VLC, ffmpeg, tkinter ni Node: eso es del sistema. `pip install -r` no actualiza solo yt-dlp si ya está instalado; para eso usa **Preferencias → Actualizar yt-dlp**.

No uses `python3 main.py` a pelo si acabas de borrar el entorno: ese comando no recrea `.venv`.

También puedes instalar a mano:

```bash
python3 -m pip install -r requirements.txt
```

Para correr las pruebas del parseo M3U y de la EPG (opcional, no hace falta para usar el programa):

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

## Instalación en Ubuntu (paquete .deb)

1. Descarga el `.deb` desde la página de lanzamientos.
2. En una terminal:

```bash
sudo dpkg -i kidneysm3u_1.2.5_all.deb
sudo apt-get install -f   # si hace falta
```

3. Ejecuta `kidneysm3u` o busca el lanzador **Kidneys M3U**.

El paquete instala el código en `/usr/share/kidneysm3u`. Al arrancar se copia a `~/.local/share/kidneysm3u` (ahí van `config.json`, cookies, favoritos, `epg_cache/` y `.venv`). Así no se escribe en directorios de sistema.

El icono del lanzador y la ventana del programa comparten el mismo identificador (`Kidneysm3u`). En GNOME/Ubuntu el programa se queda en el icono desde el que lo abriste, no aparece otro genérico de Python.

> [!NOTE]
> El primer arranque tarda más porque crea el entorno virtual e instala dependencias. Los siguientes son más rápidos. Si actualizas el `.deb` y ya tenías una copia en `~/.local/share/kidneysm3u`, el siguiente arranque sustituye el código de esa carpeta.

### Desinstalar

```bash
sudo apt remove kidneysm3u
```

Eso quita el programa de `/usr` (binario, lanzador y copia en `/usr/share/kidneysm3u`). **No borra** `~/.local/share/kidneysm3u`: ahí están tus datos (`config.json`, cookies, favoritos, `epg_cache/`, `.venv`). `apt purge` tampoco la elimina: el paquete no escribe en el home y el script de desinstalación no debe borrar carpetas de usuario (corre como root; con `sudo`, `$HOME` suele ser el de root, no el tuyo).

Si quieres borrar también esa copia local:

```bash
rm -rf ~/.local/share/kidneysm3u
```

Sin esa carpeta, un reinstalado arranca como la primera vez (vuelve a copiar el código y a crear `.venv`).

## Instalación en Windows

1. Instala [VLC](https://www.videolan.org/vlc/). Marca «Add to PATH» o añade `C:\Program Files\VideoLAN\VLC` al PATH.
2. Instala [Python 3.8+](https://www.python.org/downloads/) con «Add Python to PATH».
3. En la carpeta del proyecto:

```bash
python run_app.py
```

Eso crea el entorno, instala dependencias y abre el programa. Alternativa:

```bash
python -m pip install -r requirements.txt
python main.py
```

Si el audio o el vídeo fallan, comprueba que VLC está en el PATH y que `python-vlc` encaja con tu versión de VLC.

Para YouTube en Windows hace falta **Firefox**: Chrome, Brave y Edge cifran las cookies y el programa no puede leerlas. En **Preferencias** elige **Automático** o **Firefox**, inicia sesión en youtube.com con Firefox, ciérralo y pulsa **Reexportar cookies**. Detalle en [YouTube](youtube.md#cookies).

### Instalador de Windows

El usuario instala **Kidneysm3u-Setup-1.2.5.exe** (asistente de Inno Setup): Program Files, menú Inicio y desinstalador. Hace falta [VLC](https://www.videolan.org/vlc/) en el PATH.

Para generar el instalador desde Linux (Docker) o desde Windows:

```bash
bash build-windows.sh
```

El archivo queda en `dist/Kidneysm3u-Setup-1.2.5.exe`. Las preferencias y cookies van a `%LOCALAPPDATA%\kidneysm3u`. Al desinstalar, el asistente pregunta si quieres borrar también esa carpeta. Editor/compañía: **entreunosyceros**.

## Actualizar el programa

La versión instalada se compara con [GitHub Releases](https://github.com/entreunosyceros/kidneysm3u/releases) (`entreunosyceros/kidneysm3u`). No sustituye a **Actualizar yt-dlp** (eso es solo el extractor de YouTube).

### Aviso al abrir

Si hay una versión más nueva y los avisos no están desactivados, unos segundos después de abrir la ventana principal aparece un diálogo. La consulta va en segundo plano (la ventana no se congela) y, como mucho, **una vez al día**. Si no hay red, no se muestra nada.

En el aviso:

| Botón | Qué hace |
| --- | --- |
| **Actualizar** | Windows: descarga `Kidneysm3u-Setup-*.exe`, lanza el instalador y cierra el programa. Ubuntu (`.deb`): descarga `kidneysm3u_*_all.deb` y lo instala con `pkexec` (pide administrador). Luego hay que cerrar y abrir otra vez `kidneysm3u`. |
| **Más tarde** | Cierra el aviso. La próxima vez que abras el programa volverá a preguntar. |
| **No avisarme** | Deja de consultar al arrancar. Se puede volver a activar en Preferencias. |

El paquete nuevo **se instala encima** del antiguo (mismo nombre de paquete / mismo `AppId` de Inno Setup). No hace falta desinstalar. Preferencias, cookies y favoritos se quedan (`~/.local/share/kidneysm3u` o `%LOCALAPPDATA%\kidneysm3u`).

Si usas el **código fuente** (`python3 run_app.py` en el clon), el botón abre la página de lanzamientos: no se instala un `.exe`/`.deb` encima del árbol git. Actualiza con `git pull` o bajando el zip.

### Buscar a mano

**Ayuda → Buscar actualizaciones** (ventana principal). Consulta GitHub **en ese momento**, aunque el aviso automático falle, esté desactivado o ya se hubiera mirado hoy. La barra de estado muestra «Buscando actualizaciones…» y el resultado (versión nueva, ya estás al día, o error de red). Si hay paquete, sale el mismo diálogo.

### Desactivar o reactivar avisos

**Archivo → Preferencias** (apartado **Actualizaciones**): casilla «Avisar si hay una versión nueva al abrir el programa». Por defecto está activada. **Ayuda → Buscar actualizaciones** sigue disponible con la casilla desmarcada.

### Publicar un release (para que el aviso encuentre el paquete)

El programa mira el último release de GitHub (`releases/latest`) y saca el número del **tag** o del título. Sirven tags como `Versión1.2.4`, `Versión 1.2.4`, `v1.2.4` o `1.2.4`: se compara `1.2.4` con `app_version.py`.

En cada versión hay que adjuntar en GitHub, con estos nombres (el número del archivo, no el del tag):

- `Kidneysm3u-Setup-1.2.5.exe`
- `kidneysm3u_1.2.5_all.deb`

(cambia el número según `packaging/VERSION` / `app_version.py`). Sin esos archivos, el programa puede avisar de que hay versión nueva pero no podrá descargar el instalador.

## Siguiente

- [Uso](uso.md) — cargar una lista y reproducir
- [Notas](notas.md) — problemas conocidos

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
