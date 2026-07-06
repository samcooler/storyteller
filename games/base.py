class Game:
    """Base class every game in the switcher implements."""

    name = "Unnamed Game"
    description = ""

    def __init__(self, screen):
        self.screen = screen

    def handle_event(self, event):
        """Handle a single pygame event."""

    def update(self, dt):
        """Advance game state by dt seconds."""

    def draw(self, surface):
        """Draw the current frame onto surface."""

    def reset(self):
        """Called each time the game is (re)selected from the menu."""

    def serialize(self):
        """Return a JSON-serializable dict capturing enough state to resume
        this game later, or None if it doesn't support save/load. Paired
        with `games/save.py`, which owns the file I/O/versioning; this only
        owns *what* goes in the blob."""
        return None

    def deserialize(self, data):
        """Restore state from a dict previously returned by `serialize`,
        in place of calling `reset`."""
        raise NotImplementedError
