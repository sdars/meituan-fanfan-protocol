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


@dataclass
class UserState:
    """stores/userInfo.js 的运行时字段 (业务请求需要的凭据/参数)。"""

    token: str | None = None           # mt-c-token
    device_id: str | None = None       # deviceid
    latitude: float = 0.0
    longitude: float = 0.0
    app_version: str = "0.0.0"         # xcxVersion
    oad_params: dict = field(default_factory=dict)


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
                raw_path: str | None = None) -> dict:
        key = FRONTEND_FN.get(api, api)
        path = raw_path if raw_path is not None else API_URL.get(key, api)
        url = self.base_url + path
        if method is None:
            method = "GET" if key in GET_APIS else "POST"
        header = {"content-type": "application/json"}
        body = self._apply_interceptors(method, path, data, header)
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
