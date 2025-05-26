class FavoritesManager:
    def __init__(self, video_player):
        self.video_player = video_player
        self.favorites = []
        self.load_favorites()

    def add_favorite(self, channel_name):
        """Añade un canal a favoritos si no está ya presente"""
        for name, url in self.video_player.channels:
            if name == channel_name:
                channel_tuple = (name, url)
                if channel_tuple not in self.video_player.favorites:
                    self.video_player.favorites.append(channel_tuple)
                    self.video_player.save_favorites()
                    return True
        return False

    def remove_favorite(self, channel_name):
        """Elimina un canal de favoritos si está presente"""
        for favorite in self.video_player.favorites[:]:  # Crear una copia para iterar
            name, _ = favorite
            if name == channel_name:
                self.video_player.favorites.remove(favorite)
                self.video_player.save_favorites()
                return True
        return False

    def load_favorites(self):
        """Carga los favoritos del video player"""
        self.video_player.load_favorites()
        self.favorites = self.video_player.favorites
