# MathDoc Studio — 本轮验证报告

验证环境：本地 Linux 容器、Pandoc 3.1.11.1、FastAPI、Chromium（浏览器函数模拟后端）、LibreOffice。

## 已执行

1. `python -m pytest -q tests/test_app.py`：6/6 通过，覆盖 Markdown→MathML、公式数目、Word OMML、表格 AST、防范危险 HTML/本地图片、模拟 OpenAI-compatible 模型响应。
2. `python mathdoc_cli.py convert samples/demo.md -o output.docx`：源文档 5 个数学公式，生成 DOCX 5 个 OMML `m:oMath` 节点。
3. `python mathdoc_cli.py audit output.docx`：正确回报 5。
4. LibreOffice 打开 `samples/example_output.docx` 渲染一页 PNG，人工检查常用数学公式（含分数、上下标、矩阵、分段函数）、中文标题与三列表格，可视结果正常。最初用空白 python-docx 生成 reference.docx 导致表格错乱，已改用 Pandoc 原生参考文档为基底重新生成并复验。
5. Chromium 页面载入和按钮基础交互：成功展示左右分栏，按模拟后端返回生成的文档预览，输出 6 条 MathML 公式；设置弹窗和 DeepSeek 服务商切换工作正常，未发现 JavaScript 页面异常。

## 尚未验证 / 不作保证

- 未用真实 OpenAI / DeepSeek API Key 进行网络调用；已验证请求协议和模拟响应。
- 未在用户 Windows Microsoft Word 或 WPS 上完成剪贴板粘贴测试。浏览器富文本复制中 MathML 是否变成可编辑公式依赖目标 Word 版本，**不能承诺**。
- 没有验证专有 MathType OLE 对象生成，现版本只提供 LaTeX / MathML 交换形式。
- OMML 数量等于源公式数量不证明数学语义等价，复杂 LaTeX 宏、公式编号、图片和交叉引用需要独立验收。
- 当前为本地单机工具，未进行公网暴露/多用户安全评估。

## 推荐 Windows 验收

下载 ZIP → 安装 Pandoc 和 Python → 双击 `start_windows.bat` → 加载示例 → 直接排版 → 导出 DOCX → 在 Word 打开并双击检查每条原生公式 → 复制富文本到目标 Word 空文档比较 → 用 MathType 模式逐条复制 LaTeX 检查输入。
