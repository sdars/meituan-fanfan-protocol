# -*- coding: utf-8 -*-
"""美团返返 锁单守护 (占名额 + 自动续期)。

原理: 报名成功后进入 SIGN_NO_ORDER 状态, 后端给出 30 分钟下单窗口
(`orderLimitTime` 秒, 见 docs/接口文档.md §6)。只要**未下单**, 就可以
「取消当前报名 -> 立即重新报名」把窗口复位 (每次重报产生新的
userMissionSecretId), 从而长时间占住名额而不用真下单。

本脚本循环对指定店铺执行续期, 直到:
  - 达到 --rounds 次数, 或
  - 用户下单 (取消失败, renew_lock 返回 ok=False), 或
  - Ctrl-C。

用法:
  # 每 25 分钟续期一次, 共 6 次 (约 2.5 小时锁单)
  FANFAN_TOKEN=... /root/Knight/.venv/bin/python examples/lock_keeper.py 三米粥铺 \
      --interval 1500 --rounds 6

  # 先报名再守护 (若当前 CAN_SIGN)
  FANFAN_TOKEN=... /root/Knight/.venv/bin/python examples/lock_keeper.py jzj测试 --sign-first

环境变量: FANFAN_TOKEN / FANFAN_USER_ID / FANFAN_OPEN_ID / FANFAN_DEVICE_ID /
          FANFAN_LAT / FANFAN_LON
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meituan_fanfan import FanfanClient, Signer, UserState  # noqa: E402
from meituan_fanfan.api import STAGING_BASE_URL  # noqa: E402


def build_client():
    token = os.environ.get("FANFAN_TOKEN")
    user_id = os.environ.get("FANFAN_USER_ID")
    open_id = os.environ.get("FANFAN_OPEN_ID")
    if not token and os.path.exists("/tmp/fanfan_auth.json"):
        a = json.load(open("/tmp/fanfan_auth.json"))
        token, user_id, open_id = a.get("token"), str(a.get("userId")), a.get("openId")
    if not token:
        print("缺 token: 设 FANFAN_TOKEN 或先跑 examples/full_chain.py")
        sys.exit(1)
    user = UserState(
        token=token, user_id=user_id, open_id=open_id,
        device_id=os.environ.get("FANFAN_DEVICE_ID", "f3457391d7494fd4b52c6f7d09e6575f"),
        latitude=float(os.environ.get("FANFAN_LAT", "30.19")),
        longitude=float(os.environ.get("FANFAN_LON", "120.17")),
        app_version="1.0.0", csec_version_name="1.0.0")
    return FanfanClient(signer=Signer(), user=user, base_url=STAGING_BASE_URL)


def main():
    ap = argparse.ArgumentParser(description="美团返返锁单守护")
    ap.add_argument("keyword", help="店铺名关键字, 如 三米粥铺")
    ap.add_argument("--interval", type=int, default=1500, help="续期间隔秒 (默认 1500=25 分钟, 留 5 分钟余量)")
    ap.add_argument("--rounds", type=int, default=0, help="续期轮数 (0=无限)")
    ap.add_argument("--sign-first", action="store_true", help="若当前未报名, 先报名")
    args = ap.parse_args()

    cli = build_client()
    print("[*] 锁单守护 keyword=%s interval=%ss rounds=%s" % (args.keyword, args.interval, args.rounds or "inf"))

    if args.sign_first:
        p, a = cli.find_poi(args.keyword)
        if p and a.get("userSignStatus") == "CAN_SIGN":
            r = cli.sign_up(a["poiEventId"], a["pvid"])
            print("[init] 首次报名 -> %s %s" % (r.get("ret"), r.get("msg")))
            time.sleep(2)

    n = 0
    while True:
        n += 1
        res = cli.renew_lock(args.keyword)
        ts = time.strftime("%H:%M:%S")
        if res.get("ok"):
            print("[%s] #%d 续期成功 action=%s umsid %s -> %s"
                  % (ts, n, res.get("action"), res.get("old_umsid"), res.get("new_umsid")))
        else:
            print("[%s] #%d 续期失败 action=%s msg=%s" % (ts, n, res.get("action"), res.get("msg")))
            if res.get("action") == "not_found":
                print("[!] 店铺不在可报名列表 (可能被抢光/下线), 退出")
                break
            break

        if args.rounds and n >= args.rounds:
            print("[*] 达到轮数上限, 退出")
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
