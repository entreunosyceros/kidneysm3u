from player_controls import PlayerControlsMixin
from player_iptv import IptvPlaybackMixin
from player_overlay import ChannelNoticeMixin
from video_player import VideoPlayer


def test_player_uses_iptv_overlay_and_controls_mixins():
    assert issubclass(VideoPlayer, IptvPlaybackMixin)
    assert issubclass(VideoPlayer, ChannelNoticeMixin)
    assert issubclass(VideoPlayer, PlayerControlsMixin)
    for name in (
        '_play_iptv_url',
        '_watch_iptv_start',
        '_show_channel_unavailable',
        'hide_controls_and_menu',
        'toggle_play',
        'save_iptv_resume',
        'play_history_url',
    ):
        assert hasattr(VideoPlayer, name)
