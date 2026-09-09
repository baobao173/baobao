# -*- coding: utf-8 -*-
"""猜数字游戏：程序在 1~100 之间随机选一个数，玩家不断猜测直到猜中。"""

import random

MIN_NUMBER = 1
MAX_NUMBER = 100


def check_guess(secret: int, guess: int) -> str:
    """比较猜测值与秘密数字，返回 'too_low' / 'too_high' / 'correct'。"""
    if guess < secret:
        return "too_low"
    if guess > secret:
        return "too_high"
    return "correct"


def play(secret: int) -> int:
    """在终端里玩一局猜数字，返回用掉的猜测次数。

    提示文本由 guess 的返回值决定：太小提示“太小了”，
    太大提示“太大了”，猜中则结束游戏。
    """
    hints = {
        "too_low": "太小了，再大一点！",
        "too_high": "太大了，再小一点！",
    }
    print(f"我已想好一个 {MIN_NUMBER}~{MAX_NUMBER} 之间的数字，开始猜吧！")

    attempts = 0
    while True:
        try:
            guess = int(input("请输入你的猜测："))
        except ValueError:
            print("请输入一个整数。")
            continue

        if guess < MIN_NUMBER or guess > MAX_NUMBER:
            print(f"请输入 {MIN_NUMBER}~{MAX_NUMBER} 之间的整数。")
            continue

        attempts += 1
        result = check_guess(secret, guess)
        if result == "correct":
            print(f"恭喜你！猜对了，答案是 {secret}，共用了 {attempts} 次。")
            return attempts
        print(hints[result])


def main() -> None:
    secret = random.randint(MIN_NUMBER, MAX_NUMBER)
    play(secret)


if __name__ == "__main__":
    main()
