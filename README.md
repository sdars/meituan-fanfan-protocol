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
  test_protocol.py   黄金向量逐字节比对 (14 项)
  fixtures/          golden.json / deep.json / vmcap.json / dfp.json
examples/
  login_flow.py / login_via_yyb.py / probe_login.py / business_api.py
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
