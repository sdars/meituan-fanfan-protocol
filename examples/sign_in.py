# -*- coding: utf-8 -*-
"""美团返返 签到链路示例 (纯协议)。

链路 (对应 chunk_8 签到页 onLoad / signIn):
  [1] fetchActivityList(['CHECK_IN']) -> data.checkIn
        {missionSecretId, isTodayCheckedIn, daysCheckedIn, checkInList[...]}
  [2] 从 checkInList 找 isCanCheckIn=true 的 day
  [3] fetchSignInInfo(missionSecretId, day)  POST /wmpact/mission/check/in
        -> {ret:0, data:{awardType:'POINTS', awardValue:100}}
  [4] 复查 fetchActivityList -> isTodayCheckedIn=true

**关键: 必须用 prod 域** (offsiteact.meituan.com)。st 域 (offsiteact.st.meituan.com)
返回的 missionSecretId 在 prod 域无效, 且直接用 st 域打 check/in 会 ret 99
(签到失败, 请稍后重试~)。见 docs/接口文档.md。

运行:
  /root/Knight/.venv/bin/python examples/sign_in.py          # 用已保存 token (env)
  FANFAN_TOKEN=... FANFAN_DEVICE_ID=... /root/Knight/.venv/bin/python examples/sign_in.py

无 token 时可用 examples/full_chain.py 先登录并写入 /tmp/fanfan_auth.json。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meituan_fanfan import FanfanClient, Signer, UserState  # noqa: E402
from meituan_fanfan.api import BASE_URL  # noqa: E402


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

    user = UserState(token=token, user_id=user_id, open_id=open_id,
                     device_id=os.environ.get("FANFAN_DEVICE_ID", "f3457391d7494fd4b52c6f7d09e6575f"),
                     latitude=39.9087, longitude=116.3975,
                     app_version="1.0.0", csec_version_name="1.0.0")
    # 签到必须走 prod 域
    cli = FanfanClient(signer=Signer(), user=user, base_url=BASE_URL)
    print("[*] base_url =", cli.base_url)

    ci = cli.fetch_check_in()
    print("[1] missionSecretId = %s  isTodayCheckedIn = %s  daysCheckedIn = %s"
          % (ci.get("missionSecretId"), ci.get("isTodayCheckedIn"), ci.get("daysCheckedIn")))
    target = next((it for it in (ci.get("checkInList") or []) if it.get("isCanCheckIn")), None)
    if not target:
        print("[2] 今日无可签到 day (已签或未到时间)")
        return
    print("[2] target day = %s (award=%s %s)"
          % (target.get("day"), target.get("awardValue"), target.get("awardType")))

    res = cli.sign_in()
    print("[3] signIn ->", json.dumps(res, ensure_ascii=False))
    ci2 = cli.fetch_check_in()
    print("[4] after -> isTodayCheckedIn = %s  daysCheckedIn = %s"
          % (ci2.get("isTodayCheckedIn"), ci2.get("daysCheckedIn")))


if __name__ == "__main__":
    main()
