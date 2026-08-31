#!/usr/bin/env python3
"""Ventana de chat Twitch con WebKitGTK (Python del sistema en Linux)."""

import argparse
import sys


def _configure_webview(webview):
    settings = webview.get_settings()
    settings.set_enable_javascript(True)
    settings.set_enable_mediasource(True)
    settings.set_enable_webaudio(True)
    settings.set_enable_webgl(True)
    settings.set_enable_media_stream(True)
    try:
        settings.set_media_playback_requires_user_gesture(False)
    except (AttributeError, TypeError):
        pass


def main():
    parser = argparse.ArgumentParser(description='Ventana de chat Twitch')
    parser.add_argument('--url', required=True)
    parser.add_argument('--title', default='Chat')
    parser.add_argument('--width', type=int, default=380)
    parser.add_argument('--height', type=int, default=640)
    args = parser.parse_args()

    try:
        import gi
    except ImportError as exc:
        print(f'PyGObject (gi) no disponible: {exc}', file=sys.stderr)
        return 1

    gi.require_version('Gtk', '3.0')
    gi.require_version('WebKit2', '4.1')
    from gi.repository import Gtk, WebKit2

    width = max(280, args.width)
    height = max(320, args.height)
    window = Gtk.Window(title=args.title, default_width=width, default_height=height)
    window.set_default_size(width, height)

    webview = WebKit2.WebView()
    _configure_webview(webview)
    webview.set_hexpand(True)
    webview.set_vexpand(True)
    webview.load_uri(args.url)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
    scrolled.add(webview)
    window.add(scrolled)
    window.connect('destroy', Gtk.main_quit)
    window.show_all()
    Gtk.main()
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
