"""Card games: UNO, Crazy Eights, Go Fish, Blackjack, Teen Patti."""
from .blackjack import BlackjackGame
from .crazy8 import CrazyEightsGame
from .gofish import GoFishGame
from .teenpatti import TeenPattiGame
from .uno import UnoGame

GAMES = {
    "uno": UnoGame,
    "crazy8": CrazyEightsGame,
    "gofish": GoFishGame,
    "blackjack": BlackjackGame,
    "teenpatti": TeenPattiGame,
}

INFO = {
    "uno": {"title": "UNO", "emoji": "🟥", "min": 2, "max": 6, "shuffle": True, "cmd": "playuno", "cat": "Cards", "new": True, "turn": 25},
    "crazy8": {"title": "Crazy Eights", "emoji": "🎱", "min": 2, "max": 5, "shuffle": True, "cmd": "playcrazy8", "cat": "Cards", "new": True, "turn": 25},
    "gofish": {"title": "Go Fish", "emoji": "🐟", "min": 2, "max": 4, "shuffle": True, "cmd": "playgofish", "cat": "Cards", "new": True, "turn": 25},
    "blackjack": {"title": "Blackjack", "emoji": "🂡", "min": 2, "max": 5, "shuffle": False, "cmd": "playblackjack", "cat": "Casino", "new": True, "turn": 20},
    "teenpatti": {"title": "Teen Patti", "emoji": "🃏", "min": 2, "max": 6, "shuffle": True, "cmd": "playteenpatti", "cat": "Casino", "new": True, "turn": 25},
}
