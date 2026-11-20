from .hangman import HangmanGame
from .mafia import MafiaGame
from .mastermind import MastermindGame
from .trivia import TriviaGame

GAMES = {"mafia": MafiaGame, "hangman": HangmanGame, "mastermind": MastermindGame, "trivia": TriviaGame}
INFO = {
    "mafia": {"title": "Mafia", "emoji": "🕵️", "min": 4, "max": 10, "shuffle": True, "cmd": "playmafia", "cat": "Party", "new": True, "turn": 40},
    "hangman": {"title": "Hangman", "emoji": "🔤", "min": 2, "max": 6, "shuffle": True, "cmd": "playhangman", "cat": "Party", "new": True, "turn": 25},
    "mastermind": {"title": "Mastermind", "emoji": "🎯", "min": 2, "max": 2, "shuffle": True, "cmd": "playmastermind", "cat": "Brain", "new": True, "turn": 45},
    "trivia": {"title": "Trivia Quiz", "emoji": "❓", "min": 2, "max": 6, "shuffle": True, "cmd": "playtrivia", "cat": "Brain", "new": True, "turn": 15},
}
