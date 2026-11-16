# -*- coding: utf-8 -*-
"""v2.2 训练监控上报器（云端运行）：把 t22f.log 推到 GitHub Gist，供本地轮询。
用法：python3 /root/up_gist.py <GITHUB_TOKEN> （由外层 while 循环每 120 秒调一次）"""
import json, sys, urllib.request

GIST_ID = "e9d19ad1d85e12a7f52c8cca2a6d2419"
LOG = "/root/autodl-tmp/t22f.log"

if len(sys.argv) < 2:
    print("usage: python3 up_gist.py <TOKEN>")
    sys.exit(1)
TOKEN = sys.argv[1]

try:
    try:
        content = open(LOG, encoding="utf-8", errors="replace").read()[-80000:]
    except FileNotFoundError:
        content = "LOG_NOT_FOUND"
    body = json.dumps({"files": {"t22f.log": {"content": content or "empty"}}}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}", data=body,
        headers={"Authorization": f"token {TOKEN}", "Content-Type": "application/json"},
        method="PATCH")
    urllib.request.urlopen(req, timeout=30)
    print("pushed OK", flush=True)
except Exception as e:
    print("push fail:", repr(e), flush=True)
