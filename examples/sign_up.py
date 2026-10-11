# -*- coding: utf-8 -*-
"""美团返返 店铺报名链路示例 (纯协议)。

链路 (对应首页 poi-card 的 fetchPoiListCashback -> fetchSignUpTask):
  [1] fetchPoiListCashback  POST /wmpact/ge/queryPoiByRecallBiz
        body {recallBizId:'cpsPromotionOrderMulti', pageNo:1, pageSize:20, sjActivity:'ssxm4'}
        -> data.infos[], 每个 poi 含 planActivityInfoList[]
  [2] 取 planActivityInfoList[i] 中 userSignStatus=='CAN_SIGN' 的活动
        poiEventId(==missionSecretId), pvid
  [3] fetchSignUpTask  POST /wmpact/mission/open
        body {missionSecretId, channelType:'SELF', pvid, sjActivity:'ssxm4', wxp, ...}
        -> ret:0 成功 / 204 抢光 / 209 频繁 / 202 已下线

**两个关键点**:
  1. 读店铺列表 (fetchPoiList) **必须用 st 域** 且带真实经纬度; prod 域召回为空
     (noRecallPoiReason=3)。本示例用杭州滨江 (30.19,120.17) 才能召回三米粥铺等。
  2. 报名写接口 **必须带 wxp** (constants.js WXP_BACK_UP)。缺 wxp 时后端返回
     ret:10 (必要参数为空); 带上后才进入真实报名逻辑。

运行:
  FANFAN_TOKEN=... FANFAN_DEVICE_ID=... /root/Knight/.venv/bin/python examples/sign_up.py

无 token 时可用 examples/full_chain.py 先登录并写入 /tmp/fanfan_auth.json。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meituan_fanfan import FanfanClient, Signer, UserState  # noqa: E402
from meituan_fanfan.api import STAGING_BASE_URL, WXP_PROD  # noqa: E402


def main():
    token = os.environ.get("FANFAN_TOKEN")
    user_id = os.environ.get("FANFAN_USER_ID")
    open_id = os.environ.get("FANFAN_OPEN_ID")
    if not token and os.path.exists("/tmp/fanfan_auth.json"):
        a = json.load(open("/tmp/fanfan_auth.json"))
        token, user_id, open_id = a.get("token"), str(a.get("userId")), a.get("openId")
    if not token:
        print("缺 token: 设 FANFAN_TOKEN 或先跑 examples/full_chain.py")
        return

    # 店铺列表必须走 st 域 + 真实经纬度 (示例: 杭州滨江)
    lat = float(os.environ.get("FANFAN_LAT", "30.19"))
    lon = float(os.environ.get("FANFAN_LON", "120.17"))
    user = UserState(token=token, user_id=user_id, open_id=open_id,
                     device_id=os.environ.get("FANFAN_DEVICE_ID", "f3457391d7494fd4b52c6f7d09e6575f"),
                     latitude=lat, longitude=lon,
                     app_version="1.0.0", csec_version_name="1.0.0")
    cli = FanfanClient(signer=Signer(), user=user, base_url=STAGING_BASE_URL)
    print("[*] base_url = %s  lat/lon = %s/%s" % (cli.base_url, lat, lon))

    pois = cli.fetch_signable_pois()
    print("[1] 召回店铺 = %d" % len(pois))
    cands = [(p, a) for p in pois for a in (p.get("planActivityInfoList") or [])
             if a.get("userSignStatus") == "CAN_SIGN"]
    print("[2] CAN_SIGN 候选 = %d" % len(cands))
    for p, a in cands:
        print("    %-24s poiEventId=%s inv=%s"
              % (p.get("poiBaseInfo", {}).get("name"), a.get("poiEventId"), a.get("validInventory")))

    if not cands:
        print("无可报名店铺")
        return
    p, a = cands[0]
    print("[3] 报名 %s ..." % p.get("poiBaseInfo", {}).get("name"))
    res = cli.sign_up(a.get("poiEventId"), a.get("pvid"), wxp=WXP_PROD)
    print("[4] signUp ->", json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
