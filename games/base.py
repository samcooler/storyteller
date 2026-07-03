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
