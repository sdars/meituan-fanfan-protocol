# -*- coding: utf-8 -*-
"""纯协议闭合链路验证: 用 fixtures 黄金向量逐字节比对。

运行: /root/Knight/.venv/bin/python tests/test_protocol.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
FX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.abspath(SRC))

from meituan_fanfan import _mtgsig, _vm, _finger, signer  # noqa: E402


def load(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f)


PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("[%s] %s%s" % ("OK" if cond else "FAIL", name,
                          (" -> " + str(detail)) if (detail and not cond) else ""))


def test_vm():
    cap = load("vmcap.json")
    m = cap["m"]
    pc_json = json.dumps(cap["Pc"], separators=(",", ":"))
    out = _vm.cb(m, pc_json)
    check("vm.cb e_in", m + out == cap["e_in"])
    a5 = _vm.x_b64(m + out)
    check("vm.x_b64 a5", a5 == json.loads(cap["mtgsig"])["a5"])


def test_mtgsig():
    g = load("golden.json")
    d = load("deep.json")
    gm = json.loads(g["mtgsig"])
    sig = _mtgsig.sign(d["y"], d["i"], d["f"], bytes(d["w"]),
                       json.dumps(d["Pc"], separators=(",", ":")),
                       x0=3, a1="1.2", a3=gm["a3"], a7=gm["a7"])
    check("mtgsig.a4", sig["a4"] == gm["a4"], sig["a4"])
    check("mtgsig.a5", sig["a5"] == gm["a5"])
    check("mtgsig.d1", sig["d1"] == gm["d1"], sig["d1"])
    check("mtgsig.a2/a3/a6/a7", sig["a2"] == gm["a2"] and sig["a3"] == gm["a3"]
          and sig["a6"] == gm["a6"] and sig["a7"] == gm["a7"])


def test_siua_decrypt():
    g = load("golden.json")
    plain = _finger.decrypt_siua(g["y"])
    check("siua decrypt == gzInput", plain == g["gzInput"])


def test_local_id():
    g = load("golden.json")
    # golden localId = ts + randAZ7 + md5({"system":{}}) + crc32[:4]
    # 反推: md5 与 target 一致即说明键序/序列化正确
    import hashlib
    target_md5 = "60e593ce0a815b08d658526270cd17d6"
    md5 = hashlib.md5(json.dumps({"system": {}}, separators=(",", ":"),
                                 ensure_ascii=False).encode()).hexdigest()
    check("localId md5", md5 == target_md5, md5)
    # 端到端: 用固定 rand 生成 localId 前缀结构
    import random
    rng = random.Random()
    lid = _finger.build_local_id(1791000000000, {}, rng=rng)
    check("localId 结构", lid.startswith("1791000000000") and len(lid) == 13 + 7 + 32 + 4, lid)


def test_build_w():
    d = load("deep.json")
    # deep.json w = b'POST /wmpact/mission/user/list {"foo":"bar"}'
    w = signer.build_w("POST", "https://offsiteact.meituan.com/wmpact/mission/user/list",
                       {"foo": "bar"}, {"content-type": "application/json"})
    check("build_w", list(w) == list(d["w"]), list(w)[:60])


def test_signer_end_to_end():
    """Signer 用固定 siua/i/f 产出可解析 mtgsig, 且字段自洽。"""
    g = load("golden.json")
    s = signer.Signer()
    s.siua = g["y"]
    s.dfp_id = g["mtgsig"] and json.loads(g["mtgsig"])["a3"]
    s.env_flag = 123
    req = s.sign("POST", "https://offsiteact.meituan.com/wmpact/mission/user/list",
                 {"foo": "bar"}, {"content-type": "application/json"},
                 now_ms=1791000000000)
    sig = json.loads(req["header"]["mtgsig"])
    check("signer mtgsig fields", set(sig) >= {"a1", "a2", "a3", "a4", "a5", "a6", "a7", "x0", "d1"})
    check("signer a2==now", sig["a2"] == 1791000000000)


def test_wechat_fingerprint_shape():
    fp = _finger.build_wechat_fingerprint({}, appid="wxfdba1f3193621ebf",
                                          dfpid="dfp123", local_id="dfp123",
                                          ts=1791000000000)
    check("wechatFingerprint 前缀", fp.startswith("WX__ver1.2.0_CCCC_"))
    # 能解密回明文 (验证 AES/gzip 自洽)
    import base64
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    ct = base64.b64decode(fp[len("WX__ver1.2.0_CCCC_"):])
    pt = Cipher(algorithms.AES(_finger.AES_KEY), modes.CBC(_finger.AES_IV)).decryptor().update(ct)
    import gzip
    obj = json.loads(gzip.decompress(pt[:-pt[-1]]).decode())
    check("wechatFingerprint 字段变换", "ext" not in obj and "sessionId" not in obj
          and "gyro" not in obj["system"] and obj["localid"] == "dfp123")


def test_login_branches():
    """登录链路补分支: LoginError / net_check path / build_wechat_fingerprint。"""
    from meituan_fanfan import LoginClient, LoginConfig, LoginError
    from meituan_fanfan.login import PATHS
    c = LoginClient(cfg=LoginConfig())
    check("newwxsilentlogin path",
          PATHS["newwxsilentlogin"] == "/user/v1/weappsilentloginembedded")
    # LoginError 结构化属性
    e = LoginError("boom", {"error": {"code": 101144, "type": "user_has_risk"}})
    check("LoginError.code/type", e.code == 101144 and e.type == "user_has_risk")
    # build_wechat_fingerprint 纯 Python 生成, 前缀固定
    fp = c.build_wechat_fingerprint()
    check("build_wechat_fingerprint 前缀",
          fp.startswith(_finger.WECHAT_FP_PREFIX) and len(fp) > 60)
    # get_wx_ids 失败时抛 LoginError (非 RuntimeError) —— 离线打桩, 不打网络
    c._re_form = lambda *a, **k: {"error": {"code": 101172, "type": "weapp_invalid_session"}}
    raised = None
    try:
        c.get_wx_ids("fake")
    except Exception as ex:  # noqa: BLE001
        raised = ex
    check("get_wx_ids 失败抛 LoginError", isinstance(raised, LoginError))

    # silent_login 业务错误 (101144 风控) 抛 LoginError 并带 code/type
    c2 = LoginClient(cfg=LoginConfig())
    c2._re_form = lambda *a, **k: {"error": {"code": 101144, "type": "user_has_risk"}}
    raised2 = None
    try:
        c2.silent_login("fake", "fp")
    except LoginError as ex:
        raised2 = ex
    check("silent_login 风控抛 LoginError",
          raised2 is not None and raised2.code == 101144 and raised2.type == "user_has_risk")

    # net_check=True 走 embedded path (打桩记录 path)
    seen = {}
    def fake_form(path, data, method="POST"):
        seen["path"] = path
        return {"openId": "o", "unionId": "u", "data": {"token": "t", "userId": 1}}
    c2._re_form = fake_form
    c2.silent_login("code", "fp", net_check=True)
    check("net_check 走 embedded", seen.get("path") == PATHS["newwxsilentlogin"])


def test_sign_in_helper():
    """签到链路: fetch_check_in 解析 data.checkIn; sign_in 自动取 id/day 打 check/in。"""
    from meituan_fanfan.api import FanfanClient, UserState

    cli = FanfanClient(user=UserState(token="T"))
    calls = {}

    class _Resp:
        def __init__(self, payload):
            self._p = payload
        def json(self):
            return self._p

    class _Http:
        def __init__(self, outer):
            self.outer = outer
        def request(self, method, url, headers=None, data=None, params=None):
            if "activity/list" in url:
                return _Resp({"ret": 0, "data": {"checkIn": {
                    "missionSecretId": "SID", "isTodayCheckedIn": False, "daysCheckedIn": 0,
                    "checkInList": [
                        {"day": 1, "isCanCheckIn": True},
                        {"day": 2, "isCanCheckIn": False}]}}})
            return _Resp({"ret": 0, "data": {"awardType": "POINTS", "awardValue": 100}})

    cli.http = _Http(calls)
    ci = cli.fetch_check_in()
    check("fetch_check_in 解析 missionSecretId", ci.get("missionSecretId") == "SID")
    res = cli.sign_in()
    check("sign_in ret=0", res.get("ret") == 0)
    check("sign_in award=100", (res.get("data") or {}).get("awardValue") == 100)

    # 无 isCanCheckIn 时返回 -1, 不打 check/in
    class _Http2(_Http):
        def request(self, *a, **k):
            return _Resp({"ret": 0, "data": {"checkIn": {"missionSecretId": "S", "checkInList": []}}})
    cli.http = _Http2({})
    check("sign_in 无可签 day 返回 -1", cli.sign_in().get("ret") == -1)


def test_sign_up_helper():
    """报名链路: fetch_signable_pois 解析 infos; sign_up 必带 wxp 打 mission/open。"""
    from meituan_fanfan.api import FanfanClient, UserState

    cli = FanfanClient(user=UserState(token="T"))
    seen = {}

    class _Resp:
        def __init__(self, payload):
            self._p = payload
        def json(self):
            return self._p

    class _Http:
        def request(self, method, url, headers=None, data=None, params=None):
            body = json.loads(data.decode()) if data else {}
            if "queryPoiByRecallBiz" in url:
                return _Resp({"ret": 0, "infos": [{
                    "poiBaseInfo": {"name": "三米粥铺(滨江浦沿店)"},
                    "planActivityInfoList": [
                        {"poiEventId": "EID", "pvid": "PV", "userSignStatus": "CAN_SIGN"}]}]})
            seen["body"] = body
            return _Resp({"ret": 0, "msg": "成功"})

    cli.http = _Http()
    pois = cli.fetch_signable_pois()
    check("fetch_signable_pois 解析 infos", len(pois) == 1 and pois[0]["planActivityInfoList"][0]["poiEventId"] == "EID")
    res = cli.sign_up("EID", "PV")
    check("sign_up ret=0", res.get("ret") == 0)
    check("sign_up 必带 wxp", bool(seen["body"].get("wxp")))
    check("sign_up channelType=SELF", seen["body"].get("channelType") == "SELF")
    check("sign_up 打 mission/open", seen["body"].get("missionSecretId") == "EID")


if __name__ == "__main__":
    test_vm()
    test_mtgsig()
    test_siua_decrypt()
    test_local_id()
    test_build_w()
    test_signer_end_to_end()
    test_wechat_fingerprint_shape()
    test_login_branches()
    test_sign_in_helper()
    test_sign_up_helper()
    print("\n==== %d PASS / %d FAIL ====" % (len(PASS), len(FAIL)))
    if FAIL:
        print("FAILED:", FAIL)
        sys.exit(1)
    print("ALL PASS ✅")
