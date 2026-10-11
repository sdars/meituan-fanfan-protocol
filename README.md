# 美团返返小程序 纯协议逆向

AppID `wxfdba1f3193621ebf`（美团返返 / foodtaster）登录及全部业务接口的
**mtgsig 签名 + 指纹 + 登录链路** 纯 Python 复现。

- **零 adb / Frida / 真机 / RPC**：所有签名在 Python 侧静态生成。
- 算法来源：`npm/@mtfe/wx-jsguard` (jsguard 1.6.5) + `copy/account/account-core`。

## 目录

```
src/meituan_fanfan/
  _vm.py         jsguard 自定义 VM (cb / rc4_prga / x_b64)
  _mtgsig.py     mtgsig 请求签名 (ee / signWithSiua)
  _finger.py     设备指纹 siua / dfpId / localId / wechatFingerprint
  signer.py      请求规范化 + Signer
  login.py       登录链路 (getWxIds / silentLogin / getMtInfo)
  api.py         业务接口客户端 (offsiteact /wmpact/*)
tests/
  test_protocol.py   黄金向量逐字节比对 (29 项)
  fixtures/          golden.json / deep.json / vmcap.json / dfp.json
examples/
  login_flow.py / login_via_yyb.py / probe_login.py / business_api.py
  probe_all_apis.py     全量业务接口探测 (60 个前端函数, 支持 prod/staging 域)
  full_chain.py         全链路闭合 (YYB 铸码 -> 登录 -> 业务接口)
  sign_in.py            签到链路 (fetchActivityList(CHECK_IN) -> check/in, 必须 prod 域)
  sign_up.py            店铺报名链路 (queryPoiByRecallBiz -> mission/open, st 域 + 必带 wxp)
  lock_keeper.py        锁单守护 (取消->重报续期, 复位 30 分钟下单窗口)
  diagnose_account.py   账号诊断 (YYB 会话 rt/at/scope + 美团 appid 铸码能力)
docs/
  接口文档.md / 算法原理.md
```

## 快速开始

```bash
# 运行协议验证
/root/Knight/.venv/bin/python tests/test_protocol.py

# 依赖
/root/Knight/.venv/bin/pip install -r requirements.txt
```

## 账号诊断

`examples/diagnose_account.py` 对「指定 / 批量 / 全部」YYB 账号做体检, 在 pcyyb
的 rt/at 有效性 + 有效期 + scope + 授权能力之上, 追加本仓库最关键的判据:
**该账号能否为返返 appid `wxfdba1f3193621ebf` 铸出原生 wx.login code**。

```bash
cd /root/YYB/meituan-fanfan
# 单个账号 (open_id 或 json 路径)
/root/Knight/.venv/bin/python examples/diagnose_account.py -a <open_id_or_json>
# 一批 / 全部
/root/Knight/.venv/bin/python examples/diagnose_account.py -a A -a B
/root/Knight/.venv/bin/python examples/diagnose_account.py --all
# 机器可读 / 只跑 pcyyb 侧
/root/Knight/.venv/bin/python examples/diagnose_account.py --all --json
/root/Knight/.venv/bin/python examples/diagnose_account.py --all --no-cast
```

输出: `open_id  scope_runtime=yes/no  buffer=OK/失效码  cast[<appid>]=OK <code>...`

> pcyyb 侧完整诊断能力见 `pcyyb/protocol/docs/账号诊断.md`。

## 说明

- `code`（wx.login 返回值）是唯一需要真实微信环境的外部输入。
- `wechatFingerprint` 由 `finger.g()` 纯 Python 生成。
- 逆向分析原始产物见 `/root/YYB/work/逆向分析/2026-10-11/meituan_fanfan/`。
- **签到闭环实测**: 签到 = `fetchActivityList(['CHECK_IN'])` 取 `missionSecretId`
  + 可签到的 `day`, 再 `fetchSignInInfo(missionSecretId, day)` 打
  `/wmpact/mission/check/in`。**必须用 prod 域** `offsiteact.meituan.com`
  (staging 域返回的 `missionSecretId` 无效, check/in 会 ret 99)。实测
  prod 域 `ret:0` 成功发放 100 积分, 复查 `isTodayCheckedIn=true`。详见
  [`docs/接口文档.md`](docs/接口文档.md) §4, 示例 `examples/sign_in.py`。
- **店铺报名闭环实测**: 报名 = `fetchPoiList`(st 域 + 真实经纬度) 取店铺
  `planActivityInfoList[].{poiEventId,pvid}` (userSignStatus=`CAN_SIGN`),
  再 `fetchSignUpTask` 打 `/wmpact/mission/open`。**报名必带 `wxp`** (constants.js
  `WXP_BACK_UP`), 否则后端 `ret:10 必要参数为空`; 带上后进入真实逻辑, 实测
  三米粥铺等可返回 `ret:0 成功`, 复查 `fetchMissionList` 出现 `IN_PROGRESS` 新记录。
  详见 [`docs/接口文档.md`](docs/接口文档.md) §5, 示例 `examples/sign_up.py`。
- **锁单续期实测**: 报名后进入 `SIGN_NO_ORDER`, 后端给 **30 分钟**下单窗口
  (`orderLimitTime` 秒)。只要未下单, 就能「`cancelMission` -> 立即 `signUpTask`」
  复位窗口 (每次重报产生新 `userMissionSecretId`)。取消接口同样**必带 `wxp`**。
  详见 [`docs/接口文档.md`](docs/接口文档.md) §6, 守护脚本 `examples/lock_keeper.py`。
