# 美团返返 能否通过 YYB(应用宝) 免密登录 —— 可行性评估

> 结论（2026-10-11 实测，分两条路径）：
>
> - **login_code 路径（[A] pcyyb_get_wx_login_code）：不能**。应用宝对
>   `wxfdba1f3193621ebf` 返回 `-109 invalid wx app id`（白名单外），且其为其它
>   appid 签发的 `login_code` 也无法被美团服务端消费（凭证按 appid 绑定）。
> - **MMTLS 原生 code 路径（[B] authorize_buffer + qqfarm 铸码）：理论可行**。
>   YYB 登录态可换取「微信平台授权 buffer」，用 qqfarm 的 MMTLS/ShortLink 实现
>   铸出**目标 appid 的原生 `wx.login` code**（与真机 `wx.login()` 等价）。
>   此路径不经过应用宝白名单，只要 buffer 可用即可为任意 appid 铸码。
>
> 两条路径的**共同前提**是 pcyyb 账号登录态具备 `snsapi_runtime_pcsdk` scope
> （扫码登录时授予）。scope 缺失时 `authorize_buffer` 返回
> `-101 GetLoginBuffer error [40188] [invalid scope]`（见 §7）。

## 1. 设想的链路

```
YYB 扫码登录 (unionid)
   │  [A] pcyyb_get_wx_login_code(unionid, wxa_appid=wxfdba1f3193621ebf)
   ▼
login_code  ──►  美团 getweappuserinfo(code)  ──►  openId/unionId  ──►  silentLogin
```

即用 YYB 免密授权替代 `wx.login`，从而彻底摆脱真机微信。

> 注：上为 **login_code 路径**（已被证否）。另有 **MMTLS 原生 code 路径**：
> 不走 `[A]`，而是 `[B] authorize_buffer` 取微信平台授权 buffer，再用 qqfarm 的
> MMTLS/ShortLink 铸出目标 appid 的原生 `wx.login` code，直接喂美团
> `getweappuserinfo`。见 §7。

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

## 6. 补充：YYB 登录态本身就是一个微信开放平台授权态

用 `refresh_token` 刷新出新鲜 `access_token` 后，直接打微信开放平台接口：

```
GET https://api.weixin.qq.com/sns/userinfo?access_token=<YYB at>&openid=<YYB open_id>
-> {"openid":"owNAX6txE4vcGLryGW-ptHb5JrcY","nickname":"...",
    "headimgurl":"https://thirdwx.qlogo.cn/...",
    "unionid":"oTOwy6QWDRrpteehjeRYPXyOoVUs"}
```

即：**应用宝登录本身就是微信扫码 OAuth**（`open.weixin.qq.com/connect/qrconnect`，
appid=`wxd44977328b36e647`，scope=`snsapi_login,snsapi_runtime_pcsdk`），
YYB 持有的 `access_token` 是**微信开放平台的合法 sns token**，
`open_id` 是该 appid 下的 openid，`unionid` 全局唯一。

但这**不能反向授权第三方小程序**：

- 该微信态绑定的开放平台 appid 是应用宝自己的 `wxd44977328b36e647`，
  openid/unionid 都是「在该 appid 下」的身份；
- 授权小程序用的是另一套接口（`pcyyb_get_wx_login_code`），只对白名单 appid
  签发，美团返返 `-109`（见 §2）。

方向性：**微信 → 应用宝** 是成立的（登录）；**应用宝 → 美团返返** 不成立（授权）。

## 7. MMTLS 原生 code 路径（本轮新增）

### 7.1 为什么 login_code 路径不行、原生 code 路径可行

`[A] pcyyb_get_wx_login_code` 是应用宝**面向自己生态**的免密授权：它按目标
appid 白名单签发 `login_code`，美团 appid 不在名单内（`-109`）。

但应用宝登录态里还藏着一个**微信平台授权 buffer**（`pcyyb_get_wx_login_buffer_auth`
返回的 protobuf `{token, app, appid}`）。这个 buffer 是微信官方给「PC 端 SDK
（snsapi_runtime_pcsdk）」的登录凭据。把它交给微信 MMTLS 长连接，可以发起
一次**真正的 `wx.login()`**，铸出**任意目标 appid** 的原生登录 code —— 这正是
真机里 `wx.login({appId})` 拿到的同款码。

```
pcyyb SessionStore.load(account)      # 扫码登录态 (unionid/at/guid)
  -> authorize_buffer()['raw']         # [B] 微信平台授权 buffer
  -> qqfarm.getNativeWxLoginCode(buf, app_id)   # MMTLS + ShortLink 铸码
  -> code                              # 目标 appid 的原生 wx.login code
  -> 美团 getweappuserinfo / weappsilentlogin
```

> 关键：`pcyyb.authorize_code()` 返回的 `login_code` **不是** `wx.login` code，
> 喂美团会得 `101172 weapp_invalid_session`。必须走 MMTLS 铸码。

### 7.2 前提：`snsapi_runtime_pcsdk` scope 必须在线

`authorize_buffer` 依赖登录态里的 **runtime scope**。扫码登录时
`open.weixin.qq.com/connect/qrconnect` 的 `scope=snsapi_login,snsapi_runtime_pcsdk`
会授予它；一旦 scope 失效（如刷新/长时间闲置），`authorize_buffer` 返回：

```
{"code":-101,"msg":"GetLoginBuffer error [40188] [invalid scope, rid: ...]"}
```

此时**两种 code 路径都不可用**，必须**重新扫码登录**恢复 scope。

### 7.3 本项目封装

- `src/meituan_fanfan/yyb_code.py`：`get_wx_login_code(app_id)` /
  `try_get_wx_login_code(app_id)`（复用 pcyyb + qqfarm，不修改其仓库）。
- `examples/login_via_yyb.py`：YYB 铸码 → getWxIds → silentLogin → getMtInfo。
- `examples/probe_login.py`：风控对照探测（打印真实 HTTP 状态）。

### 7.4 与美团外卖的对称性

同一套 MMTLS 铸码逻辑已在**美团外卖**（`wx2c348cf579062e56`）实测：
`getWxIds` 稳定成功（HTTP 200，拿到 openId/unionId），`silentLogin` 首次返回
真实 token，随后被 `101144 user_has_risk` 行为风控拦截。返返与外卖共用美团
账号中台（同域 `open.meituan.com`、同 `getweappuserinfo`/`weappsilentlogin`
路径），故返返链路**算法层等价**，差异仅在 appName / risk_* / token_id 等常量。

> 详见 `meituan-waimai/docs/登录链路与风控.md`。
