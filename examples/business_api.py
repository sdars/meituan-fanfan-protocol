# -*- coding: utf-8 -*-
"""业务接口示例 (纯协议)。

用已登录的 token / deviceid 调用 /wmpact/* 接口。
运行:
  /root/Knight/.venv/bin/python examples/business_api.py <token> <deviceid>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from meituan_fanfan import FanfanClient, Signer, UserState  # noqa: E402


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else None
    device_id = sys.argv[2] if len(sys.argv) > 2 else None
    user = UserState(token=token, device_id=device_id,
                     latitude=39.9087, longitude=116.3975, app_version="1.0.0")
    cli = FanfanClient(signer=Signer(), user=user)
    print("[*] 积分余额:", cli.fetchPointsBalance())
    print("[*] 任务列表:", cli.fetchMissionList())
    print("[*] 钱包余额:", cli.fetchWalletBalance())


if __name__ == "__main__":
    main()
