# -*- coding: utf-8 -*-
"""请求签名器: 复现 jsguard ee()/signWithSiua 的请求规范化 + mtgsig 生成。

调用 sign_request() 得到带 mtgsig header 的最终请求 (url/header/data)。
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote

from . import _mtgsig
from . import _finger

# 与 jsguard F()/Y() 等价的 url 解析 (协议/主机/端口/路径/查询/哈希)
_URL_RE = re.compile(
    r"^(?:([A-Za-z]+):)?(/{0,3})([0-9.\-A-Za-z]+)(?::(\d+))?(?:/([^?#]*))?(?:\?([^#]*))?(?:#(.*))?$"
)


def _enc(s) -> str:
    """等价 JS encodeURIComponent 的额外转义 (jsguard Y)。"""
    return quote(str(s), safe="~!*'()-_.").replace("!", "%21").replace("'", "%27").replace(
        "(", "%28").replace(")", "%29").replace("*", "%2A")


def _parse_url(url: str):
    m = _URL_RE.match(url)
    if not m:
        return None
    proto, _, host, port, path, query, _hash = m.groups()
    pathname = "/" + (path or "")
    return {"protocol": proto or "", "host": host or "", "port": port, "pathname": pathname,
            "query": query or ""}


def _parse_query(qs: str, keep_empty: bool = False):
    """jsguard F(): 解析 query 为 [key, value] 对 (已 decode)。"""
    from urllib.parse import unquote
    out = []
    if not qs:
        return out
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            out.append([unquote(k.replace("+", " ")), unquote(v.replace("+", " "))])
        elif part:
            out.append([unquote(part.replace("+", " ")), "undefined" if keep_empty else ""])
    return out


def _push_obj(pairs, obj, keep_undefined=False):
    """jsguard q(): 把对象/数组展开成 [enc(k), enc(v)] 对。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v is None:
                pairs.append([_enc(k), "undefined" if keep_undefined else "null"])
            elif isinstance(v, (dict, list)):
                pairs.append([_enc(k), _enc(json.dumps(v, separators=(",", ":"), ensure_ascii=False))])
            else:
                pairs.append([_enc(k), _enc(v)])
    elif isinstance(obj, list):
        for k, v in obj:
            pairs.append([_enc(k), _enc(v)])


def _sort_pairs(pairs):
    """jsguard Q(): 先按 key 再按 value 排序。"""
    return sorted(pairs, key=lambda e: (e[0], e[1]))


def build_w(method: str, url: str, data, header: dict | None = None) -> bytes:
    """复现 ee() 里构造的待签名串 w。返回 encodeURIComponent 后的字节。"""
    header = header or {}
    method = method.upper()
    ct = ""
    for k, v in header.items():
        if k.lower() == "content-type":
            ct = str(v).lower()
    is_form = ct.startswith("application/x-www-form-urlencoded")

    info = _parse_url(url) or {"pathname": "/", "query": ""}
    pathname = info["pathname"]
    query_pairs = _parse_query(info["query"])

    h = []
    body = ""
    if method == "GET":
        if isinstance(data, dict) and data:
            _push_obj(h, data, keep_undefined=True)
            if query_pairs:
                extra = {}
                for k, v in _parse_query(info["query"], keep_empty=True):
                    if not (isinstance(data, dict) and k in data):
                        extra[k] = v
                _push_obj(h, extra, keep_undefined=True)
        else:
            _push_obj(h, query_pairs)
    else:
        _push_obj(h, query_pairs)
        if is_form:
            if isinstance(data, str):
                body = data
            elif isinstance(data, dict):
                parts = []
                for k, v in data.items():
                    if v is None:
                        parts.append([quote(str(k)), "undefined"])
                    else:
                        parts.append([quote(str(k)), quote(str(v))])
                body = "&".join("%s=%s" % (k, v) for k, v in parts)

    h = _sort_pairs(h)
    w = _mtgsig.W(method + " " + pathname + " " + "&".join("%s=%s" % (k, v) for k, v in h))
    if is_form:
        if body:
            w += _mtgsig.X(_mtgsig.W(body))
    else:
        if isinstance(data, str):
            w += _mtgsig.X(_mtgsig.W(data))
        elif data is not None:
            w += _mtgsig.X(_mtgsig.W(json.dumps(data, separators=(",", ":"), ensure_ascii=False)))
    return w


@dataclass
class Signer:
    """持有 jsguard 运行时状态 (Pc / siua / dfpId / appId)。"""

    app_id: str = "wxfdba1f3193621ebf"
    siua: str = ""                       # finger.i(); 为空则惰性生成
    dfp_id: str = ""                      # finger.d()
    env_flag: int = 6                     # zc.env (微信小程序真机默认 6)
    server_time_diff: int = 0             # finger.std()
    pc_b1: dict = field(default_factory=dict)
    pc_b2: str = ""                       # 页面路由
    _seq: int = 0

    def _ensure_siua(self):
        if not self.siua:
            local_id = _finger.build_local_id(int(time.time() * 1000), {})
            arr = _finger.build_dfp_array(self.app_id, local_id, int(time.time() * 1000), [None] * 42)
            self.siua = _finger.build_siua(arr)
        if not self.dfp_id:
            self.dfp_id = self.siua[4:]

    def sign(self, method: str, url: str, data=None, header: dict | None = None,
             now_ms: int | None = None) -> dict:
        """返回 {'url','header','data'} 的最终请求 (header 含 mtgsig)。"""
        self._ensure_siua()
        i = int(time.time() * 1000 if now_ms is None else now_ms) + self.server_time_diff
        self._seq += 1
        pc = {"b7": i // 1000, "b1": self.pc_b1, "b8": self._seq, "b2": self.pc_b2}
        pc_json = json.dumps(pc, separators=(",", ":"), ensure_ascii=False)
        w = build_w(method, url, data, header)
        sig = _mtgsig.sign(self.siua, i, self.env_flag, w, pc_json,
                           a3=self.dfp_id, a7=self.app_id)
        out_header = dict(header or {})
        out_header["mtgsig"] = json.dumps(sig, separators=(",", ":"), ensure_ascii=False)
        return {"url": url, "header": out_header, "data": data, "method": method.upper()}

    def sign_with_siua(self, options: dict, wx_ids: dict | None = None,
                       token: str | None = None, user_id: str | None = None) -> dict:
        """复现 @mtfe/weapp-safety-request addCommonParams + jsguard.signWithSiua。

        options: {'url','method','header','data'}。
        wx_ids: {'openId','openIdCipher'} 会作为 header 注入;
        token/user_id 会作为 header 'token'/'csecuserid' 注入。
        返回注入后的 options (含 header.mtgsig)。
        """
        opts = dict(options)
        header = dict(opts.get("header") or {})
        if wx_ids:
            if wx_ids.get("openId"):
                header.setdefault("openId", wx_ids["openId"])
            if wx_ids.get("openIdCipher"):
                header.setdefault("openIdCipher", wx_ids["openIdCipher"])
        if token:
            header.setdefault("token", token)
        if user_id:
            header.setdefault("csecuserid", user_id)
        opts["header"] = header
        signed = self.sign(opts.get("method", "GET"), opts["url"],
                           opts.get("data"), header)
        opts["header"] = signed["header"]
        opts["method"] = signed["method"]
        return opts
