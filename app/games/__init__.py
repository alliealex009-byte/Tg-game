"""Game registry. To add a game: write an engine (see tictactoe.py), register it here (GAMES + GAME_INFO),
add a renderer in webapp/ (HUB.UI.<type> = {build, apply}). Lobby, bets, timers, AFK, bots, spectators and rematch are automatic.

GAME_INFO keys: title, emoji, min/max players, shuffle (random seats), cmd (/playX), cat (menu category),
tag (one-line pitch used in share texts), turn (seconds per turn, optional), nobots (no computer players),
ambient (soft background sound in the mini app; off for Ludo and Carrom)."""
from .adventure import AdventureGame
from .arena import ArenaGame
from .battleship import BattleshipGame
from .blackjack import BlackjackGame
from .boxing import BoxingGame
from .bulls import BullsGame
from .carrom import CarromGame
from .checkers import CheckersGame
from .chess import ChessGame
from .connect4 import ConnectFourGame
from .dots import DotsGame
from .gomoku import GomokuGame
from .hangman import HangmanGame
from .highlow import HighLowGame
from .liars import LiarsGame
from .ludo import LudoGame
from .mafia import MafiaGame
from .memory import MemoryGame
from .nim import NimGame
from .pig import PigGame
from .quick import ReactionGame, TugGame
from .race import MathGame, ScrambleGame
from .racing import RacingGame
from .reversi import ReversiGame
from .rps import RPSGame
from .snakes import SnakesGame
from .teenpatti import TeenPattiGame
from .tictactoe import TicTacToeGame
from .trivia import TriviaGame
from .uno import UnoGame

GAMES = {
    "ludo": LudoGame, "snakes": SnakesGame, "carrom": CarromGame, "connect4": ConnectFourGame, "tictactoe": TicTacToeGame,
    "rps": RPSGame, "memory": MemoryGame,
    "chess": ChessGame, "checkers": CheckersGame, "reversi": ReversiGame, "dots": DotsGame, "gomoku": GomokuGame,
    "battleship": BattleshipGame, "uno": UnoGame, "teenpatti": TeenPattiGame, "blackjack": BlackjackGame, "highlow": HighLowGame,
    "pig": PigGame, "liars": LiarsGame, "nim": NimGame, "mafia": MafiaGame, "trivia": TriviaGame, "scramble": ScrambleGame,
    "mathduel": MathGame, "bulls": BullsGame, "hangman": HangmanGame, "boxing": BoxingGame, "racing": RacingGame,
    "adventure": AdventureGame, "arena": ArenaGame, "tugwar": TugGame, "reaction": ReactionGame,
}


def _g(title, emoji, lo, hi, cmd, cat, tag, shuffle=True, **extra):
    return dict(title=title, emoji=emoji, min=lo, max=hi, shuffle=shuffle, cmd=cmd, cat=cat, tag=tag, **extra)


GAME_INFO = {
    # classics
    "ludo": _g("Ludo", "🎲", 2, 4, "playludo", "Board", "roll a six, race home, capture rivals", False),
    "snakes": _g("Snakes & Ladders", "🐍", 2, 4, "playsnake", "Board", "climb the ladders, dodge the snakes"),
    "carrom": _g("Carrom", "🎯", 2, 2, "playcarrom", "Board", "flick the striker and pocket the coins"),
    "connect4": _g("Connect Four", "🔴", 2, 2, "playc4", "Brain", "drop discs and line up four"),
    "tictactoe": _g("Tic-Tac-Toe", "❌", 2, 2, "playttt", "Brain", "the quickest duel there is"),
    "rps": _g("Rock Paper Scissors", "✊", 2, 2, "playrps", "Quick", "best of three, no peeking"),
    "memory": _g("Memory Match", "🧠", 2, 2, "playmemory", "Brain", "flip cards and find the pairs"),
    # board & strategy
    "chess": _g("Chess", "♟", 2, 2, "playchess", "Board", "full rules: castling, en passant, checkmate", ambient=True, turn=60),
    "checkers": _g("Checkers", "⚫", 2, 2, "playcheckers", "Board", "jump, capture and crown your kings", ambient=True, turn=40),
    "reversi": _g("Reversi", "⚪", 2, 2, "playreversi", "Board", "flip the board to your colour", ambient=True, turn=40),
    "dots": _g("Dots & Boxes", "🔲", 2, 4, "playdots", "Board", "close the boxes, steal the turns", turn=30),
    "gomoku": _g("Gomoku", "⭕", 2, 2, "playgomoku", "Board", "five in a row wins", ambient=True, turn=40),
    "battleship": _g("Battleship", "🚢", 2, 2, "playbattle", "Board", "hunt down the hidden fleet", ambient=True, turn=30),
    "nim": _g("Nim", "🪨", 2, 2, "playnim", "Brain", "take the last stone", turn=30),
    # cards
    "uno": _g("UNO", "🃏", 2, 6, "playuno", "Cards", "match colours, play +4, be first out", ambient=True, turn=25),
    "teenpatti": _g("Teen Patti", "🎴", 2, 6, "playteenpatti", "Cards", "3-card poker: blind, chaal, show", ambient=True, turn=25),
    "blackjack": _g("Blackjack", "🂡", 2, 4, "playblackjack", "Cards", "beat the dealer to 21", ambient=True, turn=20),
    "highlow": _g("Higher or Lower", "⬆️", 2, 4, "playhighlow", "Cards", "guess the next card, first to 7", turn=15),
    # dice & luck
    "pig": _g("Pig Dice", "🐷", 2, 4, "playpig", "Casino", "push your luck, bank it before a 1", turn=20),
    "liars": _g("Liar's Dice", "🎰", 2, 4, "playliars", "Casino", "bid, bluff and call the liar", turn=25),
    # party & brain
    "mafia": _g("Mafia", "🕵️", 4, 10, "playmafia", "Party", "find the mafia before they find you", ambient=True, turn=35),
    "trivia": _g("Quiz Race", "❓", 2, 6, "playtrivia", "Party", "7 questions, fastest brain wins", ambient=True, turn=15),
    "scramble": _g("Word Scramble", "🔤", 2, 4, "playscramble", "Party", "unscramble the word first", turn=30),
    "mathduel": _g("Math Duel", "➗", 2, 4, "playmath", "Party", "solve it before they do", turn=20),
    "bulls": _g("Code Breaker", "🔐", 2, 4, "playbulls", "Brain", "crack the secret 4-digit code", turn=40),
    "hangman": _g("Hangman", "🪢", 2, 4, "playhangman", "Party", "guess the word letter by letter", turn=25),
    # action
    "boxing": _g("Boxing", "🥊", 2, 2, "playboxing", "Action", "jab, hook, block and knock them out", ambient=True, turn=15),
    "racing": _g("Turbo Race", "🏎", 2, 4, "playrace", "Action", "pick your gear, hit the nitro, win the race", ambient=True, turn=15),
    "adventure": _g("Adventure Quest", "🗺", 2, 4, "playadventure", "Action", "find the key, slay monsters, escape", ambient=True, turn=25),
    "arena": _g("Arena Shooter", "🔫", 2, 4, "playarena", "Action", "take cover and be the last one standing", ambient=True, turn=25),
    "tugwar": _g("Tug of War", "🪢", 2, 2, "playtug", "Quick", "tap tap tap! pull the rope", nobots=True, turn=12),
    "reaction": _g("Reaction Duel", "⚡", 2, 2, "playreact", "Quick", "tap the instant it turns green", nobots=True, turn=14),
}
