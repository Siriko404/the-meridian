from social_roulette.sim.random_agent import play_game


def measure_baseline(n=5000, num_players=5):
    wins = sum(1 for seed in range(n) if play_game(num_players, seed)["winner"] == 0)
    return wins / n


def main():
    wr = measure_baseline()
    print(f"random id-0 win-rate over 5000 games = {wr:.4f}  (chance = {1/5:.4f})")


if __name__ == "__main__":
    main()
