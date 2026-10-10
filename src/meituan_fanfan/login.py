# -*- coding: utf-8 -*-
"""美团账号登录链路纯协议复现 (copy/account/account-core)。

链路 (silentLogin):
  1. getWxIds(code):  POST open.meituan.com/user/thirdinfo/getweappuserinfo
                       form {code, appName}  -> {openId, openIdCipher, unionId}
  2. silentLogin:     POST open.meituan.com/user/v1/weappsilentlogin
                       form {wechatFingerprint, code}
                       -> {token, userId, openId, openIdCipher, unionId, ...}
  3. getMtInfo:       GET  open.meituan.com/user/v1/info?token=&fields=...

请求包装 (re):
  - url 经 te() 追加 sdkVersion/utm_medium/joinkey/sdkType=wxmp/login_sdk_version/
    appName/risk_*/version_name/token_id/uuid 等 query 参数;
  - data 合并 device_type(=model)/device_os="微信小程序";
  - 再经 jsguard.signWithSiua 注入 header.mtgsig。

红线: 唯一需要外部输入的是 wx.login 的 code (真实微信环境);
      wechatFingerprint 由 finger.g() 纯 Python 生成, 无 adb/Frida/RPC。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests

from .signer import Signer

PROD_DOMAIN = "open.meituan.com"
TEST_DOMAIN = "open.wpt.test.sankuai.com"

PATHS = {
    "getmtuserinfo": "/user/v1/info",
    "getwxinfo": "/user/thirdinfo/getweappuserinfo",
    "getwxuserinfo": "/user/thirdinfo/getwechatuserinfo",
    "updatemtuserinfo": "/user/settings",
    "wxmobilelogin": "/user/v2/weappgetmobilelogin",
    "wxbindapply": "/user/v2/weappbindmobileloginapply",
    "wxbind": "/user/v2/weappbindmobilelogin",
    "wxslientlogin": "/user/v1/weappsilentlogin",
    "logout": "/thirdlogin/wechatapplogout",
    "generateticket": "/thirdlogin/user/h5/sharelogin/generateTicket",
}

GET_MT_INFO_FIELDS = ["id", "username", "avatarurl", "avatartype", "mobile",
                      "city", "cityid", "nickname"]


@dataclass
class LoginConfig:
    """来自 app/contants.js + account SDK init 的常量。"""

    app_name: str = "foodtaster"
    app_id: str = "wxfdba1f3193621ebf"
    risk_app: int = 348
    risk_platform: int = 13          # RistPlatform
    risk_partner: int = 845          # RistPartner
    token_id: str = "tUGmSJ0I3ChAAhzf_pB1ug"
    joinkey: str = "100441_2043809892"
    sdk_version: str = "6.11.2"
    # 设备相关 (真机由 wx.getSystemInfoSync 提供)
    wx_version: str = ""             # wx.version -> sdkVersion query
    platform: str = ""               # "iphone"/"android"/"devtools" -> utm_medium
    model: str = ""                  # device_type
    version_name: str = "1.0.0"      # 小程序版本
    uuid: str = ""                   # lxcuid
    env: str = "prod"                # prod | test

    @property
    def domain(self) -> str:
        return PROD_DOMAIN if self.env == "prod" else TEST_DOMAIN


def _te(url: str, cfg: LoginConfig) -> str:
    """account-core te(): 追加签名相关 query 参数 (仅非 null 值)。"""
    params = {
        "sdkVersion": cfg.wx_version,
        "utm_medium": cfg.platform,
        "joinkey": cfg.joinkey,
        "sdkType": "wxmp",
        "login_sdk_version": cfg.sdk_version,
        "appName": cfg.app_name,
        "risk_app": cfg.risk_app,
        "risk_partner": cfg.risk_partner,
        "risk_platform": cfg.risk_platform,
        "version_name": cfg.version_name,
        "token_id": cfg.token_id,
        "uuid": cfg.uuid,
    }
    pairs = ["%s=%s" % (quote(str(k), safe=""), quote(str(v), safe=""))
             for k, v in params.items() if v is not None and v != ""]
    if not pairs:
        return url
    return url + ("&" if "?" in url else "?") + "&".join(pairs)


class LoginClient:
    def __init__(self, cfg: LoginConfig | None = None, signer: Signer | None = None,
                 session: requests.Session | None = None):
        self.cfg = cfg or LoginConfig()
        self.signer = signer or Signer(app_id=self.cfg.app_id)
        self.http = session or requests.Session()
        # 登录态缓存
        self.auth: dict = {}       # {userId, token}
        self.wx_ids: dict = {}     # {openId, openIdCipher, unionId}
        self.mt_info: dict = {}

    # --- 请求包装 re() ---------------------------------------------------------
    def _re(self, path: str, data: dict | None = None, method: str = "POST",
            header: dict | None = None, enable_body_token: bool = False) -> dict:
        url = "https://" + self.cfg.domain + path
        url = _te(url, self.cfg)
        body = dict(data or {})
        if enable_body_token:
            body["token"] = self.auth.get("token")
        body["device_type"] = self.cfg.model
        body["device_os"] = "微信小程序"
        h = dict(header or {})
        signed = self.signer.sign(method, url, body, h)
        if signed["method"].upper() == "GET":
            # wx.request GET: data 追加到 query (签名仍用 te() 后的原始 url)
            params = {k: v for k, v in body.items() if v is not None}
            req = self.http.request("GET", signed["url"], headers=signed["header"], params=params)
        else:
            req = self.http.request(signed["method"], signed["url"], headers=signed["header"],
                                    data=json.dumps(signed["data"], ensure_ascii=False).encode("utf-8"))
        try:
            return req.json()
        except Exception:
            return {"statusCode": req.status_code, "text": req.text}

    def _re_form(self, path: str, data: dict, method: str = "POST") -> dict:
        """表单请求 (ke/silentLogin 用的 header=we: x-www-form-urlencoded)。"""
        url = _te("https://" + self.cfg.domain + path, self.cfg)
        body = dict(data)
        body["device_type"] = self.cfg.model
        body["device_os"] = "微信小程序"
        header = {"content-type": "application/x-www-form-urlencoded"}
        signed = self.signer.sign(method, url, body, header)
        req = self.http.request(signed["method"], signed["url"],
                                headers=signed["header"],
                                data="&".join("%s=%s" % (quote(str(k), safe=""), quote(str(v), safe=""))
                                              for k, v in signed["data"].items()))
        try:
            return req.json()
        except Exception:
            return {"statusCode": req.status_code, "text": req.text}

    # --- 业务链路 --------------------------------------------------------------
    def get_wx_ids(self, code: str) -> dict:
        """ke(): wx.login code -> {openId, openIdCipher, unionId}。"""
        resp = self._re_form(PATHS["getwxinfo"], {"code": code, "appName": self.cfg.app_name})
        openid = resp.get("openid") or resp.get("openId")
        openid_cipher = resp.get("openidCipher") or resp.get("openIdCipher")
        unionid = resp.get("unionid") or resp.get("unionId")
        unionid_cipher = resp.get("unionIdCipher")
        if openid and openid_cipher and unionid:
            self.wx_ids = {"openId": openid, "openIdCipher": openid_cipher, "unionId": unionid}
            if unionid_cipher:
                self.wx_ids["unionIdCipher"] = unionid_cipher
            return self.wx_ids
        raise RuntimeError("getwxinfo 失败: %s" % json.dumps(resp, ensure_ascii=False))

    def silent_login(self, code: str, wechat_fingerprint: str) -> dict:
        """silentLogin(): POST wxslientlogin {wechatFingerprint, code}。

        成功且返回 token/userId 时写入 self.auth。
        """
        resp = self._re_form(PATHS["wxslientlogin"],
                             {"wechatFingerprint": wechat_fingerprint, "code": code})
        openid = resp.get("openId") or resp.get("openid")
        unionid = resp.get("unionId") or resp.get("unionid")
        data = resp.get("data") or {}
        merged = {"openId": openid, "unionId": unionid,
                  "openIdCipher": resp.get("openIdCipher"), **(data if isinstance(data, dict) else {})}
        if resp.get("unionIdCipher"):
            merged["unionIdCipher"] = resp["unionIdCipher"]
        if not openid and not unionid:
            raise RuntimeError("weappsilentlogin 失败: %s" % json.dumps(resp, ensure_ascii=False))
        if merged.get("token") and merged.get("userId"):
            self.auth = {"userId": merged["userId"], "token": merged["token"]}
            if openid:
                self.wx_ids = {k: v for k, v in merged.items()
                               if k in ("openId", "openIdCipher", "unionId", "unionIdCipher")}
        return merged

    def get_mt_info(self, token: str | None = None) -> dict:
        """Ie(): GET getmtuserinfo?token=&fields=...。"""
        tok = token or self.auth.get("token")
        q = "token=%s&fields=%s" % (quote(str(tok), safe=""), quote(",".join(GET_MT_INFO_FIELDS), safe=""))
        resp = self._re(PATHS["getmtuserinfo"] + "?" + q, data={}, method="GET")
        user = (resp or {}).get("user") or {}
        if user.get("id"):
            self.mt_info = {k: user.get(k) for k in
                            ("id", "username", "avatarurl", "mobile", "city", "cityid", "nickname")}
            return self.mt_info
        raise RuntimeError("getmtuserinfo 失败: %s" % json.dumps(resp, ensure_ascii=False))

    def login(self, code: str, wechat_fingerprint: str, fetch_mt_info: bool = True) -> dict:
        """完整静默登录: getWxIds -> silentLogin -> (可选) getMtInfo。"""
        self.get_wx_ids(code)
        result = self.silent_login(code, wechat_fingerprint)
        if fetch_mt_info and self.auth.get("token"):
            try:
                result["mtInfo"] = self.get_mt_info()
            except Exception as e:  # noqa: BLE001
                result["mtInfoError"] = str(e)
        return result
