"""Aviso de canal IPTV que no arranca (overlay y banner)."""

import sys
import tkinter as tk
from tkinter import ttk

from display_text import plain_display_text
from ui_theme import get_colors, get_font

YOUTUBE_TITLE_HIDE_MS = 2500
YOUTUBE_TITLE_BAR_H = 44


class YoutubeTitleOverlayMixin:
    """Clase que representa youtubetitleoverlaymixin."""
    def _video_overlay_title(self):
        """Texto del canal o vídeo para la barra superpuesta al mover el ratón."""
        if getattr(self, '_playing_youtube', False):
            handler = getattr(self, 'youtube_handler', None)
            title = ''
            if handler:
                title = (getattr(handler, '_loading_title_text', None) or '').strip()
            if (not title or title == 'YouTube') and self.current_channel is not None:
                try:
                    title = self.channels[self.current_channel][0]
                except (IndexError, TypeError):
                    title = ''
            return plain_display_text(title, '')
        if self.current_channel is not None and getattr(self, '_media_started', False):
            try:
                return plain_display_text(self.channels[self.current_channel][0], '')
            except (IndexError, TypeError):
                return ''
        return ''

    def _youtube_title_text(self):
        """Uso interno: youtube title text."""
        return self._video_overlay_title()

    def _video_overlay_motion_allowed(self):
        """True si debe mostrarse el título al mover el ratón sobre el vídeo."""
        if getattr(self, '_iptv_failed', False):
            return False
        if getattr(self, '_playing_youtube', False):
            return True
        return (
            self.current_channel is not None
            and getattr(self, '_media_started', False)
            and not getattr(self, '_playing_youtube', False)
        )

    def _cancel_youtube_title_hide_job(self):
        """Uso interno: cancel youtube title hide job."""
        job = getattr(self, '_yt_title_hide_job', None)
        self._yt_title_hide_job = None
        if not job or not self._widget_exists(getattr(self, 'window', None)):
            return
        try:
            self.window.after_cancel(job)
        except tk.TclError:
            pass

    def _hide_youtube_title_overlay(self):
        """Uso interno: hide youtube title superposición."""
        self._cancel_youtube_title_hide_job()
        top = getattr(self, '_yt_title_top', None)
        self._yt_title_top = None
        if top is not None:
            try:
                top.destroy()
            except tk.TclError:
                pass

    def _youtube_title_target_frame(self):
        """Uso interno: youtube title target marco."""
        if callable(getattr(self, '_video_target_frame', None)):
            target = self._video_target_frame()
            if self._widget_exists(target):
                return target
        video = getattr(self, 'video_frame', None)
        if self._widget_exists(video):
            return video
        return None

    def _position_youtube_title_overlay(self, event=None):
        """Uso interno: position youtube title superposición."""
        top = getattr(self, '_yt_title_top', None)
        if not self._widget_exists(top):
            return
        area = self._youtube_title_target_frame()
        if not self._widget_exists(area):
            return
        try:
            area.update_idletasks()
            x = area.winfo_rootx()
            y = area.winfo_rooty()
            width = max(160, area.winfo_width())
            top.geometry(f'{int(width)}x{YOUTUBE_TITLE_BAR_H}+{int(x)}+{int(y)}')
            label = getattr(self, '_yt_title_label', None)
            if self._widget_exists(label):
                from ui_layout import wraplength_for
                label.configure(wraplength=wraplength_for(width, padding=28, min_wrap=80))
            top.lift()
            try:
                top.attributes('-topmost', True)
            except tk.TclError:
                pass
        except tk.TclError:
            pass

    def _show_youtube_title_overlay(self):
        """Uso interno: show youtube title superposición."""
        title = self._video_overlay_title()
        if not title or not self._widget_exists(self.window):
            self._hide_youtube_title_overlay()
            return
        area = self._youtube_title_target_frame()
        if not self._widget_exists(area):
            return
        label = getattr(self, '_yt_title_label', None)
        top = getattr(self, '_yt_title_top', None)
        if self._widget_exists(top) and self._widget_exists(label):
            try:
                label.configure(text=title)
                self._position_youtube_title_overlay()
                top.deiconify()
                top.lift()
            except tk.TclError:
                pass
            return
        self._hide_youtube_title_overlay()
        colors = get_colors()
        top = tk.Toplevel(self.window)
        top.withdraw()
        try:
            top.overrideredirect(True)
        except tk.TclError:
            pass
        try:
            top.attributes('-topmost', True)
        except tk.TclError:
            pass
        try:
            top.wm_attributes('-type', 'splash')
        except tk.TclError:
            pass
        top.configure(bg=colors['surface'])
        bar = tk.Frame(top, bg=colors['surface'], highlightthickness=0, padx=14, pady=10)
        bar.pack(fill=tk.BOTH, expand=True)
        label = tk.Label(
            bar,
            text=title,
            font=get_font(12, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            anchor='w',
            justify='left',
            wraplength=720,
        )
        label.pack(fill=tk.BOTH, expand=True)
        self._yt_title_top = top
        self._yt_title_label = label
        self._position_youtube_title_overlay()
        try:
            top.deiconify()
            top.lift()
        except tk.TclError:
            pass
        try:
            self.window.bind('<Configure>', self._position_youtube_title_overlay, add='+')
            area.bind('<Configure>', self._position_youtube_title_overlay, add='+')
        except tk.TclError:
            pass

    def _schedule_youtube_title_hide(self):
        """Uso interno: schedule youtube title hide."""
        if not self._widget_exists(getattr(self, 'window', None)):
            return
        self._cancel_youtube_title_hide_job()
        self._yt_title_hide_job = self.window.after(
            YOUTUBE_TITLE_HIDE_MS,
            self._hide_youtube_title_overlay,
        )

    def _on_youtube_video_motion(self, event=None):
        """Callback interno para youtube video motion."""
        if not self._video_overlay_motion_allowed():
            return
        if self._widget_exists(getattr(self, '_yt_replay_frame', None)):
            return
        if not self._video_overlay_title():
            return
        self._show_youtube_title_overlay()
        self._schedule_youtube_title_hide()

    def _bind_youtube_title_motion(self, widget):
        """Uso interno: bind youtube title motion."""
        if not self._widget_exists(widget):
            return
        try:
            widget.bind('<Motion>', self._on_youtube_video_motion, add='+')
        except tk.TclError:
            pass


class ChannelNoticeMixin:
    """Clase que representa channelnoticemixin."""
    def _pack_video_frame(self):
        """Uso interno: pack video marco."""
        frame = getattr(self, 'video_frame', None)
        if not self._widget_exists(frame):
            return
        try:
            if frame.winfo_ismapped():
                return
        except tk.TclError:
            pass
        try:
            controls = getattr(self, 'controls_frame', None)
            if self._widget_exists(controls) and controls.winfo_ismapped():
                frame.pack(fill=tk.BOTH, expand=True, before=controls)
            else:
                frame.pack(fill=tk.BOTH, expand=True)
        except tk.TclError:
            try:
                frame.pack(fill=tk.BOTH, expand=True)
            except tk.TclError:
                pass

    def _release_vlc_video_window(self):
        """Uso interno: release VLC video ventana."""
        if not self.player:
            return
        try:
            self.player.stop()
        except Exception:
            pass
        try:
            if sys.platform.startswith('win'):
                self.player.set_hwnd(0)
            elif sys.platform == 'darwin':
                self.player.set_nsobject(0)
            else:
                self.player.set_xwindow(0)
        except Exception:
            pass

    def _position_notice_top(self, event=None):
        """Uso interno: position notice top."""
        top = getattr(self, '_iptv_notice_top', None)
        if not self._widget_exists(top) or not self._widget_exists(self.window):
            return
        area = getattr(self, 'player_frame', None)
        if not self._widget_exists(area):
            area = getattr(self, 'video_frame', None)
        if not self._widget_exists(area):
            return
        try:
            area.update_idletasks()
            x = area.winfo_rootx()
            y = area.winfo_rooty()
            width = max(120, area.winfo_width())
            height = max(80, area.winfo_height())
            controls = getattr(self, 'controls_frame', None)
            if self._widget_exists(controls) and controls.winfo_ismapped():
                height = max(80, height - controls.winfo_height() - 8)
            panel = getattr(self, '_iptv_status_frame', None)
            top.geometry(f'{int(width)}x{int(height)}+{int(x)}+{int(y)}')
            from ui_layout import wraplength_for
            wrap = wraplength_for(width, padding=56, min_wrap=120, max_wrap=560)
            for host in (top, panel):
                if not self._widget_exists(host):
                    continue
                for label in getattr(host, '_notice_labels', ()) or ():
                    try:
                        label.configure(wraplength=wrap)
                    except tk.TclError:
                        pass
            top.lift()
            try:
                top.attributes('-topmost', True)
            except tk.TclError:
                pass
        except tk.TclError:
            pass
        panel = getattr(self, '_iptv_status_frame', None)
        if self._widget_exists(panel):
            try:
                panel.lift()
            except tk.TclError:
                pass

    def _iptv_progress_target_area(self):
        """Uso interno: área del reproductor para centrar el aviso."""
        area = getattr(self, 'player_frame', None)
        if self._widget_exists(area):
            return area
        return getattr(self, 'video_frame', None)

    def _position_iptv_progress_overlay(self, event=None):
        """Uso interno: coloca el aviso de reconexión sobre el vídeo."""
        top = getattr(self, '_iptv_progress_top', None)
        if not self._widget_exists(top) or not self._widget_exists(self.window):
            return
        area = self._iptv_progress_target_area()
        if not self._widget_exists(area):
            return
        try:
            area.update_idletasks()
            x = area.winfo_rootx()
            y = area.winfo_rooty()
            width = max(160, area.winfo_width())
            height = max(120, area.winfo_height())
            controls = getattr(self, 'controls_frame', None)
            if self._widget_exists(controls) and controls.winfo_ismapped():
                height = max(120, height - controls.winfo_height() - 8)
            top.geometry(f'{int(width)}x{int(height)}+{int(x)}+{int(y)}')
            card = getattr(top, '_progress_card', None)
            if self._widget_exists(card):
                from ui_layout import wraplength_for
                wrap = wraplength_for(width, padding=72, min_wrap=160, max_wrap=480)
                for label in getattr(card, '_progress_labels', ()) or ():
                    try:
                        label.configure(wraplength=wrap)
                    except tk.TclError:
                        pass
            top.lift()
            try:
                top.attributes('-topmost', True)
            except tk.TclError:
                pass
        except tk.TclError:
            pass
        panel = getattr(self, '_iptv_progress_frame', None)
        if self._widget_exists(panel):
            try:
                panel.lift()
            except tk.TclError:
                pass

    def _hide_iptv_progress_overlay(self):
        """Quita el aviso breve de reconexión o buffer IPTV."""
        self._iptv_progress_title = None
        bar = getattr(self, '_iptv_progress_bar', None)
        if bar is not None:
            try:
                bar.stop()
            except tk.TclError:
                pass
        self._iptv_progress_bar = None
        top = getattr(self, '_iptv_progress_top', None)
        self._iptv_progress_top = None
        if top is not None:
            try:
                top.destroy()
            except tk.TclError:
                pass
        frame = getattr(self, '_iptv_progress_frame', None)
        self._iptv_progress_frame = None
        if frame is not None:
            try:
                frame.destroy()
            except tk.TclError:
                pass
        clear_status = getattr(self, 'clear_player_status', None)
        if callable(clear_status):
            clear_status('Reconectando')
            clear_status('Conectando')
            clear_status('Bufferizando')
            clear_status('Ampliando buffer')
            clear_status('Reintentando')

    def _fill_iptv_progress_card(self, parent, title, detail, colors):
        """Uso interno: tarjeta centrada con mensaje de reconexión."""
        card = tk.Frame(
            parent,
            bg=colors['surface'],
            highlightbackground=colors['border'],
            highlightthickness=1,
            padx=24,
            pady=18,
        )
        card.place(relx=0.5, rely=0.5, anchor='center')
        title_label = tk.Label(
            card,
            text=title,
            font=get_font(15, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            wraplength=420,
            justify='center',
        )
        title_label.pack()
        labels = [title_label]
        if detail:
            detail_label = tk.Label(
                card,
                text=detail,
                font=get_font(10),
                bg=colors['surface'],
                fg=colors['text_muted'],
                wraplength=420,
                justify='center',
            )
            detail_label.pack(pady=(10, 12))
            labels.append(detail_label)
        bar = ttk.Progressbar(card, length=280, mode='indeterminate')
        bar.pack(fill=tk.X)
        try:
            bar.start(12)
        except tk.TclError:
            pass
        parent._progress_card = card
        card._progress_labels = tuple(labels)
        return card, bar

    def _show_iptv_progress_overlay(self, title, detail=''):
        """Aviso breve encima del vídeo durante reconexión o subida de buffer."""
        if getattr(self, '_playing_youtube', False) or getattr(self, '_iptv_failed', False):
            return
        if not self._widget_exists(self.window):
            return
        title = plain_display_text(title, 'Reconectando…')
        detail = plain_display_text(detail, '')
        current = getattr(self, '_iptv_progress_title', None)
        if current == title and (
            self._widget_exists(getattr(self, '_iptv_progress_top', None))
            or self._widget_exists(getattr(self, '_iptv_progress_frame', None))
        ):
            self._position_iptv_progress_overlay()
            return
        self._iptv_progress_title = title
        self._hide_iptv_progress_overlay()
        self._iptv_progress_title = title
        colors = get_colors()
        video = getattr(self, 'video_frame', None)
        parent = getattr(self, 'player_frame', None)
        overlay_parent = parent if self._widget_exists(parent) else video
        if self._widget_exists(overlay_parent):
            panel = tk.Frame(overlay_parent, bg='#000000', highlightthickness=0)
            try:
                if self._widget_exists(video):
                    panel.place(in_=video, relx=0, rely=0, relwidth=1, relheight=1)
                    panel.lift(video)
                else:
                    panel.place(relx=0, rely=0, relwidth=1, relheight=1)
            except tk.TclError:
                panel.pack(fill=tk.BOTH, expand=True)
            _, bar = self._fill_iptv_progress_card(panel, title, detail, colors)
            self._iptv_progress_frame = panel
            self._iptv_progress_bar = bar
        top = tk.Toplevel(self.window)
        top.withdraw()
        try:
            top.overrideredirect(True)
        except tk.TclError:
            pass
        try:
            top.attributes('-topmost', True)
        except tk.TclError:
            pass
        try:
            top.wm_attributes('-type', 'splash')
        except tk.TclError:
            pass
        top.configure(bg='#000000')
        _, bar = self._fill_iptv_progress_card(top, title, detail, colors)
        self._iptv_progress_top = top
        if self._iptv_progress_bar is None:
            self._iptv_progress_bar = bar
        self._position_iptv_progress_overlay()
        try:
            top.deiconify()
            top.lift()
            top.update_idletasks()
        except tk.TclError:
            pass
        try:
            self.window.bind('<Configure>', self._position_iptv_progress_overlay, add='+')
            area = self._iptv_progress_target_area()
            if self._widget_exists(area):
                area.bind('<Configure>', self._position_iptv_progress_overlay, add='+')
        except tk.TclError:
            pass
        for delay in (80, 250, 700):
            self.window.after(delay, self._position_iptv_progress_overlay)
        set_status = getattr(self, 'set_player_status', None)
        if callable(set_status):
            set_status(title, timeout_ms=15000)

    def _hide_channel_status(self):
        """Uso interno: hide canal status."""
        self._hide_iptv_progress_overlay()
        self._hide_youtube_title_overlay()
        hide_replay = getattr(self, '_hide_youtube_replay_prompt', None)
        if hide_replay:
            hide_replay()
        self._iptv_failed = False
        self._iptv_ok_ticks = 0
        top = getattr(self, '_iptv_notice_top', None)
        self._iptv_notice_top = None
        if top is not None:
            try:
                top.destroy()
            except tk.TclError:
                pass
        frame = getattr(self, '_iptv_status_frame', None)
        self._iptv_status_frame = None
        if frame is not None:
            try:
                frame.destroy()
            except tk.TclError:
                pass
        banner = getattr(self, '_iptv_banner', None)
        self._iptv_banner = None
        if banner is not None:
            try:
                banner.destroy()
            except tk.TclError:
                pass
        self._pack_video_frame()

    def _fill_notice_card(self, parent, name, colors):
        """Uso interno: fill notice card."""
        card = tk.Frame(
            parent,
            bg=colors['surface'],
            highlightbackground=colors['border'],
            highlightthickness=1,
            padx=28,
            pady=22,
        )
        card.place(relx=0.5, rely=0.5, anchor='center')
        title = plain_display_text(name, 'Este canal')
        name_label = tk.Label(
            card,
            text=title,
            font=get_font(16, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            wraplength=460,
            justify='center',
        )
        name_label.pack()
        msg_label = tk.Label(
            card,
            text='Este canal por el momento no funciona',
            font=get_font(12),
            bg=colors['surface'],
            fg=colors['text_muted'],
            wraplength=460,
            justify='center',
        )
        msg_label.pack(pady=(12, 0))
        parent._notice_labels = (name_label, msg_label)
        parent._notice_card = card

    def _show_controls_banner(self, text, colors):
        """Uso interno: show controls banner."""
        old = getattr(self, '_iptv_banner', None)
        if self._widget_exists(old):
            try:
                old.destroy()
            except tk.TclError:
                pass
        controls = getattr(self, 'controls_frame', None)
        if not self._widget_exists(controls):
            self._iptv_banner = None
            return
        banner = tk.Label(
            controls,
            text=text,
            font=get_font(11, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            pady=8,
            wraplength=640,
            justify='center',
        )
        try:
            buttons = getattr(self, 'controls_buttons_frame', None)
            if self._widget_exists(buttons) and buttons.winfo_ismapped():
                banner.pack(side=tk.TOP, fill=tk.X, before=buttons, pady=(0, 4))
            else:
                banner.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        except tk.TclError:
            banner.pack(side=tk.TOP, fill=tk.X)
        self._iptv_banner = banner
        from ui_layout import bind_wraplength
        bind_wraplength(controls, padding=24, min_wrap=120)

    def _show_channel_unavailable(self, name):
        """Aviso encima del vídeo. En Linux VLC tapa los widgets del frame embebido."""
        if getattr(self, '_playing_youtube', False):
            return
        if not self._widget_exists(self.window):
            return
        already = self._iptv_failed and (
            self._widget_exists(getattr(self, '_iptv_notice_top', None))
            or self._widget_exists(getattr(self, '_iptv_status_frame', None))
            or self._widget_exists(getattr(self, '_iptv_banner', None))
        )
        if already:
            self._position_notice_top()
            return
        self._iptv_failed = True
        print(f"[IPTV] Aviso: «{name}» no funciona")
        handler = getattr(self, 'youtube_handler', None)
        if handler:
            handler.hide_loading()
        self.show_controls_and_menu()
        if self.hide_controls_timer:
            try:
                self.window.after_cancel(self.hide_controls_timer)
            except Exception:
                pass
            self.hide_controls_timer = None
        self._release_vlc_video_window()
        try:
            self.window.update_idletasks()
        except tk.TclError:
            pass
        colors = get_colors()
        parent = getattr(self, 'player_frame', None)
        video = getattr(self, 'video_frame', None)
        self._pack_video_frame()
        old_panel = getattr(self, '_iptv_status_frame', None)
        if self._widget_exists(old_panel):
            try:
                old_panel.destroy()
            except tk.TclError:
                pass
        overlay_parent = parent if self._widget_exists(parent) else video
        if self._widget_exists(overlay_parent):
            panel = tk.Frame(overlay_parent, bg='#000000', highlightthickness=0)
            try:
                if self._widget_exists(video):
                    panel.place(in_=video, relx=0, rely=0, relwidth=1, relheight=1)
                else:
                    panel.place(relx=0, rely=0, relwidth=1, relheight=1)
                panel.lift()
            except tk.TclError:
                panel.pack(fill=tk.BOTH, expand=True)
            self._fill_notice_card(panel, name, colors)
            self._iptv_status_frame = panel
        self._show_controls_banner('Este canal por el momento no funciona', colors)
        old_top = getattr(self, '_iptv_notice_top', None)
        if self._widget_exists(old_top):
            try:
                old_top.destroy()
            except tk.TclError:
                pass
        top = tk.Toplevel(self.window)
        top.withdraw()
        try:
            top.overrideredirect(True)
        except tk.TclError:
            pass
        try:
            top.attributes('-topmost', True)
        except tk.TclError:
            pass
        try:
            top.wm_attributes('-type', 'splash')
        except tk.TclError:
            pass
        top.configure(bg='#000000')
        self._fill_notice_card(top, name, colors)
        self._iptv_notice_top = top
        self._position_notice_top()
        try:
            top.deiconify()
            top.lift()
            top.update_idletasks()
        except tk.TclError:
            pass
        self._position_notice_top()
        try:
            self.window.bind('<Configure>', self._position_notice_top, add='+')
            if self._widget_exists(parent):
                parent.bind('<Configure>', self._position_notice_top, add='+')
        except tk.TclError:
            pass
        for delay in (80, 250, 700, 1500):
            self.window.after(delay, self._position_notice_top)

    def _iptv_report_unavailable(self, name):
        """Uso interno: IPTV report unavailable."""
        hide = getattr(self, '_hide_iptv_progress_overlay', None)
        if callable(hide):
            hide()
        self._show_channel_unavailable(name)
