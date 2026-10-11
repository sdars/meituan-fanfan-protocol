# -*- coding: utf-8 -*-
"""美团返返业务接口客户端 (offsiteact.meituan.com /wmpact/*)。

复现 api/index.js + api/interceptors.js + api/request.js:
  - request.use(addMcToken):     header['mt-c-token'] = token
  - request.use(addDeviceId):    header['deviceid']   = deviceId
  - request.use(addOadParams):   data 合并 oadParams + lat/lon
  - request.use(addAppBaseInfoParams): data.xcxVersion = appVersion
  - response.use(returnData):    ret===999999 -> 重登
所有请求在发出前经 @mtfe/weapp-safety-request 注入 header.mtgsig (Signer.sign)。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import requests

from .signer import Signer

BASE_URL = "https://offsiteact.meituan.com"
TEST_BASE_URL = "https://offsiteact.waimai.test.sankuai.com"
STAGING_BASE_URL = "https://offsiteact.st.meituan.com"

# api/index.js exports.API_URL (与前端函数一一对应)
API_URL = {
    "getStructConfig": "/wmpact/ge/getPageModuleInfo",
    "fetchPoiList": "/wmpact/ge/queryPoiByRecallBiz",
    "fetchDaoZongList": "/wmpact/daodian/get_wxlist",
    "guide": "/wmpact/mission/guide",
    "signUpTask": "/wmpact/mission/open",
    "cancelMission": "/wmpact/mission/cancel",
    "missionList": "/wmpact/mission/user/list",
    "searchList": "/wmpact/search/history/list",
    "searchSave": "/wmpact/search/history/save",
    "searchClear": "/wmpact/search/history/clear",
    "cashBack": "/wmpact/mission/cash/back",
    "unlogPoolInfo": "/wmpact/mission/prizepool",
    "waitComment": "/wmpact/mission/user/wait/comment/list",
    "completeComment": "/wmpact/mission/user/complete/comment/list",
    "getCommentDetail": "/wmpact/mission/user/comment/get",
    "activityList": "/wmpact/xcx/activity/list",
    "queryShare": "/wmpact/share/query",
    "joinShare": "/wmpact/share/join",
    "openShare": "/wmpact/share/open",
    "signIn": "/wmpact/mission/check/in",
    "pointsBalance": "/wmpact/points/balance",
    "shareList": "/wmpact/share/list",
    "withdrawList": "/wmpact/wallet/detail",
    "walletDeduct": "/wmpact/wallet/deduct",
    "queryWalletBalance": "/wmpact/wallet/balance",
    "queryPointsDetail": "/wmpact/points/detail",
    "queryGeneralWalletBalance": "/wmpact/generalWallet/balance",
    "queryGeneralWalletWithdrawList": "/wmpact/generalWallet/detail",
    "generalWalletDeduct": "/wmpact/generalWallet/deduct",
    "wxaCode": "/wmpact/mission/getWXQrCode",
    "wxUrlLink": "/wmpact/mission/getWxUrlLink",
    "queryCpsSharePoi": "/wmpact/ge/queryCpsSharePoi",
    "queryDaoDianSingle": "/wmpact/daodian/get_single",
    "queryDynamicRule": "/wmpact/dynamic/rule",
    "getUserRole": "/wmpact/mission/userrole",
    "personAuth": "/wmpact/mission/talent/auth",
    "getAgreementPDF": "/wmpact/mission/talent/getcontract",
    "personSign": "/wmpact/mission/talent/sign",
    "promoteProduct": "/wmpact/mission/talent/selectpool",
    "promoteActivity": "/wmpact/mission/talent/promoteactivity",
    "getTalentShareInfo": "/wmpact/mission/talent/promotionUrlInfo",
    "getTalentPromoteData": "/wmpact/mission/talent/databoard",
    "getMpJumpUrl": "/wmpact/page/wakeup/get_single",
    "getSubscribeTemplateIds": "/wmpact/xcx/subscribe/template",
    "queryRTBPoiInfo": "/wmpact/ge/queryPoiInfo",
    "getWxpDecode": "/wmpact/cps/p/decode",
    "talentWithdrawTax": "/wmpact/generalWallet/estimatePersonalTax",
    "getResourceConfig": "/wmpact/ads/resource/get",
    "getRightsMall": "/wmpact/rights/mall",
    "rightsExchange": "/wmpact/rights/exchange",
    "queryRightsExchangeRecord": "/wmpact/rights/user/exchange/list",
    "queryUnusedRightsList": "/wmpact/rights/user/unused/list",
    "queryDelayCashBackList": "/wmpact/generalWallet/delay/cash/back",
    "fetchHeatmapTaps": "/wmpact/ge/frontend/event/heatmap/taps",
    "reportEvents": "/wmpact/ge/frontend/event/report",
}

# 前端函数名 -> API_URL key (来自 api/index.js 各 fetchXxx)
FRONTEND_FN = {
    "getStructConfig": "getStructConfig",
    "fetchPoiListCashback": "fetchPoiList",
    "fetchCommonPoiList": "fetchPoiList",
    "fetchPoiListFission": "fetchPoiList",
    "fetchDaoZongList": "fetchDaoZongList",
    "fetchCpsSharePoi": "queryCpsSharePoi",
    "fetchGuide": "guide",
    "fetchSignUpTask": "signUpTask",
    "fetchCancelMission": "cancelMission",
    "fetchMissionList": "missionList",
    "fetchSearchList4Address": "searchList",
    "fetchSearchList4Poi": "searchList",
    "fetchSearchSave4Address": "searchSave",
    "fetchSearchSave4Poi": "searchSave",
    "fetchSearchClear4Address": "searchClear",
    "fetchSearchClear4Poi": "searchClear",
    "fetchCashBack": "cashBack",
    "fetchUnlogPoolInfo": "unlogPoolInfo",
    "fetchWaitComment": "waitComment",
    "fetchCompleteComment": "completeComment",
    "fetchCommentDetail": "getCommentDetail",
    "fetchActivityList": "activityList",
    "fetchShareInfo": "queryShare",
    "fetchOpenShare": "openShare",
    "fetchJoinShare": "joinShare",
    "fetchSignInInfo": "signIn",
    "fetchPointsBalance": "pointsBalance",
    "fetchShareList": "shareList",
    "fetchWithdrawList": "withdrawList",
    "fetchWalletDeduct": "walletDeduct",
    "fetchWalletBalance": "queryWalletBalance",
    "fetchPointsDetail": "queryPointsDetail",
    "fetchGeneralWalletBalance": "queryGeneralWalletBalance",
    "fetchGeneralWithdrawList": "queryGeneralWalletWithdrawList",
    "fetchGeneralWalletDeduct": "generalWalletDeduct",
    "fetchTalentWithdrawTax": "talentWithdrawTax",
    "getWxaCode": "wxaCode",
    "getWxUrlLink": "wxUrlLink",
    "fetchDaoDianSingle": "queryDaoDianSingle",
    "fetchDynamicRule": "queryDynamicRule",
    "fetchUserRole": "getUserRole",
    "fetchPersonAuth": "personAuth",
    "fetchAgreementPDF": "getAgreementPDF",
    "fetchPersonSign": "personSign",
    "fetchPromoteProduct": "promoteProduct",
    "fetchPromoteActivity": "promoteActivity",
    "fetchTalentShareInfo": "getTalentShareInfo",
    "fetchTalentDataBoard": "getTalentPromoteData",
    "fetchMpJumpUrl": "getMpJumpUrl",
    "fetchSubscribeTemplateIds": "getSubscribeTemplateIds",
    "fetchRTBPoiInfo": "queryRTBPoiInfo",
    "fetchWxpDecode": "getWxpDecode",
    "fetchResourceConfig": "getResourceConfig",
    "fetchRightsMall": "getRightsMall",
    "fetchRightsExchange": "rightsExchange",
    "fetchRightsExchangeRecord": "queryRightsExchangeRecord",
    "fetchUnusedCouponList": "queryUnusedRightsList",
    "fetchDelayCashBackList": "queryDelayCashBackList",
    "fetchHeatmapTaps": "fetchHeatmapTaps",
    "reportEvents": "reportEvents",
}

# 使用 GET 的接口
GET_APIS = {"queryDynamicRule", "getSubscribeTemplateIds", "getWxpDecode", "fetchHeatmapTaps"}

# 每个前端函数的默认请求参数 (api/index.js 里固定的部分)。
# 用于无需业务上下文的探测 / 个例。
DEFAULT_PARAMS = {
    "getStructConfig": {"actId": "1"},
    "fetchPoiList": {"recallBizId": "cpsPromotionOrderMulti", "pageNo": 1, "pageSize": 10},
    "fetchDaoZongList": {"recallBizId": "cpsDaoZongWxProduct", "pageNo": 1, "pageSize": 10},
    "queryCpsSharePoi": {"recallBizId": "cpsSelfPromotionSinglePoi", "pageNo": 1},
    "guide": {"eventIdList": []},
    "signUpTask": {},
    "cancelMission": {"userMissionSecretId": "1"},
    "missionList": {},
    "searchList": {"biz": "SHANG_JIN_SEARCH", "count": 10},
    "searchSave": {"biz": "SHANG_JIN_SEARCH", "searchKey": "x", "ext": "{}"},
    "searchClear": {"biz": "SHANG_JIN_SEARCH"},
    "cashBack": {},
    "unlogPoolInfo": {},
    "waitComment": {},
    "completeComment": {},
    "getCommentDetail": {"orderViewId": "1"},
    "activityList": {"queryModel": {}},
    "queryShare": {"teamId": "1"},
    "joinShare": {"teamId": "1"},
    "openShare": {"activityId": "1", "userId": "1"},
    # 注意: missionSecretId 必须来自 prod 域 fetchActivityList(['CHECK_IN']) 的
    # data.checkIn.missionSecretId (st 域的 id 在 prod 域无效); 用 FanfanClient.sign_in() 自动取。
    "signIn": {"day": 1, "missionSecretId": "1"},
    "pointsBalance": {},
    "shareList": {},
    "withdrawList": {},
    "walletDeduct": {"openId": None},
    "queryWalletBalance": {},
    "queryPointsDetail": {},
    "queryGeneralWalletBalance": {"walletType": 1},
    "queryGeneralWalletWithdrawList": {},
    "generalWalletDeduct": {"openId": None},
    "talentWithdrawTax": {},
    "wxaCode": {"grantType": "client_credential", "appid": "wxfdba1f3193621ebf"},
    "wxUrlLink": {"grantType": "client_credential", "appid": "wxfdba1f3193621ebf"},
    "queryDaoDianSingle": {"recallBizId": "cpsDaoZongWxSinglePoi"},
    "queryDynamicRule": {"type": "1"},
    "getUserRole": {},
    "personAuth": {},
    "getAgreementPDF": {},
    "personSign": {},
    "promoteProduct": {"bizLine": 40},
    "promoteActivity": {},
    "getTalentShareInfo": {},
    "getTalentPromoteData": {},
    "getMpJumpUrl": {"urlContainerList": [1]},
    "getSubscribeTemplateIds": {"slot": "1"},
    "queryRTBPoiInfo": {"sjActivity": "1", "mediumParams": {"poi_id_str": "1"}},
    "getWxpDecode": {"p": "1"},
    "getResourceConfig": {"spotIdList": [1]},
    "getRightsMall": {},
    "rightsExchange": {},
    "queryRightsExchangeRecord": {},
    "queryUnusedRightsList": {},
    "queryDelayCashBackList": {},
    "fetchHeatmapTaps": {},
    "reportEvents": {},
}

# @mtfe/weapp-safety-request addCommonParams 注入位置 (constants/common.js)
PARAMS_POS_URL = ["yodaReady", "csecappid", "csecplatform", "csecversionname", "csecversion"]
PARAMS_POS_HEADER = ["token", "csecuuid", "csecdpid", "csecuserid",
                     "openId", "openIdCipher", "eptoken", "csecepuid"]

# safety-request defaultInitParams (constants/common.js)
SAFETY_DEFAULT_PARAMS = {"csecversion": "1.4.0", "yodaReady": "wx", "csecplatform": 3}

# openresty WAF 只放行带正常 UA 的请求; 缺 UA / python-requests 默认 UA 会被 403
DEFAULT_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.40(0x18002832) "
              "NetType/WIFI Language/zh_CN miniProgram")


def _referer(app_id: str, ver: int = 1) -> str:
    return "https://servicewechat.com/%s/%d/page-frame.html" % (app_id, ver)


@dataclass
class UserState:
    """stores/userInfo.js 的运行时字段 (业务请求需要的凭据/参数)。"""

    token: str | None = None           # mt-c-token
    device_id: str | None = None       # deviceid
    latitude: float = 0.0
    longitude: float = 0.0
    app_version: str = "0.0.0"         # xcxVersion
    oad_params: dict = field(default_factory=dict)
    # --- safety-request 层注入 (addCommonParams) ---
    open_id: str | None = None         # header.openId
    open_id_cipher: str | None = None  # header.openIdCipher
    csec_uuid: str | None = None       # header.csecuuid (lxcuid)
    csec_app_id: str | None = None     # url.csecappid
    csec_version_name: str | None = None  # url.csecversionname (小程序版本)
    csec_version: str = "1.4.0"        # url.csecversion (sdk 版本)
    csec_platform: int = 3             # url.csecplatform (3=WX)
    csec_dp_id: str | None = None      # header.csecdpid
    ep_token: str | None = None        # header.eptoken
    csec_ep_uid: str | None = None     # header.csecepuid
    app_id: str = "wxfdba1f3193621ebf"

    def safety_params(self) -> dict:
        """合并 safety-request 层的 url/header 待注入参数。"""
        p = dict(SAFETY_DEFAULT_PARAMS)
        p["csecappid"] = self.csec_app_id or self.app_id
        p["csecversion"] = self.csec_version
        p["csecplatform"] = self.csec_platform
        if self.csec_version_name:
            p["csecversionname"] = self.csec_version_name
        if self.token:
            p["token"] = self.token
        if self.csec_uuid:
            p["csecuuid"] = self.csec_uuid
        if self.user_id:
            p["csecuserid"] = str(self.user_id)
        if self.open_id:
            p["openId"] = self.open_id
        if self.open_id_cipher:
            p["openIdCipher"] = self.open_id_cipher
        if self.csec_dp_id:
            p["csecdpid"] = self.csec_dp_id
        if self.ep_token:
            p["eptoken"] = self.ep_token
        if self.csec_ep_uid:
            p["csecepuid"] = self.csec_ep_uid
        return p

    user_id: str | None = None         # header.csecuserid


class FanfanClient:
    def __init__(self, signer: Signer | None = None, user: UserState | None = None,
                 base_url: str = BASE_URL, session: requests.Session | None = None):
        self.signer = signer or Signer()
        self.user = user or UserState()
        self.base_url = base_url
        self.http = session or requests.Session()

    def _apply_interceptors(self, method: str, path: str, data: Any, header: dict):
        # addDeviceId
        if self.user.device_id:
            header["deviceid"] = self.user.device_id
        # addMcToken
        if self.user.token:
            header["mt-c-token"] = self.user.token
        # addOadParams + addAppBaseInfoParams
        d = dict(data) if isinstance(data, dict) else ({} if data is None else data)
        if isinstance(d, dict):
            d.update(self.user.oad_params)
            d["lat"] = self.user.latitude
            d["lon"] = self.user.longitude
            if self.user.app_version:
                d["xcxVersion"] = self.user.app_version
        return d

    def request(self, api: str, data: dict | None = None, method: str | None = None,
                raw_path: str | None = None, apply_safety: bool = True) -> dict:
        key = FRONTEND_FN.get(api, api)
        path = raw_path if raw_path is not None else API_URL.get(key, api)
        url = self.base_url + path
        if method is None:
            method = "GET" if key in GET_APIS else "POST"
        header = {
            "content-type": "application/json",
            "User-Agent": DEFAULT_UA,
            "Referer": _referer(self.user.app_id),
        }
        body = self._apply_interceptors(method, path, data, header)
        # @mtfe/weapp-safety-request addCommonParams: url query + header 注入
        if apply_safety:
            sp = self.user.safety_params()
            from urllib.parse import urlencode
            q = [(k, sp[k]) for k in PARAMS_POS_URL if sp.get(k) is not None]
            if q:
                url = url + ("&" if "?" in url else "?") + urlencode(q)
            for k in PARAMS_POS_HEADER:
                if sp.get(k) is not None:
                    header.setdefault(k, sp[k])
        signed = self.signer.sign(method, url, body, header)
        if signed["method"] == "GET":
            resp = self.http.request("GET", signed["url"], headers=signed["header"],
                                     params={k: v for k, v in signed["data"].items() if v is not None})
        else:
            resp = self.http.request(signed["method"], signed["url"], headers=signed["header"],
                                     data=json.dumps(signed["data"], ensure_ascii=False).encode("utf-8"))
        try:
            result = resp.json()
        except Exception:
            return {"statusCode": resp.status_code, "text": resp.text}
        # response.use(returnData): ret===999999 -> 需要重登
        if isinstance(result, dict) and result.get("ret") == 999999:
            result["_needRelogin"] = True
        return result

    def __getattr__(self, name):
        if name in FRONTEND_FN:
            def _call(data=None, **kw):
                return self.request(name, data=data, **kw)
            return _call
        raise AttributeError(name)

    # --- 签到链路 (fetchActivityList(CHECK_IN) -> fetchSignInInfo) --------------
    def fetch_check_in(self) -> dict:
        """取签到面板: data.checkIn = {missionSecretId, isTodayCheckedIn,
        daysCheckedIn, checkInList[...]}。对应页面 onLoad 的
        fetchActivityList([QUERY_MODEL.CHECK_IN])。"""
        r = self.request("fetchActivityList", data={"queryModel": ["CHECK_IN"]})
        return ((r.get("data") or {}).get("checkIn") or {}) if isinstance(r, dict) else {}

    def sign_in(self, mission_secret_id: str | None = None, day: int | None = None) -> dict:
        """自动签到: 缺省先从 fetchActivityList 取 missionSecretId 与可签到的 day。

        **必须用 prod 域** (BASE_URL): st 域返回的 missionSecretId 在 prod 域无效,
        直接用 st 域打 check/in 会返回 ret 99 (签到失败)。
        """
        if mission_secret_id is None or day is None:
            ci = self.fetch_check_in()
            mission_secret_id = mission_secret_id or ci.get("missionSecretId")
            if day is None:
                for it in (ci.get("checkInList") or []):
                    if it.get("isCanCheckIn"):
                        day = it.get("day")
                        break
        if day is None:
            return {"ret": -1, "msg": "无可签到 day (今日已签或未到签到时间)"}
        return self.request("fetchSignInInfo",
                            data={"day": day, "missionSecretId": mission_secret_id})
