from channel_zap import (
    zap_buffer_append,
    zap_buffer_backspace,
    zap_event_digit,
    zap_max_digits,
    zap_number,
    zap_visible_index,
)


class _Event:
    def __init__(self, keysym='', char=''):
        self.keysym = keysym
        self.char = char


def test_zap_maps_one_based_visible_list():
    assert zap_visible_index(1, 10) == 0
    assert zap_visible_index(10, 10) == 9
    assert zap_visible_index(0, 10) is None
    assert zap_visible_index(11, 10) is None
    assert zap_visible_index(1, 0) is None
    assert zap_number('007') == 7
    assert zap_visible_index(zap_number('007'), 20) == 6


def test_zap_buffer_timeout_digits_and_numpad():
    assert zap_max_digits(9) == 1
    assert zap_max_digits(10) == 2
    assert zap_max_digits(5000) == 4
    assert zap_buffer_append('', '1', 80) == '1'
    assert zap_buffer_append('1', '2', 80) == '12'
    assert zap_buffer_append('12', '3', 80) == '23'
    assert zap_buffer_backspace('12') == '1'
    assert zap_buffer_backspace('') == ''
    assert zap_event_digit(_Event(keysym='5', char='5')) == '5'
    assert zap_event_digit(_Event(keysym='KP_9', char='')) == '9'
    assert zap_event_digit(_Event(keysym='g', char='g')) == ''
