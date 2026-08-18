"""公文写作工作室 · 桌面应用启动器

内嵌 FastAPI 后端（后台线程）+ 系统 WebView 窗口（pywebview）。
应用窗口内 Ctrl+Shift+K 快捷键稳定生效（不受浏览器标签页/插件干扰）。

用法：
    pip install pywebview
    python desktop.py
"""
import threading

import uvicorn


def _run_server():
    uvicorn.run("writer_studio.backend.main:app", host="127.0.0.1", port=8000, log_level="warning")


def main():
    threading.Thread(target=_run_server, daemon=True).start()
    import webview
    webview.create_window(
        "公文写作工作室",
        "http://127.0.0.1:8000",
        width=1440, height=900,
        min_size=(1100, 700),
    )
    webview.start()


if __name__ == "__main__":
    main()
