"""Aviso de canal IPTV que no arranca (overlay y banner)."""

import sys
import tkinter as tk

from ui_theme import get_colors, get_font


class ChannelNoticeMixin:
    def _pack_video_frame(self):
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
            top.geometry(f'{int(width)}x{int(height)}+{int(x)}+{int(y)}')
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

    def _hide_channel_status(self):
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
        card = tk.Frame(
            parent,
            bg=colors['surface'],
            highlightbackground=colors['border'],
            highlightthickness=1,
            padx=28,
            pady=22,
        )
        card.place(relx=0.5, rely=0.5, anchor='center')
        title = (name or '').strip() or 'Este canal'
        tk.Label(
            card,
            text=title,
            font=get_font(16, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            wraplength=460,
            justify='center',
        ).pack()
        tk.Label(
            card,
            text='Este canal por el momento no funciona',
            font=get_font(12),
            bg=colors['surface'],
            fg=colors['text_muted'],
            wraplength=460,
            justify='center',
        ).pack(pady=(12, 0))

    def _show_controls_banner(self, text, colors):
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
        self._show_channel_unavailable(name)
