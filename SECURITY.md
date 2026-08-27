# Política de seguridad

## Versiones con soporte

| Versión | Soportada |
| ------- | --------- |
| 1.2.x   | ✅        |
| < 1.2   | ❌        |

## Alcance

**Kidneysm3u** es una aplicación de **escritorio** (Python + Tkinter) que abre listas M3U/IPTV con VLC embebido y YouTube con yt-dlp. En el ámbito de seguridad nos interesa especialmente:

- **Credenciales en listas y EPG**: URLs de paneles (`username`, `password`, tokens) en M3U, XMLTV o el gestor de descargas.
- **Sesión de YouTube**: `cookies.txt`, exportación desde el navegador (`browser-cookie3`) y fugas al registro o a issues.
- **Almacenamiento local**: `config.json`, `favoritos.json`, `enlaces.json`, historial y, con el `.deb`, `~/.local/share/kidneysm3u/` (incluye `.venv`).
- **Reproducción**: manejo de streams remotos en VLC, reconexión IPTV y caché local de YouTube (no descifrar DRM).
- **Dependencias**: vulnerabilidades en `yt-dlp`, `python-vlc`, `requests` u otras librerías de `requirements.txt`.

**Fuera de alcance habitual:**

- Disponibilidad o legalidad de listas IPTV y de los servidores de terceros.
- Fallos de YouTube, VLC o del panel Xtream ajenos a este programa.
- Contenido de las listas que el usuario carga voluntariamente.

## Cómo reportar una vulnerabilidad

1. **No** abras un issue público con detalles del fallo ni pegues URLs con usuario/contraseña, cookies o tokens.
2. Usa [GitHub Security Advisories](https://github.com/sapoclay/kidneysm3u/security/advisories/new) (**Report a vulnerability**) si tienes acceso.
3. Si no puedes usar Advisories, abre un issue con título `SECURITY (sin detalles)` y pide un canal privado; no incluyas pasos de explotación en público.

Incluye, en la medida de lo posible:

- Descripción del problema y componente afectado (`video_player.py`, `youtube_player.py`, `descargas.py`, EPG, etc.).
- Pasos para reproducirlo (sin credenciales reales).
- Impacto estimado (credenciales, datos locales, ejecución de código, red).
- Versión (`packaging/VERSION`, p. ej. 1.2.1) o commit afectado.
- Sistema operativo y si usas código fuente o el paquete `.deb`.
- Sugerencia de mitigación, si la tienes.

## Qué esperar

- **Acuse de recibo** en un plazo razonable (habitualmente en pocos días).
- Evaluación del informe y, si procede, parche o mitigación en una versión posterior.
- Crédito al informante en las notas de la corrección, salvo que prefiera anonimato.

## Buenas prácticas para usuarios

- No subas `cookies.txt`, `config.json` ni listas M3U con usuario y contraseña a issues, PRs o capturas.
- Mantén Python y las dependencias actualizadas; yt-dlp se actualiza en **Preferencias → Actualizar yt-dlp**.
- Clona y descarga el código solo desde el repositorio oficial: [github.com/entreunosyceros/kidneysm3u](https://github.com/entreunosyceros/kidneysm3u). Las actualizaciones in-app bajan el `.exe` o `.deb` de esa misma página de Releases ([cómo actualizar](docs/instalacion.md#actualizar-el-programa)).
- En equipos compartidos, protege `~/.local/share/kidneysm3u/` (instalación `.deb`) o la carpeta del proyecto (código fuente). Desinstalar el `.deb` **no** borra esa carpeta; ver [docs/instalacion.md](docs/instalacion.md#desinstalar).
