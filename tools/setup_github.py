#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键完成 GitHub 侧配置：建仓 -> 推送 -> 写 Secrets/Variables -> 触发工作流

用法（token 仅在内存使用，不写入文件）：
  python tools/setup_github.py --token <PAT> --owner zw193020 --repo tariff-monitor-4g \
      --smtp-host smtp.qq.com --smtp-port 465 --smtp-user x@qq.com --smtp-pass <授权码> \
      --mail-to x@qq.com --site-url https://xxx.app.workbuddy.host
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

try:
    from nacl import encoding, public
except ImportError:
    print("缺少 pynacl，请先 pip install pynacl")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"


def gh(method, path, token, data=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": "tariff-setup"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read().decode("utf-8")
            return r.status, (json.loads(b) if b else {})
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "ignore")
        try:
            b = json.loads(b)
        except Exception:
            pass
        return e.code, b


def git(*args):
    p = subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def enc(pub_b64, value):
    pk = public.PublicKey(pub_b64.encode(), encoding.Base64Encoder())
    return base64.b64encode(public.SealedBox(pk).encrypt(value.encode())).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--owner", default="zw193020")
    ap.add_argument("--repo", default="tariff-monitor-4g")
    ap.add_argument("--smtp-host", default="smtp.qq.com")
    ap.add_argument("--smtp-port", default="465")
    ap.add_argument("--smtp-user", required=True)
    ap.add_argument("--smtp-pass", required=True)
    ap.add_argument("--mail-to", required=True)
    ap.add_argument("--site-url", default="")
    ap.add_argument("--focus", default="hunan,guangdong,zhejiang")
    a = ap.parse_args()

    code, me = gh("GET", "/user", a.token)
    if code != 200:
        print("令牌无效:", me); sys.exit(1)
    print("已登录:", me.get("login"))

    code, info = gh("GET", "/repos/%s/%s" % (a.owner, a.repo), a.token)
    if code == 200:
        print("仓库已存在:", info.get("full_name"))
    else:
        code, info = gh("POST", "/user/repos", a.token, {
            "name": a.repo, "private": False, "auto_init": False,
            "description": "四家运营商资费监控（移动/联通/电信/广电）"})
        if code not in (200, 201):
            print("建仓失败:", info); sys.exit(1)
        print("已建仓:", info.get("full_name"))

    remote = "https://%s:%s@github.com/%s/%s.git" % (a.owner, a.token, a.owner, a.repo)
    if not os.path.exists(os.path.join(ROOT, ".git")):
        git("git", "init", "-b", "main")
        git("git", "config", "core.autocrlf", "false")
    git("git", "config", "user.name", a.owner)
    git("git", "config", "user.email", a.owner + "@users.noreply.github.com")
    git("git", "add", "-A")
    git("git", "commit", "-m", "init: 四家运营商资费监控")
    code, out = git("git", "push", "-u", remote, "main")
    if code != 0:
        print("推送失败:\n", out[-2000:]); sys.exit(1)
    print("代码已推送（含四家数据）")

    code, pk = gh("GET", "/repos/%s/%s/actions/secrets/public-key" % (a.owner, a.repo), a.token)
    if code != 200:
        print("取公钥失败:", pk); sys.exit(1)
    secrets = {
        "SMTP_HOST": a.smtp_host, "SMTP_PORT": a.smtp_port,
        "SMTP_USER": a.smtp_user, "SMTP_PASS": a.smtp_pass,
        "MAIL_TO": a.mail_to, "MAIL_FROM": a.smtp_user,
        "MAIL_FROM_NAME": "运营商资费监控",
    }
    for k, v in secrets.items():
        c, r = gh("PUT", "/repos/%s/%s/actions/secrets/%s" % (a.owner, a.repo, k), a.token,
                  {"encrypted_value": enc(pk["key"], v), "key_id": pk["key_id"]})
        print(("  OK  " if c in (200, 201, 204) else "  FAIL ") + k)

    variables = {"SITE_URL": a.site_url, "FOCUS_PROVS": a.focus, "FOCUS_SEC": "hunan"}
    for k, v in variables.items():
        if not v:
            continue
        c, _ = gh("GET", "/repos/%s/%s/actions/variables/%s" % (a.owner, a.repo, k), a.token)
        m = "PATCH" if c == 200 else "POST"
        c, r = gh(m, "/repos/%s/%s/actions/variables/%s" % (a.owner, a.repo, k), a.token,
                  {"name": k, "value": v})
        print(("  OK  " if c in (200, 201, 204) else "  FAIL ") + "变量 " + k)

    c, r = gh("POST", "/repos/%s/%s/actions/workflows/dingtalk-summary.yml/dispatches"
              % (a.owner, a.repo), a.token, {"ref": "main"})
    print("已触发汇总推送" if c in (200, 204) else "触发失败: %s" % r)
    print("\n完成：https://github.com/%s/%s/actions" % (a.owner, a.repo))


if __name__ == "__main__":
    main()
