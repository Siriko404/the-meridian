import random


class SeededRng:
    def __init__(self, seed):
        self._r = random.Random(seed)

    def roll_two_dice(self):
        return (self._r.randint(1, 6), self._r.randint(1, 6))

    def shuffle(self, seq):
        self._r.shuffle(seq)

    def choice(self, seq):
        return self._r.choice(seq)

    def randint(self, a, b):
        return self._r.randint(a, b)
