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
