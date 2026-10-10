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


if __name__ == "__main__":
    test_vm()
    test_mtgsig()
    test_siua_decrypt()
    test_local_id()
    test_build_w()
    test_signer_end_to_end()
    test_wechat_fingerprint_shape()
    print("\n==== %d PASS / %d FAIL ====" % (len(PASS), len(FAIL)))
    if FAIL:
        print("FAILED:", FAIL)
        sys.exit(1)
    print("ALL PASS ✅")
