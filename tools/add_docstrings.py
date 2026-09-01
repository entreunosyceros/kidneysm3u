#!/usr/bin/env python3
"""Añade docstrings en español a funciones y clases que no las tengan."""

from __future__ import annotations

import ast
import io
import os
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {'.venv', 'build', 'dist', '__pycache__', '.git', 'debian-package', 'epg_cache'}
SKIP_FILES: set[str] = set()

# Prefijos habituales -> plantilla (sin el nombre base)
_PREFIXES = (
    ('__init__', 'Inicializa {target}.'),
    ('__str__', 'Representación legible de {target}.'),
    ('__repr__', 'Representación técnica de {target}.'),
    ('__enter__', 'Entra en el contexto de {target}.'),
    ('__exit__', 'Sale del contexto de {target}.'),
    ('__call__', 'Ejecuta {target} como callable.'),
    ('get_', 'Obtiene {name}.'),
    ('set_', 'Establece {name}.'),
    ('is_', 'Indica si {name}.'),
    ('has_', 'Indica si existe {name}.'),
    ('show_', 'Muestra {name}.'),
    ('open_', 'Abre {name}.'),
    ('close_', 'Cierra {name}.'),
    ('load_', 'Carga {name}.'),
    ('save_', 'Guarda {name}.'),
    ('create_', 'Crea {name}.'),
    ('build_', 'Construye {name}.'),
    ('make_', 'Genera {name}.'),
    ('setup_', 'Configura {name}.'),
    ('bind_', 'Enlaza {name} a eventos de la interfaz.'),
    ('update_', 'Actualiza {name}.'),
    ('refresh_', 'Refresca {name}.'),
    ('sync_', 'Sincroniza {name}.'),
    ('parse_', 'Interpreta {name}.'),
    ('normalize_', 'Normaliza {name}.'),
    ('format_', 'Formatea {name}.'),
    ('validate_', 'Valida {name}.'),
    ('ensure_', 'Garantiza {name}.'),
    ('handle_', 'Gestiona {name}.'),
    ('on_', 'Responde al evento {name}.'),
    ('_on_', 'Callback interno para {name}.'),
    ('toggle_', 'Alterna {name}.'),
    ('apply_', 'Aplica {name}.'),
    ('run_', 'Ejecuta {name}.'),
    ('start_', 'Inicia {name}.'),
    ('stop_', 'Detiene {name}.'),
    ('cancel_', 'Cancela {name}.'),
    ('schedule_', 'Programa {name}.'),
    ('fetch_', 'Obtiene {name} desde la red o el disco.'),
    ('download_', 'Descarga {name}.'),
    ('upload_', 'Sube {name}.'),
    ('play_', 'Reproduce {name}.'),
    ('search_', 'Busca {name}.'),
    ('filter_', 'Filtra {name}.'),
    ('sort_', 'Ordena {name}.'),
    ('draw_', 'Dibuja {name}.'),
    ('render_', 'Renderiza {name}.'),
    ('extract_', 'Extrae {name}.'),
    ('convert_', 'Convierte {name}.'),
    ('merge_', 'Combina {name}.'),
    ('split_', 'Divide {name}.'),
    ('copy_', 'Copia {name}.'),
    ('move_', 'Mueve {name}.'),
    ('delete_', 'Elimina {name}.'),
    ('remove_', 'Quita {name}.'),
    ('add_', 'Añade {name}.'),
    ('insert_', 'Inserta {name}.'),
    ('append_', 'Añade {name} al final.'),
    ('clear_', 'Limpia {name}.'),
    ('reset_', 'Restablece {name}.'),
    ('init_', 'Inicializa {name}.'),
    ('destroy_', 'Destruye {name}.'),
    ('find_', 'Localiza {name}.'),
    ('pick_', 'Elige {name}.'),
    ('choose_', 'Elige {name}.'),
    ('compute_', 'Calcula {name}.'),
    ('calc_', 'Calcula {name}.'),
    ('count_', 'Cuenta {name}.'),
    ('list_', 'Lista {name}.'),
    ('read_', 'Lee {name}.'),
    ('write_', 'Escribe {name}.'),
    ('test_', 'Comprueba {name}.'),
)

_WORDS = {
    'cfg': 'configuración',
    'config': 'configuración',
    'url': 'URL',
    'urls': 'URLs',
    'ui': 'interfaz',
    'epg': 'guía EPG',
    'm3u': 'lista M3U',
    'iptv': 'IPTV',
    'yt': 'YouTube',
    'vlc': 'VLC',
    'subs': 'subtítulos',
    'sub': 'subtítulo',
    'btn': 'botón',
    'widget': 'widget',
    'window': 'ventana',
    'frame': 'marco',
    'tree': 'árbol',
    'listbox': 'lista',
    'sidebar': 'barra lateral',
    'overlay': 'superposición',
    'pip': 'PiP',
    'thumb': 'miniatura',
    'logo': 'logo',
    'channel': 'canal',
    'channels': 'canales',
    'playlist': 'lista de reproducción',
    'queue': 'cola',
    'history': 'historial',
    'record': 'grabación',
    'buffer': 'buffer',
    'stream': 'stream',
    'cookie': 'cookie',
    'cookies': 'cookies',
    'fav': 'favorito',
    'favorite': 'favorito',
    'favorites': 'favoritos',
    'deb': 'paquete .deb',
    'exe': 'ejecutable',
}


