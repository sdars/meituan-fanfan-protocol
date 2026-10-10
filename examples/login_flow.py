# -*- coding: utf-8 -*-
"""登录链路示例 (纯协议, 零 adb/Frida/真机)。

唯一外部输入: code —— 来自真实微信环境的 wx.login。
wechatFingerprint 由 _finger.build_wechat_fingerprint 纯 Python 生成。

运行:
  /root/Knight/.venv/bin/python examples/login_flow.py <wx.login code>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meituan_fanfan import LoginClient, LoginConfig  # noqa: E402
from meituan_fanfan import _finger  # noqa: E402


def build_fingerprint(app_id="wxfdba1f3193621ebf", system=None, session_id=None):
    """构造登录用 wechatFingerprint (finger.g 等价)。"""
    import time
    ts = int(time.time() * 1000)
    local_id = _finger.build_local_id(ts, system or {})
    return _finger.build_wechat_fingerprint(
        system or {}, appid=app_id, dfpid=local_id, local_id=local_id,
        ts=ts, session_id=session_id)


def main():
    if len(sys.argv) < 2:
        print("用法: python examples/login_flow.py <wx.login code>")
        return
    code = sys.argv[1]
    cfg = LoginConfig(model="iPhone 13", platform="iphone", wx_version="8.0.40")
    client = LoginClient(cfg)
    fp = build_fingerprint(app_id=cfg.app_id)
    print("[*] wechatFingerprint:", fp[:60], "...")
    result = client.login(code=code, wechat_fingerprint=fp)
    print("[+] token:", result.get("token"))
    print("[+] userId:", result.get("userId"))
    print("[+] openId:", result.get("openId"))


if __name__ == "__main__":
    main()
