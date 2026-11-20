from .emojiquiz import EmojiQuizGame
from .guessnum import GuessNumberGame
from .penalty import PenaltyGame
from .scribble import ScribbleGame
from .wyr import WouldYouRatherGame
from .mathblitz import MathBlitzGame
from .poker import PokerGame
from .simon import SimonGame
from .yahtzee import YahtzeeGame

GAMES = {"poker": PokerGame, "yahtzee": YahtzeeGame, "simon": SimonGame, "mathblitz": MathBlitzGame, "wyr": WouldYouRatherGame, "guessnum": GuessNumberGame, "emojiquiz": EmojiQuizGame, "penalty": PenaltyGame, "scribble": ScribbleGame}
INFO = {
    "poker": {"title": "Poker Showdown", "emoji": "♠️", "min": 2, "max": 6, "shuffle": True, "cmd": "playpoker", "cat": "Casino", "new": True, "turn": 12},
    "yahtzee": {"title": "Yahtzee", "emoji": "🎲", "min": 2, "max": 4, "shuffle": True, "cmd": "playyahtzee", "cat": "Classic", "new": True, "turn": 30},
    "simon": {"title": "Simon Duel", "emoji": "🔴", "min": 2, "max": 6, "shuffle": True, "cmd": "playsimon", "cat": "Brain", "new": True, "turn": 10},
    "mathblitz": {"title": "MathBlitz", "emoji": "➗", "min": 2, "max": 6, "shuffle": True, "cmd": "playmath", "cat": "Brain", "new": True, "turn": 18},
    "wyr": {"title": "Would You Rather", "emoji": "🤔", "min": 2, "max": 8, "shuffle": True, "cmd": "playwyr", "cat": "Party", "new": True, "turn": 20},
    "guessnum": {"title": "Guess the Number", "emoji": "🔢", "min": 2, "max": 6, "shuffle": True, "cmd": "playguess", "cat": "Brain", "new": True, "turn": 20},
    "emojiquiz": {"title": "EmojiQuiz", "emoji": "🎬", "min": 2, "max": 6, "shuffle": True, "cmd": "playemoji", "cat": "Party", "new": True, "turn": 25},
    "penalty": {"title": "Penalty Shootout", "emoji": "⚽", "min": 2, "max": 2, "shuffle": True, "cmd": "playpenalty", "cat": "Action", "new": True, "turn": 10},
    "scribble": {"title": "Scribble", "emoji": "🎨", "min": 2, "max": 8, "shuffle": True, "cmd": "playscribble", "cat": "Party", "new": True, "turn": 70},
}