def _humanize(name: str) -> str:
    """Uso interno: humanize."""
    text = name.strip('_')
    if not text:
        return 'este elemento'
    parts = re.split(r'_+', text.lower())
    out = []
    for part in parts:
        out.append(_WORDS.get(part, part.replace('-', ' ')))
    phrase = ' '.join(out)
    if phrase.endswith('s') and len(parts) > 1:
        return phrase
    return phrase


def _describe_callable(name: str, *, is_method: bool, class_name: str | None) -> str:
    """Uso interno: describe callable."""
    if name.startswith('test_'):
        return f'Prueba {_humanize(name[5:])}.'

    target = class_name or 'la instancia'
    for prefix, template in _PREFIXES:
        if name == prefix or name.startswith(prefix):
            base = name[len(prefix):] if name != prefix else ''
            if '{target}' in template and '{name}' not in template:
                return template.format(target=target if is_method else _humanize(name))
            label = _humanize(base) if base else _humanize(name)
            return template.format(name=label, target=target)

    if name.startswith('_'):
        return f'Uso interno: {_humanize(name[1:])}.'
    verb = _humanize(name)
    return f'{verb.capitalize()}.'


def _describe_class(name: str) -> str:
    """Uso interno: describe class."""
    return f'Clase que representa {_humanize(name)}.'


def _indent_of(line: str) -> str:
    """Uso interno: indent of."""
    return line[: len(line) - len(line.lstrip(' \t'))]


def _docstring_line(text: str, indent: str) -> str:
    """Uso interno: docstring line."""
    escaped = text.replace('\\', '\\\\').replace('"', '\\"')
    return f'{indent}"""{escaped}"""'


def _header_end_line(lines: list[str], start_line: int) -> int:
    """Índice 0-based de la línea que cierra la cabecera def/class."""
    depth = 0
    started = False
    for idx in range(start_line, len(lines)):
        chunk = lines[idx]
        for ch in chunk:
            if ch == '(':
                depth += 1
                started = True
            elif ch == ')':
                depth -= 1
        stripped = chunk.strip()
        if not started and stripped.endswith(':'):
            return idx
        if started and depth <= 0 and (stripped.endswith(':') or stripped.endswith('):')):
            return idx
    return start_line


class DocstringInserter(ast.NodeVisitor):
    """Clase que representa docstringinserter."""
    def __init__(self, source: str):
        """Inicializa DocstringInserter."""
        self.source = source
        self.lines = source.splitlines(keepends=True)
        self.class_stack: list[str] = []
        self.insert_after: dict[int, list[str]] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit classdef."""
        if not ast.get_docstring(node, clean=False):
            indent = _indent_of(self.lines[node.lineno - 1]) + '    '
            doc = _describe_class(node.name)
            end_line = _header_end_line(self.lines, node.lineno - 1)
            self.insert_after.setdefault(end_line, []).append(
                _docstring_line(doc, indent) + '\n'
            )
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit functiondef."""
        self._maybe_add(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit asyncfunctiondef."""
        self._maybe_add(node)
        self.generic_visit(node)

    def _maybe_add(self, node: ast.AST) -> None:
        """Uso interno: maybe add."""
        if ast.get_docstring(node, clean=False):
            return
        name = getattr(node, 'name', '')
        is_method = bool(self.class_stack)
        class_name = self.class_stack[-1] if self.class_stack else None
        doc = _describe_callable(name, is_method=is_method, class_name=class_name)
        indent = _indent_of(self.lines[node.lineno - 1]) + '    '
        end_line = _header_end_line(self.lines, node.lineno - 1)
        self.insert_after.setdefault(end_line, []).append(
            _docstring_line(doc, indent) + '\n'
        )


def _add_module_docstring(source: str, path: Path) -> str:
    """Uso interno: add module docstring."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    if ast.get_docstring(tree, clean=False):
        return source
    mod_name = path.stem.replace('_', ' ')
    doc = f'"""Módulo de {mod_name}."""\n\n'
    return doc + source


def process_file(path: Path, *, dry_run: bool = False) -> int:
    """Process file."""
    original = path.read_text(encoding='utf-8')
    updated = _add_module_docstring(original, path)
    try:
        tree = ast.parse(updated)
    except SyntaxError:
        print(f'  omitido (sintaxis): {path}')
        return 0
    inserter = DocstringInserter(updated)
    inserter.visit(tree)
    if not inserter.insert_after:
        if updated != original and not dry_run:
            path.write_text(updated, encoding='utf-8')
        return 0

    lines = updated.splitlines(keepends=True)
    for line_idx in sorted(inserter.insert_after.keys(), reverse=True):
        extra = inserter.insert_after[line_idx]
        lines[line_idx + 1:line_idx + 1] = extra
    new_source = ''.join(lines)
    if new_source == original:
        return 0
    if not dry_run:
        path.write_text(new_source, encoding='utf-8')
    added = sum(len(v) for v in inserter.insert_after.values())
    return added


def iter_source_files() -> list[Path]:
    """Iter source files."""
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith('.py') or fn in SKIP_FILES:
                continue
            files.append(Path(dirpath) / fn)
    return sorted(files)


def main() -> None:
    """Main."""
    import argparse

    parser = argparse.ArgumentParser(description='Añade docstrings en español.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    total = 0
    touched = 0
    for path in iter_source_files():
        rel = path.relative_to(ROOT)
        count = process_file(path, dry_run=args.dry_run)
        if count:
            touched += 1
            total += count
            print(f'  +{count:3d}  {rel}')
    print(f'\nArchivos modificados: {touched}, docstrings añadidos: {total}')


if __name__ == '__main__':
    main()
