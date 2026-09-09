# 猜数字游戏（guess-number）

最基础的 Python 入门小项目：程序在 1~100 之间随机选一个数，
玩家在终端里不断输入猜测，直到猜中为止。

## 运行游戏

```bash
python guess_number.py
```

示例：

```
我已想好一个 1~100 之间的数字，开始猜吧！
请输入你的猜测：50
太小了，再大一点！
请输入你的猜测：75
太大了，再小一点！
请输入你的猜测：63
恭喜你！猜对了，答案是 63，共用了 3 次。
```

## 运行测试

```bash
python -m unittest test_guess_number -v
```

## 学习要点

- `random.randint` 生成随机数
- `input()` / `print()` 与用户交互
- `while` 循环、`try/except` 处理非法输入
- 把核心比较逻辑 `check_guess()` 与输入输出分离，便于单元测试

## 许可证

本项目采用 [MIT License](../LICENSE)，版权人 baobao173。
