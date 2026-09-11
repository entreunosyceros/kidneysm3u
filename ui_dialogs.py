"""Diálogos Tk que respetan el apilado del reproductor sobre la ventana principal."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox as _messagebox


def _widget_alive(widget):
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def _root_of(widget):
    try:
        return widget.nametowidget('.')
    except tk.TclError:
        try:
            return widget.winfo_toplevel()
        except tk.TclError:
            return None


def keep_parent_above_root(parent, *, user_topmost=False):
    """
    Context manager: deja parent por encima de la raíz Tk mientras dura el diálogo.

    En Linux, un messagebox suele elevar la ventana principal (`.`) y deja el
    reproductor (Toplevel) detrás. Forzamos topmost temporal y reordenamos al cerrar.
    """

    class _Guard:
        def __init__(self):
            self._forced = False
            self._parent = parent

        def __enter__(self):
            if not _widget_alive(self._parent):
                return self
            try:
                self._parent.deiconify()
                self._parent.lift()
                self._parent.focus_force()
                if not user_topmost:
                    self._parent.attributes('-topmost', True)
                    self._forced = True
                self._parent.update_idletasks()
            except tk.TclError:
                self._forced = False
            return self

        def __exit__(self, exc_type, exc, tb):
            if not _widget_alive(self._parent):
                return False
            try:
                if self._forced and not user_topmost:
                    self._parent.attributes('-topmost', False)
            except tk.TclError:
                pass
            try:
                root = _root_of(self._parent)
                if root is not None and root is not self._parent:
                    try:
                        root.lower()
                    except tk.TclError:
                        pass
                master = getattr(self._parent, 'master', None)
                if (
                    master is not None
                    and master is not root
                    and master is not self._parent
                    and _widget_alive(master)
                ):
                    try:
                        master.lift()
                    except tk.TclError:
                        pass
                self._parent.lift()
                self._parent.focus_force()
            except tk.TclError:
                pass
            return False

    return _Guard()


def run_dialog(fn, *args, parent=None, user_topmost=False, **kwargs):
    """Ejecuta messagebox.* con parent y restaurando el z-order."""
    if parent is not None and _widget_alive(parent):
        kwargs.setdefault('parent', parent)
        with keep_parent_above_root(parent, user_topmost=user_topmost):
            return fn(*args, **kwargs)
    return fn(*args, **kwargs)


class BoundMessageBox:
    """messagebox ligado a una ventana (p. ej. el reproductor)."""

    def __init__(self, get_parent, is_user_topmost=None):
        """get_parent: callable → widget; is_user_topmost: callable → bool."""
        self._get_parent = get_parent
        self._is_user_topmost = is_user_topmost or (lambda: False)

    def _parent(self):
        try:
            return self._get_parent()
        except Exception:
            return None

    def _user_topmost(self):
        try:
            return bool(self._is_user_topmost())
        except Exception:
            return False

    def showinfo(self, *args, **kwargs):
        return run_dialog(
            _messagebox.showinfo, *args, parent=self._parent(),
            user_topmost=self._user_topmost(), **kwargs,
        )

    def showerror(self, *args, **kwargs):
        return run_dialog(
            _messagebox.showerror, *args, parent=self._parent(),
            user_topmost=self._user_topmost(), **kwargs,
        )

    def showwarning(self, *args, **kwargs):
        return run_dialog(
            _messagebox.showwarning, *args, parent=self._parent(),
            user_topmost=self._user_topmost(), **kwargs,
        )

    def askyesno(self, *args, **kwargs):
        return run_dialog(
            _messagebox.askyesno, *args, parent=self._parent(),
            user_topmost=self._user_topmost(), **kwargs,
        )

    def askyesnocancel(self, *args, **kwargs):
        return run_dialog(
            _messagebox.askyesnocancel, *args, parent=self._parent(),
            user_topmost=self._user_topmost(), **kwargs,
        )

    def askokcancel(self, *args, **kwargs):
        return run_dialog(
            _messagebox.askokcancel, *args, parent=self._parent(),
            user_topmost=self._user_topmost(), **kwargs,
        )


def dialogs_for(host):
    """Devuelve BoundMessageBox del reproductor o uno ligado a host.window."""
    dlg = getattr(host, '_dlg', None)
    if dlg is not None:
        return dlg
    window = getattr(host, 'window', None)
    if window is not None:
        return BoundMessageBox(lambda: getattr(host, 'window', None))
    player = getattr(host, 'video_player', None)
    if player is not None:
        return dialogs_for(player)
    return _messagebox
