"""Diálogos de sesión caducada con opción de reexportar cookies."""

from tkinter import messagebox

from ui_dialogs import run_dialog


def offer_reexport_cookies(parent, title, help_text, reexport_cb):
    """Muestra aviso de sesión y, si el usuario acepta, reexporta cookies."""
    body = (
        f'{help_text}\n\n'
        '¿Quieres reexportar cookies ahora desde el navegador configurado? '
        'Es necesario para que la sesión sea válida.'
    )
    try:
        ok = run_dialog(messagebox.askyesno, title, body, parent=parent)
    except Exception:
        ok = messagebox.askyesno(title, body)
    if not ok:
        return False
    if callable(reexport_cb):
        try:
            reexport_cb()
        except Exception as exc:
            try:
                run_dialog(messagebox.showerror, title, str(exc), parent=parent)
            except Exception:
                messagebox.showerror(title, str(exc))
            return False
    return True
