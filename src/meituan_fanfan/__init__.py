# -*- coding: utf-8 -*-
"""美团返返小程序 纯协议实现 (零 adb / Frida / 真机 / RPC)。

AppID: wxfdba1f3193621ebf
模块:
  _vm        jsguard 自定义 VM (cb / rc4_prga / x_b64)
  _mtgsig    mtgsig 请求签名 (ee / signWithSiua)
  _finger    设备指纹 siua / dfpId / localId (finger.i/d)
  signer     请求规范化 + 签名器 Signer
  login      登录链路 (getWxIds / silentLogin / getMtInfo)
  api        业务接口客户端 (offsiteact /wmpact/*)
"""
from .signer import Signer, build_w
from .api import FanfanClient, UserState, API_URL, FRONTEND_FN, BASE_URL
from .login import LoginClient, LoginConfig

__all__ = [
    "Signer", "build_w",
    "FanfanClient", "UserState", "API_URL", "FRONTEND_FN", "BASE_URL",
    "LoginClient", "LoginConfig",
]

__version__ = "1.0.0"
