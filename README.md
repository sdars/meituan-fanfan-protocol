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

## 说明

- `code`（wx.login 返回值）是唯一需要真实微信环境的外部输入。
- `wechatFingerprint` 由 `finger.g()` 纯 Python 生成。
- 逆向分析原始产物见 `/root/YYB/work/逆向分析/2026-10-11/meituan_fanfan/`。
