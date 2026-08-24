# Instalación

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)

## Requisitos

- Python 3.8 o superior
- [VLC Media Player](https://www.videolan.org/vlc/) (el reproductor embebido usa `python-vlc`)
- [tkinter](https://docs.python.org/3/library/tkinter.html) (suele venir con Python; en Ubuntu: `python3-tk`)
- Las librerías de `requirements.txt` (las instala `run_app.py`)
- [ffmpeg](https://ffmpeg.org/download.html) — opcional, para extraer solo el audio de YouTube
- Node o Deno — recomendable; [yt-dlp](https://github.com/yt-dlp/yt-dlp) lo usa si YouTube pide un runtime JavaScript
- [psutil](https://pypi.org/project/psutil/) — opcional, solo si activas el [monitor de CPU](notas.md#monitor-de-cpu)

En Linux instala VLC (y el binding del sistema si lo necesitas):

```bash
sudo apt install vlc python3-vlc
```

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

Si **borras `.venv`**, el siguiente `python3 run_app.py` lo vuelve a crear e instala otra vez las librerías de Python. No reinstala VLC, ffmpeg, tkinter ni Node: eso es del sistema.

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
sudo dpkg -i kidneysm3u_1.0.0_all.deb
sudo apt-get install -f   # si hace falta
```

3. Ejecuta `kidneysm3u` o busca el lanzador.

> [!NOTE]
> El primer arranque tarda más porque crea el entorno virtual e instala dependencias. Los siguientes son más rápidos.

Siguiente: [uso básico](uso.md).

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

## Siguiente

- [Uso](uso.md) — cargar una lista y reproducir
- [Notas](notas.md) — problemas conocidos

[Inicio](../README.md) · [Índice](README.md) · [Instalación](instalacion.md) · [Uso](uso.md) · [Listas M3U](listas-m3u.md) · [YouTube](youtube.md) · [Reproductor](reproductor.md) · [Notas](notas.md)
