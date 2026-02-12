#!/usr/bin/env python3
"""Lighter 通用客户端库 - 可被其他模块复用"""

import asyncio
import os
import time
import requests
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
from lighter import ApiClient, AccountApi, InfoApi, OrderApi
from lighter.configuration import Configuration

LIGHTER_BASE_URL = "https://mainnet.zklighter.elliot.ai"


class LighterClient:
    """Lighter 交易所通用客户端"""

    def __init__(self, wallet_address: str = None, api_key: str = None, key_index: int = 0):
        """初始化客户端

        Args:
            wallet_address: 钱包地址
            api_key: API Key (用于需要认证的接口)
            key_index: Key 索引
        """
        self.wallet_address = wallet_address
        self.api_key = api_key
        self.key_index = key_index
        self.base_url = LIGHTER_BASE_URL
        self._account_index = None
        self._markets_cache = None

    @classmethod
    def from_config(cls, user_id: str = "eb65"):
        """从配置文件创建客户端

        Args:
            user_id: 用户ID

        Returns:
            LighterClient 实例
        """
        from utils import load_config

        config = load_config()
        user = config.get("users", {}).get(user_id, {})
        lighter_config = user.get("accounts", {}).get("lighter", {})

        wallet_address = lighter_config.get("wallet_address", "")
        env_key = f"{user_id.upper()}_LIGHTER_API_KEY"
        api_key = (
            os.getenv(env_key)
            or os.getenv("LIGHTER_API_KEY")
            or lighter_config.get("api_key", "")
        )
        key_index = lighter_config.get("key_index", 0)

        if not wallet_address:
            raise ValueError(f"用户 {user_id} 没有配置 Lighter 钱包地址")

        return cls(wallet_address=wallet_address, api_key=api_key, key_index=key_index)

    # ==================== 市场信息 ====================

    def get_markets(self) -> dict:
        """获取市场信息，返回 symbol -> market_id 映射"""
        if self._markets_cache:
            return self._markets_cache

        url = f"{self.base_url}/api/v1/orderBooks"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                markets = {}
                for market in data.get("order_books", []):
                    symbol = market.get("symbol", "")
                    market_id = market.get("market_id")
                    if symbol and market_id is not None:
                        markets[symbol] = market_id
                self._markets_cache = markets
                return markets
            return {}
        except Exception:
            return {}

    def get_market_id_to_symbol(self) -> dict:
        """获取 market_id -> symbol 映射"""
        markets = self.get_markets()
        return {v: k for k, v in markets.items()}

    async def get_market_prices_async(self) -> dict:
        """异步获取所有市场当前价格"""
        config = Configuration(host=self.base_url)
        async with ApiClient(config) as api_client:
            order_api = OrderApi(api_client)
            result = await order_api.order_book_details()
            prices = {}
            if result and result.order_book_details:
                for book in result.order_book_details:
                    if hasattr(book, 'symbol') and hasattr(book, 'last_trade_price'):
                        prices[book.symbol] = float(book.last_trade_price) if book.last_trade_price else 0
            return prices

    def get_market_prices(self) -> dict:
        """同步获取所有市场当前价格"""
        return asyncio.run(self.get_market_prices_async())

    # ==================== 账户信息 ====================

    def get_account_index(self) -> Optional[int]:
        """通过钱包地址获取 account_index"""
        if self._account_index is not None:
            return self._account_index

        if not self.wallet_address:
            return None

        url = f"{self.base_url}/api/v1/account"
        params = {"by": "l1_address", "value": self.wallet_address}
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                accounts = data.get("accounts", [])
                for acc in accounts:
                    if acc.get("account_type") == 0:
                        self._account_index = acc.get("account_index")
                        return self._account_index
                if accounts:
                    self._account_index = accounts[0].get("account_index")
                    return self._account_index
            return None
        except Exception:
            return None

    async def get_account_info_async(self):
        """异步获取账户信息"""
        if not self.wallet_address:
            return None

        config = Configuration(host=self.base_url)
        async with ApiClient(config) as api_client:
            account_api = AccountApi(api_client)
            result = await account_api.account(by="l1_address", value=self.wallet_address)
            return result

    def get_account_info(self):
        """同步获取账户信息"""
        return asyncio.run(self.get_account_info_async())

    # ==================== 资金费率 ====================

    def get_funding_history(self, market_id: int, days: int = 7) -> list:
        """查询历史资金费率

        Args:
            market_id: 市场ID
            days: 查询天数

        Returns:
            list: 资金费率记录列表
        """
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        start_time = int((now - timedelta(days=days)).timestamp())
        end_time = int(now.timestamp())

        url = f"{self.base_url}/api/v1/fundings"
        params = {
            "market_id": market_id,
            "resolution": "1h",
            "start_timestamp": start_time,
            "end_timestamp": end_time,
            "count_back": days * 24
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("fundings", [])
            else:
                print(f"获取费率失败: {resp.status_code}")
                return []
        except Exception as e:
            print(f"请求失败: {e}")
            return []

    def get_position_funding(self, market_id: int = 255, limit: int = 100) -> list:
        """查询用户持仓资金费收入 (无认证)

        Args:
            market_id: 市场ID，255表示全部
            limit: 返回记录数量

        Returns:
            list: 资金费收入记录列表
        """
        account_index = self.get_account_index()
        if account_index is None:
            return []

        url = f"{self.base_url}/api/v1/positionFunding"
        params = {
            "account_index": account_index,
            "market_id": market_id,
            "limit": limit
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("fundings", [])
            else:
                print(f"获取资金费失败: {resp.status_code}")
                return []
        except Exception as e:
            print(f"请求失败: {e}")
            return []

    def get_position_funding_with_auth(self, market_id: int = 255, days: int = 7) -> list:
        """使用认证获取用户资金费收入 (支持分页获取更多数据)

        Args:
            market_id: 市场ID，255表示全部
            days: 查询天数

        Returns:
            list: 资金费收入记录列表 (每个元素是 SimpleNamespace 对象)
        """
        if not self.api_key:
            raise ValueError("需要 API Key 才能使用认证接口")

        account_index = self.get_account_index()
        if account_index is None:
            raise ValueError("无法获取 account_index")

        from lighter.signer_client import get_signer

        # 创建 signer 并生成 auth token
        signer = get_signer()
        chain_id = 304  # mainnet

        err = signer.CreateClient(
            self.base_url.encode("utf-8"),
            self.api_key.encode("utf-8"),
            chain_id,
            self.key_index,
            account_index,
        )
        if err is not None:
            raise Exception(f"CreateClient 失败: {err.decode('utf-8')}")

        # 创建 auth token (10分钟有效)
        deadline = int(time.time()) + 10 * 60
        result = signer.CreateAuthToken(deadline, self.key_index, account_index)
        auth_token = result.str.decode("utf-8") if result.str else None
        error = result.err.decode("utf-8") if result.err else None
        if error:
            raise Exception(f"创建认证token失败: {error}")

        # 计算截止时间
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        cutoff_time = int((now - timedelta(days=days)).timestamp())

        # 分页获取所有数据
        url = f"{self.base_url}/api/v1/positionFunding"
        headers = {"Accept-Encoding": "gzip, deflate"}
        all_fundings = []
        cursor = None
        max_pages = 20

        for _ in range(max_pages):
            params = {
                "account_index": account_index,
                "market_id": market_id,
                "limit": 100,
                "auth": auth_token
            }
            if cursor:
                params["cursor"] = cursor

            resp = requests.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code != 200:
                raise Exception(f"API 错误: {resp.status_code} - {resp.text}")

            data = resp.json()
            page_fundings = data.get("position_fundings", [])

            if not page_fundings:
                break

            # 检查是否已经超出时间范围
            for f in page_fundings:
                if f.get("timestamp", 0) >= cutoff_time:
                    all_fundings.append(type('Funding', (), f)())
                else:
                    return all_fundings

            cursor = data.get("next_cursor")
            if not cursor:
                break

        return all_fundings

    # ==================== 认证相关 ====================

    def create_auth_token(self, deadline_minutes: int = 10) -> str:
        """创建认证 token

        Args:
            deadline_minutes: token 有效时间(分钟)

        Returns:
            auth token 字符串
        """
        if not self.api_key:
            raise ValueError("需要 API Key")

        account_index = self.get_account_index()
        if account_index is None:
            raise ValueError("无法获取 account_index")

        from lighter.signer_client import get_signer

        signer = get_signer()
        chain_id = 304

        err = signer.CreateClient(
            self.base_url.encode("utf-8"),
            self.api_key.encode("utf-8"),
            chain_id,
            self.key_index,
            account_index,
        )
        if err is not None:
            raise Exception(f"CreateClient 失败: {err.decode('utf-8')}")

        deadline = int(time.time()) + deadline_minutes * 60
        result = signer.CreateAuthToken(deadline, self.key_index, account_index)
        auth_token = result.str.decode("utf-8") if result.str else None
        error = result.err.decode("utf-8") if result.err else None

        if error:
            raise Exception(f"创建认证token失败: {error}")

        return auth_token
