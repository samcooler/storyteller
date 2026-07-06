"""A tiny scene stack for the app shell.

The main loop used to juggle "am I in the menu, in a game, or showing the
options modal?" with a couple of booleans (`showing_options`, `active_game`)
and a nested if/elif. That doesn't generalize: overlays, confirmation
dialogs, a pause screen - each would add another flag and another branch.

A `Scene` is one screen's worth of behaviour (handle_event/update/draw). The
`SceneStack` keeps them in a stack: only the top scene receives input and
updates, but drawing walks up from the lowest *opaque* scene so a
non-opaque scene (a modal) renders on top of whatever it was pushed over.

Scenes drive navigation by *returning a command* from `handle_event` rather
than mutating shared shell state:

    return Push(OptionsScene())   # open a modal on top of me
    return Pop()                  # close myself, reveal what's underneath
    return Quit()                 # tear the whole stack down (exit the app)

Returning None means "handled, no navigation change."
"""


class Scene:
    """One screen in the stack. Subclasses override the hooks they need."""

    # False marks a modal/overlay: the scene below it still draws underneath.
    opaque = True

    def on_enter(self):
        """Called once, when this scene is first pushed onto the stack."""

    def on_reveal(self):
        """Called when this scene becomes the top again after the scene above
        it was popped. Distinct from on_enter so a game isn't reset() every
        time a modal closes over it."""

    def handle_event(self, event):
        """Handle one pygame event. Return a navigation command or None."""
        return None

    def update(self, dt):
        """Advance by dt seconds (top scene only)."""

    def draw(self, surface):
        """Render onto surface."""


# --- Navigation commands returned by Scene.handle_event ---------------------

class Push:
    """Push a new scene on top of the current one."""

    def __init__(self, scene):
        self.scene = scene


class Pop:
    """Remove the current scene, revealing the one beneath it."""


class Quit:
    """Tear down the whole stack; the app loop should exit."""


class SceneStack:
    def __init__(self, root):
        self.scenes = []
        self.quit = False
        self.push(root)

    @property
    def top(self):
        return self.scenes[-1] if self.scenes else None

    @property
    def empty(self):
        return not self.scenes

    def push(self, scene):
        self.scenes.append(scene)
        scene.on_enter()

    def pop(self):
        if self.scenes:
            self.scenes.pop()
        if self.scenes:
            self.top.on_reveal()

    def handle_event(self, event):
        top = self.top
        if top is None:
            return
        self._apply(top.handle_event(event))

    def update(self, dt):
        if self.top is not None:
            self.top.update(dt)

    def draw(self, surface):
        """Draw from the lowest opaque scene up to the top, so modals layer
        over the screen they were pushed onto."""
        if not self.scenes:
            return
        start = 0
        for i in range(len(self.scenes) - 1, -1, -1):
            if self.scenes[i].opaque:
                start = i
                break
        for scene in self.scenes[start:]:
            scene.draw(surface)

    def _apply(self, command):
        if command is None:
            return
        if isinstance(command, Push):
            self.push(command.scene)
        elif isinstance(command, Pop):
            self.pop()
        elif isinstance(command, Quit):
            self.scenes.clear()
            self.quit = True


class GameScene(Scene):
    """Adapts a `Game` (reset/handle_event/update/draw) into a Scene.

    The shell owns the universal "Esc leaves the game" gesture so individual
    games don't each reimplement it - `handle_event` intercepts BACK and pops,
    and only forwards everything else to the wrapped game.
    """

    def __init__(self, game):
        self.game = game

    def on_enter(self):
        self.game.reset()

    def handle_event(self, event):
        from games import input as actions
        if actions.of(event) == actions.BACK:
            return Pop()
        self.game.handle_event(event)
        return None

    def update(self, dt):
        self.game.update(dt)

    def draw(self, surface):
        self.game.draw(surface)
