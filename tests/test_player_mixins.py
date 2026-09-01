from player_controls import PlayerControlsMixin
from player_iptv import IptvPlaybackMixin
from player_overlay import ChannelNoticeMixin, YoutubeTitleOverlayMixin
from player_pip import PlayerPipMixin, pip_surface_ready
from video_player import VideoPlayer, popup_menu_origin


def test_player_uses_iptv_overlay_and_controls_mixins():
    assert issubclass(VideoPlayer, IptvPlaybackMixin)
    assert issubclass(VideoPlayer, ChannelNoticeMixin)
    assert issubclass(VideoPlayer, YoutubeTitleOverlayMixin)
    assert issubclass(VideoPlayer, PlayerControlsMixin)
    assert issubclass(VideoPlayer, PlayerPipMixin)
    for name in (
        '_play_iptv_url',
        '_watch_iptv_start',
        '_show_channel_unavailable',
        'hide_controls_and_menu',
        'toggle_play',
        'save_iptv_resume',
        'play_history_url',
        'toggle_stream_recording',
        'start_stream_recording',
        'toggle_pip',
        'open_pip',
        'toggle_always_on_top',
        'update_yt_dlp',
    ):
        assert hasattr(VideoPlayer, name)


def test_pip_mixin_uses_main_frame_when_closed():
    class Dummy(PlayerPipMixin):
        video_frame = object()
        _pip_frame = None
        _pip_window = None

        def _widget_exists(self, widget):
            return widget is not None

    dummy = Dummy()
    assert dummy._video_target_frame() is dummy.video_frame
    assert dummy.pip_is_open() is False


def test_pip_mixin_uses_pip_frame_when_open():
    class Dummy(PlayerPipMixin):
        video_frame = object()
        _pip_frame = object()
        _pip_window = object()

        def _widget_exists(self, widget):
            return widget is not None

    dummy = Dummy()
    assert dummy._video_target_frame() is dummy._pip_frame
    assert dummy.pip_is_open() is True


def test_pip_surface_needs_real_size():
    assert pip_surface_ready(480, 270, True) is True
    assert pip_surface_ready(1, 1, True) is False
    assert pip_surface_ready(480, 270, False) is False
    assert pip_surface_ready('x', 270, True) is False


def test_popup_menu_opens_below_when_there_is_room():
    x, y = popup_menu_origin(10, 100, 30, 200, 120, 0, 0, 800, 600)
    assert (x, y) == (10, 130)


def test_popup_menu_opens_above_when_button_is_at_bottom():
    x, y = popup_menu_origin(100, 1040, 40, 220, 180, 0, 0, 1920, 1080)
    assert (x, y) == (100, 860)


def test_popup_menu_clamps_when_too_tall_above():
    x, y = popup_menu_origin(10, 200, 30, 200, 500, 0, 0, 800, 600)
    assert x == 10
    assert y == 4


def test_popup_menu_clamps_x_to_stay_in_window():
    x, y = popup_menu_origin(750, 100, 30, 200, 80, 0, 0, 800, 600)
    assert x == 596
    assert y == 130


def test_youtube_title_text_uses_handler_title():
    class Dummy(YoutubeTitleOverlayMixin):
        _playing_youtube = True
        current_channel = None
        youtube_handler = type('H', (), {'_loading_title_text': 'Mi vídeo'})()

        def _widget_exists(self, widget):
            return False

    assert Dummy()._youtube_title_text() == 'Mi vídeo'


def test_hide_controls_keeps_bar_when_popup_open():
    class Dummy(PlayerControlsMixin):
        _posted_popup = object()
        timer_resets = 0

        def reset_hide_controls_timer(self):
            self.timer_resets += 1

        def _dismiss_track_menus(self):
            raise AssertionError('no debe cerrar el menú al ocultar controles')

    dummy = Dummy()
    dummy.hide_controls_and_menu()
    assert dummy.timer_resets == 1
