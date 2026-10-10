# 美团返返 能否通过 YYB(应用宝) 免密登录 —— 可行性评估

> 结论（2026-10-11 实测）：**不能**。应用宝的免密登录授权链路对
> `wxfdba1f3193621ebf`（美团返返/返现小程序）不可用，且其签发的 `login_code`
> 无法被美团服务端消费。美团返返登录链路的 `wx.login code` 只能来自真实微信环境。

## 1. 设想的链路

```
YYB 扫码登录 (unionid)
   │  [A] pcyyb_get_wx_login_code(unionid, wxa_appid=wxfdba1f3193621ebf)
   ▼
login_code  ──►  美团 getweappuserinfo(code)  ──►  openId/unionId  ──►  silentLogin
```

即用 YYB 免密授权替代 `wx.login`，从而彻底摆脱真机微信。

## 2. 实测结果（全部纯协议，无 adb）

### 2.1 YYB 授权接口对美团 appid 直接拒绝

| appid | 说明 | [A] pcyyb_get_wx_login_code |
| --- | --- | --- |
| `wx08c266f792c0a88c` | 应用宝离线页登记的小程序 | `code=0`，返回 `login_code` |
| `wxd44977328b36e647` | 平台登录 appid | `-109 invalid wx app id` |
| `wxfdba1f3193621ebf` | **美团返返** | `-109 invalid wx app id` |

`user_type=0/1` 均返回 `-109`。授权接口只对**应用宝侧登记过的小程序**签发
`login_code`，美团返返不在该白名单内（与应用宝目录 detail 为空一致）。

### 2.2 即使拿到 code，美团服务端也拒绝

用 YYB 为**可授权 appid** 签发的 `login_code` 去喂美团
`POST open.meituan.com/user/thirdinfo/getweappuserinfo`：

```
{"error":{"code":101172,"type":"weapp_invalid_session",
          "message":"会话已过期，请重新登录",
          "data":{"details":"invalid code, rid: ..."}}}
```

说明该 `login_code` 是**按目标小程序 appid 绑定**的微信态登录凭证，
不是可跨 appid 使用的微信 `code2Session` 码；美团侧只认自己 appid 的
`wx.login` code。两条链路无法对接。

## 3. 根因

1. **白名单边界**：应用宝免密登录仅覆盖其生态内已登记的小程序/小游戏；
   美团返返是美团自有小程序，未在应用宝侧登记。
2. **凭证作用域**：`login_code` 绑定目标 appid，只能被该 appid 的服务端消费；
   美团返返的登录入口只接受本 appid 的 `wx.login` code。

## 4. 对协议实现的影响

- `meituan_fanfan.login` 的 `get_wx_ids(code)` / `silent_login(code)` 中，
  `code` **必须**来自真实微信环境的 `wx.login`，无法由 YYB 免密链路提供。
- 其余环节（mtgsig 签名、siua/localId、wechatFingerprint）已是纯 Python，
  与 YYB 无关。故 `login_via_yyb` 方案**不实现**（无可行输入）。

## 5. 备选方向（若确需脱离真机）

- 微信 PC 端 / 微信开发者工具本地登录态下的 `wx.login`（仍属微信环境，
  但不是 YYB 链路）。
- 其他持有美团返返 appid 授权、可签发该 appid code 的合规渠道（暂无）。

> 复现探针：`work/逆向分析/2026-10-11/yyb_meituan/probe_feed_code.py`
