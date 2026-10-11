# -*- coding: utf-8 -*-
"""美团返返 纯协议全链路闭合示例 (YYB 铸码登录 + 业务接口)。

一条命令跑通:
  [0] YYB 会话铸原生 wx.login code
  [1] getWxIds      -> openId / unionId
  [2] silentLogin   -> token / userId
  [3] getMtInfo     -> 用户资料
  [4] 业务接口      -> 积分余额 / 任务列表 / 钱包 / 搜索历史 ...

运行:
  /root/Knight/.venv/bin/python examples/full_chain.py

前置: pcyyb 账号登录态需具备 snsapi_runtime_pcsdk scope。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meituan_fanfan import (LoginClient, LoginConfig, Signer, LoginError,
                            FanfanClient, UserState, try_get_wx_login_code)
from meituan_fanfan.api import STAGING_BASE_URL, BASE_URL

APP_ID = "wxfdba1f3193621ebf"
# 短指纹: 纯 Python 全量指纹会被 openresty WAF 403 (见 docs/YYB免密登录可行性.md)
SHORT_FP = "WX__ver1.2.0_TEST"


def main():
    use_prod = "--prod" in sys.argv
    base = BASE_URL if use_prod else STAGING_BASE_URL

    # [0] 铸码
    code, err = try_get_wx_login_code(APP_ID)
    if not code:
        print("[0] 铸码失败:", err)
        return
    print("[0] wx.login code =", code)

    cfg = LoginConfig(
        app_name="foodtaster", app_id=APP_ID,
        risk_app=348, risk_platform=13, risk_partner=845,
        token_id="tUGmSJ0I3ChAAhzf_pB1ug", joinkey="100441_2043809892",
        sdk_version="6.11.2", version_name="1.0.0",
        platform="windows", model="PC", wx_version="3.9.12", env="prod",
    )
    lc = LoginClient(cfg=cfg, signer=Signer(app_id=APP_ID))

    # [1] getWxIds
    try:
        wx_ids = lc.get_wx_ids(code)
    except LoginError as e:
        print("[1] getWxIds 失败:", e)
        return
    print("[1] wxIds =", wx_ids)

    # [2] silentLogin (再铸一次 code)
    code2, err2 = try_get_wx_login_code(APP_ID)
    if not code2:
        print("[2] 铸码失败:", err2)
        return
    try:
        res = lc.silent_login(code2, SHORT_FP)
    except LoginError as e:
        print("[2] silentLogin 失败: code=%s type=%s" % (e.code, e.type))
        return
    print("[2] token=%s userId=%s" % (str(res.get("token"))[:24] + "...", res.get("userId")))

    # [3] getMtInfo
    try:
        info = lc.get_mt_info()
        u = info or {}
        print("[3] mtInfo =", {k: u.get(k) for k in ("id", "username", "mobile")})
    except LoginError as e:
        print("[3] getMtInfo 失败:", e)

    # [4] 业务接口
    user = UserState(
        token=lc.auth.get("token"),
        user_id=str(res.get("userId") or ""),
        open_id=wx_ids.get("openId"),
        open_id_cipher=wx_ids.get("openIdCipher"),
        device_id="f3457391d7494fd4b52c6f7d09e6575f",
        latitude=39.9087, longitude=116.3975,
        app_version="1.0.0", csec_version_name="1.0.0",
    )
    cli = FanfanClient(signer=Signer(app_id=APP_ID), user=user, base_url=base)
    print("[4] base_url =", base)
    calls = [("fetchPointsBalance", None), ("fetchMissionList", None),
             ("fetchWalletBalance", None), ("getUserRole", None),
             ("fetchSearchList4Poi", {"biz": "SHANG_JIN_SEARCH", "count": 10}),
             ("queryDynamicRule", {"type": "1"})]
    for name, data in calls:
        try:
            r = cli.request(name, data=data)
        except Exception as e:
            r = {"error": str(e)[:80]}
        print("    %-24s -> %s" % (name, str(r)[:110]))


if __name__ == "__main__":
    main()
