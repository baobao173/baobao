# 猜数字游戏

程序随机选取 1～100 之间的整数。输入猜测后，程序提示偏大或偏小，猜中时显示有效猜测次数。非整数和超范围输入不计次数。

## 运行

在本目录执行，无需安装第三方库：

```bash
python guess_number.py
```

按 `Ctrl+C` 退出。

## 测试

```bash
python -m unittest test_guess_number -v
```

`check_guess()` 负责比较数字，`play()` 负责输入和提示。代码采用仓库根目录的 [MIT 许可](../LICENSE)。
