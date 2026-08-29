from favorites_manager import (
    add_favorite,
    favorite_entry,
    favorites_contain,
    normalize_favorites,
    remove_favorite,
)


def test_favorites_normalize_tuples_and_duplicates():
    items = [
        ('Uno', 'http://panel.example/1.ts'),
        ['Uno', 'http://panel.example/1.ts'],
        ('Dos', 'http://panel.example/2.ts'),
        ('Vacío', ''),
        ['Tres', 'http://panel.example/3.ts'],
    ]
    out = normalize_favorites(items)
    assert out == [
        ['Uno', 'http://panel.example/1.ts'],
        ['Dos', 'http://panel.example/2.ts'],
        ['Tres', 'http://panel.example/3.ts'],
    ]


def test_add_favorite_from_search_once_by_url():
    favorites, added = add_favorite([], 'La 1', 'http://panel.example/la1.ts')
    assert added is True
    assert favorites_contain(favorites, 'La 1 HD', 'http://panel.example/la1.ts')
    favorites, added = add_favorite(favorites, 'La 1 HD', 'http://panel.example/la1.ts')
    assert added is False
    assert len(favorites) == 1


def test_remove_favorite_matches_json_lists():
    favorites, removed = remove_favorite(
        [['La 1', 'http://panel.example/la1.ts']],
        'Otro nombre',
        'http://panel.example/la1.ts',
    )
    assert removed is True
    assert favorites == []
    assert favorite_entry('X', '')[1] == ''
    empty, added = add_favorite([], 'X', '')
    assert added is False
    assert empty == []


def test_export_import_json_and_m3u(tmp_path):
    from favorites_manager import (
        FAVORITES_KIND,
        merge_favorites,
        parse_favorites_payload,
        read_favorites_file,
        write_favorites_file,
    )

    items = [
        ['La 1', 'http://panel.example/la1.ts'],
        ['Clip', 'https://www.youtube.com/watch?v=dQw4w9wg'],
    ]
    json_path = tmp_path / 'kidneysm3u-favoritos.json'
    write_favorites_file(str(json_path), items)
    payload = json_path.read_text(encoding='utf-8')
    assert FAVORITES_KIND in payload
    loaded = read_favorites_file(str(json_path))
    assert loaded == items

    copied = tmp_path / 'favoritos.json'
    copied.write_text(
        '[["Uno", "http://panel.example/1.ts"], ["Uno", "http://panel.example/1.ts"]]',
        encoding='utf-8',
    )
    assert read_favorites_file(str(copied)) == [['Uno', 'http://panel.example/1.ts']]
    assert parse_favorites_payload([['Dos', 'http://panel.example/2.ts']]) == [
        ['Dos', 'http://panel.example/2.ts'],
    ]

    m3u_path = tmp_path / 'favoritos.m3u'
    write_favorites_file(str(m3u_path), items)
    text = m3u_path.read_text(encoding='utf-8')
    assert text.startswith('#EXTM3U')
    assert 'La 1' in text
    assert read_favorites_file(str(m3u_path)) == items

    merged, added, skipped = merge_favorites(items[:1], items)
    assert added == 1
    assert skipped == 1
    assert merged == items
    same, added, skipped = merge_favorites(items, items)
    assert added == 0
    assert skipped == 2
    assert same == items
    bogus = tmp_path / 'notas.txt'
    bogus.write_text('hola', encoding='utf-8')
    try:
        read_favorites_file(str(bogus))
        assert False, 'expected ValueError'
    except ValueError:
        pass
