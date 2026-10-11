# -*- coding: utf-8 -*-
"""YYB (应用宝电脑版) 微信会话 -> 原生 wx.login code 铸码桥接。

背景 (详见 docs/YYB免密登录可行性.md):
  美团 silentLogin 的 code 必须是目标小程序 appid 的「原生 wx.login code」。
  YYB 授权接口 [A] pcyyb_get_wx_login_code 对美团 appid 返回 -109 (白名单外),
  但 YYB 登录态可换取「微信平台授权 buffer」, 再用 qqfarm 的 MMTLS/ShortLink
  铸码实现, 在纯协议环境里铸出原生 wx.login code (按目标 appid 绑定)。

依赖 (软):
  - /root/YYB/pcyyb/protocol   (SessionStore)
  - /root/YYB/qqfarm/src       (getNativeWxLoginCode)
任一缺失时抛 YybUnavailable, 不静默。

红线: 不修改 pcyyb / qqfarm 仓库, 仅通过其公开 API 调用。
"""
from __future__ import annotations

import os
import sys

PCYYB_DIR = os.environ.get("PCYYB_PROTOCOL_DIR", "/root/YYB/pcyyb/protocol")
QQFARM_SRC = os.environ.get("QQFARM_SRC_DIR", "/root/YYB/qqfarm/src")
DEFAULT_ACCOUNT = os.environ.get(
    "MEITUAN_FANFAN_ACCOUNT",
    os.path.join(PCYYB_DIR, "accounts", "owNAX6txE4vcGLryGW-ptHb5JrcY.json"),
)
DEFAULT_APP_ID = "wxfdba1f3193621ebf"


class YybUnavailable(RuntimeError):
    """pcyyb / qqfarm 依赖不可用。"""


def _load_deps():
    """惰性导入 pcyyb + qqfarm, 返回 (SessionStore, getNativeWxLoginCode)。"""
    for p in (PCYYB_DIR, QQFARM_SRC):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from session_keepalive import SessionStore          # type: ignore
        from qqfarm import getNativeWxLoginCode             # type: ignore
    except Exception as e:  # noqa: BLE001
        raise YybUnavailable(
            "无法导入 pcyyb/qqfarm 依赖 (%s): %s\n"
            "  PCYYB_PROTOCOL_DIR=%s\n  QQFARM_SRC_DIR=%s"
            % (type(e).__name__, e, PCYYB_DIR, QQFARM_SRC)
        ) from e
    return SessionStore, getNativeWxLoginCode


def get_wx_login_code(app_id: str = DEFAULT_APP_ID,
                      account_path: str | None = None,
                      refresh: bool = True,
                      store=None):
    """用 YYB 微信会话铸出目标小程序的「原生 wx.login code」。

    链路: SessionStore.load(account) -> (可选 refresh) -> authorize_buffer()
          -> getNativeWxLoginCode(buffer, app_id) -> code

    code 单次有效: 每个需要 code 的接口 (getWxIds / silentLogin) 都要各铸一次。

    返回:
        code (str) 成功; 依赖缺失/铸码失败时抛 YybUnavailable / 底层异常。
    """
    SessionStore, getNativeWxLoginCode = _load_deps()
    st = store or SessionStore.load(account_path or DEFAULT_ACCOUNT)
    if refresh and st.need_refresh():
        st.refresh()
    buf = st.authorize_buffer()["raw"]
    return getNativeWxLoginCode(buf, app_id)


def try_get_wx_login_code(app_id: str = DEFAULT_APP_ID, **kw):
    """get_wx_login_code 的安全版: 失败返回 (None, 原因字符串), 不抛异常。"""
    try:
        return get_wx_login_code(app_id=app_id, **kw), None
    except Exception as e:  # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)


__all__ = ["get_wx_login_code", "try_get_wx_login_code", "YybUnavailable",
           "DEFAULT_ACCOUNT", "DEFAULT_APP_ID", "PCYYB_DIR", "QQFARM_SRC"]
