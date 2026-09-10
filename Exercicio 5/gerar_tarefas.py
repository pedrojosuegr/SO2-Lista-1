import random
import sys


def main():
    quantidade = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    semente = int(sys.argv[2]) if len(sys.argv) > 2 else None
    rng = random.Random(semente)
    for _ in range(quantidade):
        if rng.random() < 0.5:
            print(f"primo {rng.randrange(10**9, 10**11)}")
        else:
            print(f"fib {rng.randrange(1000, 20000)}")


if __name__ == "__main__":
    main()
