"""Registry for the board-game group."""
from .battleship import BattleshipGame
from .checkers import CheckersGame
from .chess import ChessGame
from .gomoku import GomokuGame
from .reversi import ReversiGame
from .uttt import UltimateTTTGame

GAMES = {
    "chess": ChessGame,
    "checkers": CheckersGame,
    "reversi": ReversiGame,
    "gomoku": GomokuGame,
    "uttt": UltimateTTTGame,
    "battleship": BattleshipGame,
}

INFO = {
    "chess": {"title": "Chess", "emoji": "♟️", "min": 2, "max": 2, "shuffle": True, "cmd": "playchess", "cat": "Board", "new": True, "turn": 45},
    "checkers": {"title": "Checkers", "emoji": "🔵", "min": 2, "max": 2, "shuffle": True, "cmd": "playcheckers", "cat": "Board", "new": True, "turn": 30},
    "reversi": {"title": "Reversi", "emoji": "⚫", "min": 2, "max": 2, "shuffle": True, "cmd": "playreversi", "cat": "Board", "new": True, "turn": 25},
    "gomoku": {"title": "Gomoku", "emoji": "⭕", "min": 2, "max": 2, "shuffle": True, "cmd": "playgomoku", "cat": "Board", "new": True, "turn": 30},
    "uttt": {"title": "Ultimate Tic-Tac-Toe", "emoji": "❎", "min": 2, "max": 2, "shuffle": True, "cmd": "playuttt", "cat": "Board", "new": True, "turn": 30},
    "battleship": {"title": "Battleship", "emoji": "🚢", "min": 2, "max": 2, "shuffle": True, "cmd": "playbattleship", "cat": "Board", "new": True, "turn": 25},
}
