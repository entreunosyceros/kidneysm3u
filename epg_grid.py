"""Parrilla EPG: ahora + unas horas, del grupo visible."""

import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import logo_cache
from ui_theme import (
    center_window, get_colors, get_font, set_window_icon, style_window,
)

HOURS = 6
PX_HOUR = 118
ROW_H = 36
NAME_W = 176
HEAD_H = 28


def _floor_half_hour(ts):
    dt = datetime.fromtimestamp(ts)
    minute = 0 if dt.minute < 30 else 30
    return dt.replace(minute=minute, second=0, microsecond=0).timestamp()


class EpgGridWindow:
    def __init__(self, player):
        self.player = player
        existing = getattr(player, '_epg_grid', None)
        if existing is not None:
            try:
                if existing.window.winfo_exists():
                    existing.window.deiconify()
                    existing.window.lift()
                    existing.refresh()
                    self.window = existing.window
                    return
            except tk.TclError:
                pass
        player._epg_grid = self
        colors = get_colors()
        window = tk.Toplevel(player.window)
        window.title('Guía EPG')
        window.geometry('980x560')
        window.minsize(720, 400)
        style_window(window)
        set_window_icon(window)
        center_window(window, 980, 560)
        window.transient(player.window)
        self.window = window
        self._photos = {}
        self._start = _floor_half_hour(time.time())
        self._tick_job = None

        top = ttk.Frame(window, padding=(12, 10, 12, 6))
        top.pack(fill=tk.X)
        self._title = ttk.Label(top, text='Guía', style='PageTitle.TLabel')
        self._title.pack(side=tk.LEFT)
        ttk.Button(top, text='Recargar', command=self._reload).pack(side=tk.RIGHT)
        ttk.Button(top, text='Cerrar', command=self.close).pack(side=tk.RIGHT, padx=(0, 8))
        self._hint = ttk.Label(top, text='', style='Muted.TLabel')
        self._hint.pack(side=tk.RIGHT, padx=(0, 16))

        body = ttk.Frame(window)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.canvas = tk.Canvas(
            body,
            bg=colors['list_bg'],
            highlightthickness=0,
            bd=0,
        )
        yscroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<MouseWheel>', self._on_wheel)
        self.canvas.bind('<Button-4>', self._on_wheel)
        self.canvas.bind('<Button-5>', self._on_wheel)
        window.protocol('WM_DELETE_WINDOW', self.close)
        self.draw()
        self._schedule_tick()

    def close(self):
        job = self._tick_job
        self._tick_job = None
        if job and self.player._widget_exists(self.window):
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        if getattr(self.player, '_epg_grid', None) is self:
            self.player._epg_grid = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _reload(self):
        start = getattr(self.player, '_start_epg', None)
        if start:
            start(notify=False)
        self._hint.configure(text='Actualizando…')

    def _schedule_tick(self):
        if not self.player._widget_exists(self.window):
            return
        self._tick_job = self.window.after(30000, self._tick)

    def _tick(self):
        if not self.player._widget_exists(self.window):
            return
        self.draw()
        self._schedule_tick()

    def refresh(self):
        if not self.player._widget_exists(self.window):
            return
        self.draw()

    def _on_wheel(self, event):
        delta = -1
        if getattr(event, 'num', None) == 5 or getattr(event, 'delta', 0) < 0:
            delta = 1
        self.canvas.yview_scroll(delta, 'units')
        return 'break'

    def _rows(self):
        getter = getattr(self.player, '_epg_grid_rows', None)
        if not getter:
            return []
        return getter()

    def _on_click(self, event):
        y = self.canvas.canvasy(event.y)
        if y < HEAD_H:
            return
        row = int((y - HEAD_H) // ROW_H)
        rows = self._rows()
        if 0 <= row < len(rows):
            index = rows[row][0]
            play = getattr(self.player, 'play_channel', None)
            if play:
                play(index)

    def draw(self):
        if not self.player._widget_exists(self.window):
            return
        colors = get_colors()
        canvas = self.canvas
        canvas.delete('all')
        now = time.time()
        start = self._start
        if now > start + 20 * 60:
            self._start = _floor_half_hour(now)
            start = self._start
        span = HOURS * 3600
        stop = start + span
        width = max(int(canvas.winfo_width() or 900), NAME_W + PX_HOUR * HOURS)
        rows = self._rows()
        height = HEAD_H + max(1, len(rows)) * ROW_H + 8
        canvas.configure(scrollregion=(0, 0, width, height))
        guide = getattr(self.player, '_epg', None)
        group = ''
        sidebar = getattr(self.player, 'sidebar', None)
        if sidebar:
            group = getattr(sidebar, '_active_group', '') or ''
        if group:
            self._title.configure(text=f'Guía · {group}')
        else:
            self._title.configure(text='Guía EPG')
        if not getattr(self.player, '_epg_urls', None):
            self._hint.configure(text='Sin URL de guía')
        elif not guide:
            self._hint.configure(text='Cargando…')
        else:
            self._hint.configure(text=datetime.fromtimestamp(start).strftime('%a %d %b · %H:%M'))

        canvas.create_rectangle(0, 0, width, HEAD_H, fill=colors['surface_alt'], outline='')
        canvas.create_text(
            12, HEAD_H / 2,
            text='Canal',
            fill=colors['text_muted'],
            font=get_font(9, 'bold'),
            anchor='w',
        )
        for hour in range(HOURS * 2 + 1):
            ts = start + hour * 1800
            x = NAME_W + (ts - start) / 3600 * PX_HOUR
            canvas.create_line(x, 0, x, height, fill=colors['border'])
            if hour % 2 == 0:
                canvas.create_text(
                    x + 6, HEAD_H / 2,
                    text=datetime.fromtimestamp(ts).strftime('%H:%M'),
                    fill=colors['text_muted'],
                    font=get_font(9),
                    anchor='w',
                )

        if not rows:
            hint = 'Carga una lista M3U para ver la parrilla.'
            if getattr(self.player, 'channels', None):
                hint = 'Entra en un grupo de la lista para ver la parrilla.'
            canvas.create_text(
                NAME_W + 24, HEAD_H + 40,
                text=hint,
                fill=colors['text_muted'],
                font=get_font(11),
                anchor='w',
            )
            return

        photos = getattr(self.player, '_logo_photos', None)
        if photos is None:
            photos = {}
            self.player._logo_photos = photos

        for row, (index, name, tvg_id, logo_url) in enumerate(rows):
            y = HEAD_H + row * ROW_H
            bg = colors['list_bg'] if row % 2 == 0 else colors['surface_alt']
            canvas.create_rectangle(0, y, width, y + ROW_H, fill=bg, outline='')
            canvas.create_line(0, y + ROW_H, width, y + ROW_H, fill=colors['border'])
            photo = None
            if logo_url and getattr(self.player, 'channel_logos_enabled', lambda: True)():
                photo = logo_cache.load_photo(logo_url, photos)
            text_x = 12
            if photo:
                canvas.create_image(12, y + ROW_H / 2, image=photo, anchor='w')
                text_x = 36
            canvas.create_text(
                text_x, y + ROW_H / 2,
                text=name,
                fill=colors['text'],
                font=get_font(10),
                anchor='w',
                width=NAME_W - text_x - 8,
            )
            programmes = []
            if guide:
                programmes = guide.programmes_between(tvg_id, start, stop)
            if not programmes:
                canvas.create_text(
                    NAME_W + 10, y + ROW_H / 2,
                    text='Sin datos',
                    fill=colors['text_muted'],
                    font=get_font(9),
                    anchor='w',
                )
                continue
            for prog in programmes:
                left = NAME_W + max(0, (prog.start - start) / 3600 * PX_HOUR)
                right = NAME_W + min(HOURS * PX_HOUR, (prog.stop - start) / 3600 * PX_HOUR)
                if right - left < 8:
                    continue
                current = prog.start <= now < prog.stop
                fill = colors['select_bg'] if current else colors['surface']
                outline = colors['accent'] if current else colors['border']
                canvas.create_rectangle(
                    left + 1, y + 4, right - 1, y + ROW_H - 4,
                    fill=fill, outline=outline,
                )
                label = prog.title or ''
                if right - left > 40:
                    canvas.create_text(
                        left + 6, y + ROW_H / 2,
                        text=label,
                        fill=colors['select_fg'] if current else colors['text'],
                        font=get_font(9, 'bold' if current else 'normal'),
                        anchor='w',
                        width=right - left - 10,
                    )

        now_x = NAME_W + (now - start) / 3600 * PX_HOUR
        if NAME_W <= now_x <= NAME_W + HOURS * PX_HOUR:
            canvas.create_line(now_x, 0, now_x, height, fill=colors['accent'], width=2)


def show_epg_grid(player):
    if not getattr(player, 'window', None):
        return None
    grid = EpgGridWindow(player)
    return grid
