from player_controls import PlayerControlsMixin
from player_iptv import IptvPlaybackMixin
from player_overlay import ChannelNoticeMixin
from player_pip import PlayerPipMixin
from video_player import VideoPlayer


def test_player_uses_iptv_overlay_and_controls_mixins():
    assert issubclass(VideoPlayer, IptvPlaybackMixin)
    assert issubclass(VideoPlayer, ChannelNoticeMixin)
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
