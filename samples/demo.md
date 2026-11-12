# 学术公式转换演示

## 一、研究方法

设 $\mathbf{x}\in\mathbb{R}^d$，目标为最小化目标损失：

$$
\mathcal{L}_{\mathrm{total}} = \frac{1}{n}\sum_{i=1}^{n}\left(y_i - f_{\theta}(x_i)\right)^2 + \lambda\lVert\theta\rVert_2^2
$$

其中 $\lambda > 0$ 表示正则化系数。

## 二、复杂数学结构

$$
A=\begin{bmatrix}a&b\\c&d\end{bmatrix}
$$

$$
f(x)=\begin{cases}x^2,&x\ge0\\-x,&x<0\end{cases}
$$

## 三、实验对比（演示数据）

| 方案 | Accuracy ↑ | MAE ↓ |
|:---|---:|---:|
| Baseline | 0.81 | 0.62 |
| Proposed | **0.83** | **0.59** |

*以上数字仅用于演示，不代表真实实验结论。*
