"""Run local MathDoc server and open the browser after readiness."""
from __future__ import annotations
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

URL = 'http://127.0.0.1:8765'


def healthy() -> bool:
    try:
        with urllib.request.urlopen(URL + '/api/health', timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def open_browser() -> bool:
    try:
        if webbrowser.open(URL):
            return True
    except Exception:
        pass
    if hasattr(os, 'startfile'):
        try:
            os.startfile(URL)
            return True
        except Exception:
            pass
    try:
        subprocess.Popen(['cmd', '/c', 'start', '', URL])
        return True
    except Exception:
        return False


def main():
    if healthy():
        print('检测到服务已在运行，正在打开页面：', URL, flush=True)
        if not open_browser():
            print('无法自动打开浏览器，请手动访问：', URL, flush=True)
            input('按回车退出...')
        return

    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server:app',
                               '--host', '127.0.0.1', '--port', '8765'])
    try:
        for _ in range(60):
            if server.poll() is not None:
                raise RuntimeError('服务器启动失败，请检查 8765 端口是否被占用。')
            if healthy():
                break
            time.sleep(.3)
        else:
            raise RuntimeError('服务器未按预期启动。')
        print('MathDoc Studio 已启动：', URL, flush=True)
        if not open_browser():
            print('无法自动打开浏览器，请手动访问：', URL, flush=True)
        server.wait()
    except KeyboardInterrupt:
        print('正在关闭本地服务…')
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == '__main__':
    main()
