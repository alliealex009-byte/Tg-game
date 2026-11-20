from .dominoes import DominoesGame
from .chatclash import ChatClashGame
from .coinpulse import CoinPulseGame
from .squadduel import SquadDuelGame
from .telearena import TeleArenaGame
from .clickrush import ClickRushGame
from .partydrop import PartyDropGame
from .pingplay import PingPlayGame
from .quest import QuestGame
from .race import RaceGame
from .tank import TankGame
from .wordle import WordleGame

GAMES = {"tank": TankGame, "race": RaceGame, "dominoes": DominoesGame, "wordle": WordleGame, "quest": QuestGame, "clickrush": ClickRushGame, "partydrop": PartyDropGame, "chatclash": ChatClashGame, "pingplay": PingPlayGame, "coinpulse": CoinPulseGame, "squadduel": SquadDuelGame, "telearena": TeleArenaGame}
INFO = {
    "tank": {"title": "Tank Duel", "emoji": "💣", "min": 2, "max": 2, "shuffle": True, "cmd": "playtank", "cat": "Action", "new": True, "turn": 30},
    "race": {"title": "Car Racing", "emoji": "🏎️", "min": 2, "max": 4, "shuffle": True, "cmd": "playrace", "cat": "Action", "new": True, "turn": 8},
    "dominoes": {"title": "Dominoes", "emoji": "🁣", "min": 2, "max": 4, "shuffle": True, "cmd": "playdominoes", "cat": "Board", "new": True, "turn": 30},
    "wordle": {"title": "Word Duel", "emoji": "🔠", "min": 2, "max": 4, "shuffle": True, "cmd": "playword", "cat": "Brain", "new": True, "turn": 40},
    "quest": {"title": "Adventure Quest", "emoji": "⚔️", "min": 2, "max": 4, "shuffle": True, "cmd": "playquest", "cat": "Action", "new": True, "turn": 12},
    "clickrush": {"title": "ClickRush", "emoji": "⚡", "min": 2, "max": 6, "shuffle": True, "cmd": "playclick", "cat": "Action", "new": True, "turn": 11},
    "partydrop": {"title": "PartyDrop", "emoji": "💣", "min": 2, "max": 6, "shuffle": True, "cmd": "playdrop", "cat": "Party", "new": True, "turn": 10},
    "chatclash": {"title": "ChatClash", "emoji": "⌨️", "min": 2, "max": 6, "shuffle": True, "cmd": "playchat", "cat": "Party", "new": True, "turn": 25},
    "pingplay": {"title": "PingPlay", "emoji": "🏓", "min": 2, "max": 4, "shuffle": True, "cmd": "playping", "cat": "Action", "new": True, "turn": 9},
    "coinpulse": {"title": "CoinPulse", "emoji": "🪙", "min": 2, "max": 6, "shuffle": True, "cmd": "playcoin", "cat": "Casino", "new": True, "turn": 8},
    "squadduel": {"title": "SquadDuel", "emoji": "🛡️", "min": 2, "max": 2, "shuffle": True, "cmd": "playsquad", "cat": "Brain", "new": True, "turn": 15},
    "telearena": {"title": "TeleArena", "emoji": "🌀", "min": 2, "max": 4, "shuffle": True, "cmd": "playtele", "cat": "Action", "new": True, "turn": 8},
}
