# -*- coding: utf-8 -*-
"""guess_number 核心逻辑的单元测试（使用 Python 内置 unittest，无需安装依赖）。"""

import unittest

from guess_number import check_guess, MAX_NUMBER, MIN_NUMBER


class CheckGuessTest(unittest.TestCase):
    def test_guess_too_low(self):
        self.assertEqual(check_guess(secret=50, guess=10), "too_low")

    def test_guess_too_high(self):
        self.assertEqual(check_guess(secret=50, guess=80), "too_high")

    def test_guess_correct(self):
        self.assertEqual(check_guess(secret=50, guess=50), "correct")

    def test_guess_at_lower_bound(self):
        self.assertEqual(check_guess(secret=MIN_NUMBER, guess=MIN_NUMBER), "correct")

    def test_guess_at_upper_bound(self):
        self.assertEqual(check_guess(secret=MAX_NUMBER, guess=MAX_NUMBER), "correct")


if __name__ == "__main__":
    unittest.main()
