import statistics

from social_roulette.sim.random_agent import play_game


def main(games=2000):
    turns = []
    winners = {}
    for seed in range(games):
        n = 5 + (seed % 6)
        res = play_game(n, seed)
        assert res["winner"] is not None
        turns.append(res["turns"])
        winners[res["winner"]] = winners.get(res["winner"], 0) + 1
    print(f"games={games} mean={statistics.mean(turns):.1f} median={statistics.median(turns)} max={max(turns)}")
    print("winner-by-seat:", dict(sorted(winners.items())))


if __name__ == "__main__":
    main()
