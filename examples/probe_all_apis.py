# -*- coding: utf-8 -*-
"""全量业务接口探测 (纯协议, 60 个前端函数)。

逐个调用 api/index.js 导出的全部业务接口, 记录 http/ret/msg/data。
默认走 staging 域 (offsiteact.st.meituan.com), 该域 WAF 放行全部路径;
prod 域 (offsiteact.meituan.com) 对部分路径 (mission/user/list 等) 有额外拦截。

运行:
  python examples/probe_all_apis.py [--prod] [<token>] [<deviceid>]

环境变量:
  FANFAN_TOKEN / FANFAN_DEVICE_ID / FANFAN_OPEN_ID / FANFAN_USER_ID
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meituan_fanfan import FanfanClient, Signer, UserState  # noqa: E402
from meituan_fanfan.api import (API_URL, DEFAULT_PARAMS, GET_APIS,  # noqa: E402
                                STAGING_BASE_URL, BASE_URL)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_prod = "--prod" in sys.argv
    token = (args[0] if len(args) > 0 else os.environ.get("FANFAN_TOKEN"))
    device_id = (args[1] if len(args) > 1 else os.environ.get("FANFAN_DEVICE_ID"))
    open_id = os.environ.get("FANFAN_OPEN_ID")
    user_id = os.environ.get("FANFAN_USER_ID")
    base = BASE_URL if use_prod else STAGING_BASE_URL

    user = UserState(token=token, device_id=device_id, open_id=open_id,
                     user_id=user_id, latitude=39.9087, longitude=116.3975,
                     app_version="1.0.0", csec_version_name="1.0.0")
    cli = FanfanClient(signer=Signer(), user=user, base_url=base)
    print("[*] base_url = %s" % base)

    results = []
    for key, path in API_URL.items():
        data = dict(DEFAULT_PARAMS.get(key, {}))
        if key in ("walletDeduct", "generalWalletDeduct") and open_id:
            data["openId"] = open_id
        method = "GET" if key in GET_APIS else "POST"
        try:
            r = cli.request(key, data=data)
        except Exception as e:
            r = {"statusCode": "ERR", "text": str(e)[:100]}
        http = r.get("statusCode", 200)
        ret = r.get("ret")
        msg = r.get("msg")
        results.append({"key": key, "path": path, "http": http, "ret": ret,
                        "msg": msg, "data": r.get("data")})
        print("%-34s %-4s http=%-4s ret=%-8s msg=%s"
              % (key, method, http, ret, str(msg)[:36]))

    out = "/tmp/fanfan_probe_all.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    ok = sum(1 for x in results if x["http"] == 200)
    print("\n[*] %d/%d http 200 -> %s" % (ok, len(results), out))


if __name__ == "__main__":
    main()
