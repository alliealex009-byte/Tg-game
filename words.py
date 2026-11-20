"""Hangman word list: category -> words (lowercase letters only)."""
WORDS = {
    "Animals": "elephant giraffe penguin dolphin kangaroo crocodile butterfly squirrel hedgehog octopus leopard buffalo peacock flamingo cheetah gorilla panther rabbit turtle jaguar lobster sparrow monkey camel zebra falcon beaver walrus parrot".split(),
    "Food": "pizza burger noodles pancake sandwich chocolate pineapple strawberry avocado broccoli spaghetti biscuit cheese coconut mushroom cabbage popcorn pudding mango pepper cucumber almond waffle cookie lemon yogurt tomato banana".split(),
    "Countries": "india canada brazil germany france japan egypt mexico norway sweden italy spain turkey kenya nepal poland ireland greece russia vietnam portugal argentina thailand finland denmark morocco".split(),
    "Sports": "cricket football hockey tennis cycling swimming boxing archery wrestling baseball badminton volleyball rugby skating surfing karate skiing bowling golf netball diving sailing rowing fencing".split(),
    "Nature": "mountain river forest desert island volcano glacier rainbow thunder waterfall ocean meadow canyon lagoon jungle sunrise tornado blizzard valley cliff swamp".split(),
    "Tech": "keyboard internet software browser battery printer network monitor database laptop router pixel server website android program wireless camera speaker charger password".split(),
    "Things": "umbrella backpack bicycle mirror pillow blanket lantern compass hammer ladder candle window bottle scissors trophy balloon wallet guitar piano telescope suitcase clock".split(),
    "Jobs": "doctor teacher pilot farmer engineer painter chef dentist pilot driver singer actor lawyer plumber tailor baker officer writer fireman scientist".split(),
}
for _c in WORDS:
    WORDS[_c] = sorted(set(WORDS[_c]))
ALL_WORDS = [(c, w) for c, ws in WORDS.items() for w in ws]
