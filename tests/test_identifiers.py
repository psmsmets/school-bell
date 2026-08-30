from school_bell.identifiers import (
    content_hash,
    schedule_entry_id,
    short_hash,
    trigger_id,
)


def test_content_hash_ignores_json_key_order_and_whitespace():
    first = {'schedule': {'Mon': {'08:30': 0}}, 'name': 'école'}
    second = {'name': 'école', 'schedule': {'Mon': {'08:30': 0}}}

    assert content_hash(first) == content_hash(second)


def test_config_and_schedule_hashes_have_separate_semantics():
    with_gpio = {
        'schedule': {'Mon': {'08:30': 0}},
        'buzz_gpio': [26, 20],
    }
    without_gpio = {'schedule': {'Mon': {'08:30': 0}}}

    assert content_hash(with_gpio) != content_hash(without_gpio)
    assert content_hash(with_gpio['schedule']) == content_hash(
        without_gpio['schedule']
    )


def test_schedule_and_trigger_identifiers_are_stable_and_separate():
    entry = schedule_entry_id('Monday', '08:30:00', '0')

    assert entry == schedule_entry_id('Monday', '08:30:00', '0')
    assert entry != schedule_entry_id('Monday', '08:31:00', '0')
    assert trigger_id(
        'bell-01', 'schedule-a', entry, '2026-09-07T08:30:00+02:00'
    ) == trigger_id(
        'bell-01', 'schedule-a', entry, '2026-09-07T08:30:00+02:00'
    )
    assert trigger_id(
        'bell-01', 'schedule-a', entry, '2026-09-07T08:30:00+02:00'
    ) != trigger_id(
        'bell-01', 'schedule-a', entry, '2026-09-14T08:30:00+02:00'
    )


def test_short_hash_is_a_twelve_character_display_fingerprint():
    complete = content_hash({'schedule': {'Mon': {'08:30': 0}}})

    assert short_hash(complete) == complete[:12]
    assert len(short_hash(complete)) == 12
