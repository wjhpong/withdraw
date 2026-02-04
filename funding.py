#!/usr/bin/env python3
"""资金费率查询"""

import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils import run_on_ec2, select_option, SSHError

BINANCE_BASE = "https://fapi.binance.com"
ASTER_BASE = "https://fapi.asterdex.com"
HYPERLIQUID_BASE = "https://api.hyperliquid.xyz"
LIGHTER_BASE = "https://mainnet.zklighter.elliot.ai"


def get_hyperliquid_funding_history(coin: str, days: int = 7):
    """查询 Hyperliquid 历史资金费率

    Args:
        coin: 币种，如 BTC, ETH
        days: 查询天数

    Returns:
        list: 资金费率记录列表
    """
    coin = coin.upper().replace("USDT", "")

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    start_time = int((now - timedelta(days=days)).timestamp() * 1000)

    url = f"{HYPERLIQUID_BASE}/info"
    payload = {
        "type": "fundingHistory",
        "coin": coin,
        "startTime": start_time
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"API 错误: {resp.status_code}")
            return []
    except Exception as e:
        print(f"请求失败: {e}")
        return []


def get_hyperliquid_user_funding(wallet_address: str, coin: str = None, days: int = 7):
    """查询 Hyperliquid 用户实际资金费收入（本地直接调用）

    Args:
        wallet_address: 钱包地址
        coin: 币种，如 BTC, ETH（可选）
        days: 查询天数

    Returns:
        list: 资金费收入记录列表
    """
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    start_time = int((now - timedelta(days=days)).timestamp() * 1000)

    url = f"{HYPERLIQUID_BASE}/info"
    payload = {
        "type": "userFunding",
        "user": wallet_address,
        "startTime": start_time
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            records = resp.json()
            # 过滤币种
            if coin:
                records = [r for r in records if r.get("delta", {}).get("coin", "").upper() == coin.upper()]
            return records
        else:
            print(f"API 错误: {resp.status_code}")
            return []
    except Exception as e:
        print(f"请求失败: {e}")
        return []


def show_hyperliquid_funding_history(user: str = None):
    """显示 Hyperliquid 历史资金费率和实际收入（本地直接调用）"""
    import json

    # 从本地配置获取钱包地址
    config = json.load(open("config.json"))

    # 获取用户的 hyperliquid 配置
    if not user:
        print("未指定用户")
        return

    user_data = config.get("users", {}).get(user, {})
    hl_config = user_data.get("accounts", {}).get("hyperliquid", {})
    wallet_address = hl_config.get("wallet_address")

    if not wallet_address:
        print(f"用户 {user} 没有配置 Hyperliquid 钱包地址")
        return

    symbol = input("\n请输入币种 (如 BTC, ETH, 直接回车查询全部): ").strip().upper()

    days_str = input("查询天数 (默认7天): ").strip()
    days = int(days_str) if days_str.isdigit() else 7

    # 移除 USDT 后缀
    coin = symbol.replace("USDT", "") if symbol else ""

    print(f"\n正在查询资金费数据...")

    # 本地直接调用 API 获取资金费收入
    try:
        raw_records = get_hyperliquid_user_funding(wallet_address, coin, days)

        if not raw_records:
            print("没有资金费收入记录")
            return

        # 转换数据格式
        income_records = []
        for r in raw_records:
            delta = r.get("delta", {})
            income_records.append({
                "coin": delta.get("coin", ""),
                "usdc": float(delta.get("usdc", 0)),
                "time": int(r.get("time", 0))
            })

    except Exception as e:
        print(f"查询失败: {e}")
        return

    # 获取费率数据（如果指定了币种）
    rate_data = {}
    if coin:
        rate_records = get_hyperliquid_funding_history(coin, days)
        for record in rate_records:
            funding_time = int(record.get("time", 0))
            rate = float(record.get("fundingRate", 0))
            dt = datetime.fromtimestamp(funding_time / 1000, tz=ZoneInfo("Asia/Shanghai"))
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in rate_data:
                rate_data[date_str] = {"rates": [], "sum": 0}
            rate_data[date_str]["rates"].append(rate)
            rate_data[date_str]["sum"] += rate

    # 按币种和日期分组统计
    coin_daily_stats = {}
    for record in income_records:
        record_coin = record.get("coin", "")
        income = float(record.get("usdc", 0))
        income_time = int(record.get("time", 0))

        dt = datetime.fromtimestamp(income_time / 1000, tz=ZoneInfo("Asia/Shanghai"))
        date_str = dt.strftime("%Y-%m-%d")

        if record_coin not in coin_daily_stats:
            coin_daily_stats[record_coin] = {}

        if date_str not in coin_daily_stats[record_coin]:
            coin_daily_stats[record_coin][date_str] = {"incomes": [], "sum": 0}

        coin_daily_stats[record_coin][date_str]["incomes"].append(income)
        coin_daily_stats[record_coin][date_str]["sum"] += income

    # 显示结果
    print(f"\n{'=' * 80}")
    print(f"  Hyperliquid 资金费收入 (最近 {days} 天)")
    print("=" * 80)

    grand_total = 0

    for c in sorted(coin_daily_stats.keys()):
        daily_stats = coin_daily_stats[c]

        print(f"\n {c}")
        print("-" * 75)

        # 如果有费率数据，显示费率列
        if rate_data and c == coin:
            print(f"{'日期':<12} {'次数':<6} {'累计费率':<12} {'年化费率':<12} {'收入(USDC)':<12}")
        else:
            print(f"{'日期':<12} {'结算次数':<8} {'收入(USDC)':<15}")
        print("-" * 75)

        coin_total = 0
        total_rate = 0
        for date_str in sorted(daily_stats.keys(), reverse=True):
            stats = daily_stats[date_str]
            count = len(stats["incomes"])
            daily_sum = stats["sum"]
            coin_total += daily_sum

            if rate_data and c == coin and date_str in rate_data:
                daily_rate = rate_data[date_str]["sum"]
                total_rate += daily_rate
                annual_rate = daily_rate * 365 * 100
                print(f"{date_str:<12} {count:<6} {daily_rate*100:>+.4f}%     {annual_rate:>+.2f}%      {daily_sum:>+,.2f}")
            else:
                print(f"{date_str:<12} {count:<8} {daily_sum:>+,.4f}")

        print("-" * 75)

        if rate_data and c == coin:
            avg_daily_rate = total_rate / len(daily_stats) if daily_stats else 0
            annual_avg = avg_daily_rate * 365 * 100
            print(f"{'小计':<12} {'':<6} {total_rate*100:>+.4f}%     {annual_avg:>+.2f}%      {coin_total:>+,.2f}")
        else:
            print(f"{'小计':<12} {'':<8} {coin_total:>+,.4f}")

        grand_total += coin_total

    print(f"\n{'=' * 80}")
    print(f"总收入: {grand_total:>+,.4f} USDC")
    avg_daily = grand_total / days if days > 0 else 0
    print(f"日均收入: {avg_daily:>+,.4f} USDC")
    print(f"年化收入: {avg_daily * 365:>+,.2f} USDC")
    print("=" * 80)


def get_aster_funding_history(symbol: str, days: int = 7):
    """查询 Aster 历史资金费率

    Args:
        symbol: 交易对，如 ASTERUSDT
        days: 查询天数

    Returns:
        list: 资金费率记录列表
    """
    symbol = symbol.upper()
    if not symbol.endswith("USDT"):
        symbol = symbol + "USDT"

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    start_time = int((now - timedelta(days=days)).timestamp() * 1000)

    url = f"{ASTER_BASE}/fapi/v3/fundingRate"
    params = {
        "symbol": symbol,
        "startTime": start_time,
        "limit": 1000
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"API 错误: {resp.status_code}")
            return []
    except Exception as e:
        print(f"请求失败: {e}")
        return []


def show_aster_funding_history(exchange: str = None):
    """显示 Aster 历史资金费率和实际收入"""
    import json

    symbol = input("\n请输入交易对 (如 ASTER, ASTERUSDT, 直接回车查询全部): ").strip().upper()

    days_str = input("查询天数 (默认7天): ").strip()
    days = int(days_str) if days_str.isdigit() else 7

    if symbol and not symbol.endswith("USDT"):
        symbol = symbol + "USDT"

    print(f"\n正在查询资金费数据...")

    # 从 EC2 获取实际资金费收入
    try:
        if symbol:
            output = run_on_ec2(f"aster_funding_income {exchange} {symbol} {days}")
        else:
            output = run_on_ec2(f"aster_funding_income {exchange} \"\" {days}")

        income_records = json.loads(output.strip())

        if isinstance(income_records, dict) and "error" in income_records:
            print(f"查询失败: {income_records['error']}")
            return

        if not income_records:
            print("没有资金费收入记录")
            return

    except Exception as e:
        print(f"查询失败: {e}")
        return

    # 获取费率数据（如果指定了交易对）
    rate_data = {}
    if symbol:
        rate_records = get_aster_funding_history(symbol, days)
        for record in rate_records:
            funding_time = int(record.get("fundingTime", 0))
            rate = float(record.get("fundingRate", 0))
            dt = datetime.fromtimestamp(funding_time / 1000, tz=ZoneInfo("Asia/Shanghai"))
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in rate_data:
                rate_data[date_str] = {"rates": [], "sum": 0}
            rate_data[date_str]["rates"].append(rate)
            rate_data[date_str]["sum"] += rate

    # 按交易对和日期分组统计
    symbol_daily_stats = {}
    for record in income_records:
        sym = record.get("symbol", "")
        income = float(record.get("income", 0))
        income_time = int(record.get("time", 0))

        dt = datetime.fromtimestamp(income_time / 1000, tz=ZoneInfo("Asia/Shanghai"))
        date_str = dt.strftime("%Y-%m-%d")

        if sym not in symbol_daily_stats:
            symbol_daily_stats[sym] = {}

        if date_str not in symbol_daily_stats[sym]:
            symbol_daily_stats[sym][date_str] = {"incomes": [], "sum": 0}

        symbol_daily_stats[sym][date_str]["incomes"].append(income)
        symbol_daily_stats[sym][date_str]["sum"] += income

    # 显示结果
    print(f"\n{'=' * 80}")
    print(f"  资金费收入 (最近 {days} 天) - Aster")
    print("=" * 80)

    grand_total = 0

    for sym in sorted(symbol_daily_stats.keys()):
        daily_stats = symbol_daily_stats[sym]

        print(f"\n📊 {sym}")
        print("-" * 75)

        # 如果有费率数据，显示费率列
        if rate_data and sym == symbol:
            print(f"{'日期':<12} {'次数':<6} {'累计费率':<12} {'年化费率':<12} {'收入(USDT)':<12}")
        else:
            print(f"{'日期':<12} {'结算次数':<8} {'收入(USDT)':<15}")
        print("-" * 75)

        sym_total = 0
        total_rate = 0
        for date_str in sorted(daily_stats.keys(), reverse=True):
            stats = daily_stats[date_str]
            count = len(stats["incomes"])
            daily_sum = stats["sum"]
            sym_total += daily_sum

            if rate_data and sym == symbol and date_str in rate_data:
                daily_rate = rate_data[date_str]["sum"]
                total_rate += daily_rate
                annual_rate = daily_rate * 365 * 100
                print(f"{date_str:<12} {count:<6} {daily_rate*100:>+.4f}%     {annual_rate:>+.2f}%      {daily_sum:>+,.2f}")
            else:
                print(f"{date_str:<12} {count:<8} {daily_sum:>+,.4f}")

        print("-" * 75)

        if rate_data and sym == symbol:
            avg_daily_rate = total_rate / len(daily_stats) if daily_stats else 0
            annual_avg = avg_daily_rate * 365 * 100
            print(f"{'小计':<12} {'':<6} {total_rate*100:>+.4f}%     {annual_avg:>+.2f}%      {sym_total:>+,.2f}")
        else:
            print(f"{'小计':<12} {'':<8} {sym_total:>+,.4f}")

        grand_total += sym_total

    print(f"\n{'=' * 80}")
    print(f"💰 总收入: {grand_total:>+,.4f} USDT")
    avg_daily = grand_total / days if days > 0 else 0
    print(f"📈 日均收入: {avg_daily:>+,.4f} USDT")
    print(f"📅 年化收入: {avg_daily * 365:>+,.2f} USDT")
    print("=" * 80)


def get_binance_funding_history(symbol: str, days: int = 7):
    """查询 Binance 历史资金费率

    Args:
        symbol: 交易对，如 BTCUSDT
        days: 查询天数

    Returns:
        list: 资金费率记录列表
    """
    symbol = symbol.upper()
    if not symbol.endswith("USDT"):
        symbol = symbol + "USDT"

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    start_time = int((now - timedelta(days=days)).timestamp() * 1000)

    url = f"{BINANCE_BASE}/fapi/v1/fundingRate"
    params = {
        "symbol": symbol,
        "startTime": start_time,
        "limit": 1000
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"API 错误: {resp.status_code}")
            return []
    except Exception as e:
        print(f"请求失败: {e}")
        return []


def show_binance_funding_history(exchange: str = None):
    """显示 Binance 历史资金费率和实际收入

    Args:
        exchange: EC2 交易所 key (如 binance, binance3)
    """
    import json

    symbol = input("\n请输入交易对 (如 BTC, BTCUSDT, 直接回车查询全部): ").strip().upper()

    days_str = input("查询天数 (默认7天): ").strip()
    days = int(days_str) if days_str.isdigit() else 7

    if symbol and not symbol.endswith("USDT"):
        symbol = symbol + "USDT"

    print(f"\n正在查询资金费数据...")

    # 从 EC2 获取实际资金费收入
    try:
        if symbol:
            output = run_on_ec2(f"binance_funding_income {exchange} {symbol} {days}")
        else:
            output = run_on_ec2(f"binance_funding_income {exchange} \"\" {days}")

        income_records = json.loads(output.strip())

        if isinstance(income_records, dict) and "error" in income_records:
            print(f"查询失败: {income_records['error']}")
            return

        if not income_records:
            print("没有资金费收入记录")
            return

    except Exception as e:
        print(f"查询失败: {e}")
        return

    # 获取费率数据（如果指定了交易对）
    rate_data = {}
    if symbol:
        rate_records = get_binance_funding_history(symbol, days)
        for record in rate_records:
            funding_time = int(record.get("fundingTime", 0))
            rate = float(record.get("fundingRate", 0))
            dt = datetime.fromtimestamp(funding_time / 1000, tz=ZoneInfo("Asia/Shanghai"))
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in rate_data:
                rate_data[date_str] = {"rates": [], "sum": 0}
            rate_data[date_str]["rates"].append(rate)
            rate_data[date_str]["sum"] += rate

    # 按交易对和日期分组统计
    symbol_daily_stats = {}
    for record in income_records:
        sym = record.get("symbol", "")
        income = float(record.get("income", 0))
        income_time = int(record.get("time", 0))

        dt = datetime.fromtimestamp(income_time / 1000, tz=ZoneInfo("Asia/Shanghai"))
        date_str = dt.strftime("%Y-%m-%d")

        if sym not in symbol_daily_stats:
            symbol_daily_stats[sym] = {}

        if date_str not in symbol_daily_stats[sym]:
            symbol_daily_stats[sym][date_str] = {"incomes": [], "sum": 0}

        symbol_daily_stats[sym][date_str]["incomes"].append(income)
        symbol_daily_stats[sym][date_str]["sum"] += income

    # 显示结果
    print(f"\n{'=' * 80}")
    print(f"  资金费收入 (最近 {days} 天)")
    print("=" * 80)

    grand_total = 0

    for sym in sorted(symbol_daily_stats.keys()):
        daily_stats = symbol_daily_stats[sym]

        print(f"\n📊 {sym}")
        print("-" * 75)

        # 如果有费率数据，显示费率列
        if rate_data and sym == symbol:
            print(f"{'日期':<12} {'次数':<6} {'累计费率':<12} {'年化费率':<12} {'收入(USDT)':<12}")
        else:
            print(f"{'日期':<12} {'结算次数':<8} {'收入(USDT)':<15}")
        print("-" * 75)

        sym_total = 0
        total_rate = 0
        for date_str in sorted(daily_stats.keys(), reverse=True):
            stats = daily_stats[date_str]
            count = len(stats["incomes"])
            daily_sum = stats["sum"]
            sym_total += daily_sum

            if rate_data and sym == symbol and date_str in rate_data:
                daily_rate = rate_data[date_str]["sum"]
                total_rate += daily_rate
                annual_rate = daily_rate * 365 * 100
                print(f"{date_str:<12} {count:<6} {daily_rate*100:>+.4f}%     {annual_rate:>+.2f}%      {daily_sum:>+,.2f}")
            else:
                print(f"{date_str:<12} {count:<8} {daily_sum:>+,.4f}")

        print("-" * 75)

        if rate_data and sym == symbol:
            avg_daily_rate = total_rate / len(daily_stats) if daily_stats else 0
            annual_avg = avg_daily_rate * 365 * 100
            print(f"{'小计':<12} {'':<6} {total_rate*100:>+.4f}%     {annual_avg:>+.2f}%      {sym_total:>+,.2f}")
        else:
            print(f"{'小计':<12} {'':<8} {sym_total:>+,.4f}")

        grand_total += sym_total

    print(f"\n{'=' * 80}")
    print(f"💰 总收入: {grand_total:>+,.4f} USDT")
    avg_daily = grand_total / days if days > 0 else 0
    print(f"📈 日均收入: {avg_daily:>+,.4f} USDT")
    print(f"📅 年化收入: {avg_daily * 365:>+,.2f} USDT")
    print("=" * 80)


def get_lighter_markets():
    """获取 Lighter 市场信息，返回 symbol -> market_id 映射"""
    url = f"{LIGHTER_BASE}/api/v1/orderBooks"
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
            return markets
        return {}
    except Exception:
        return {}


def get_lighter_account_index(wallet_address: str):
    """通过钱包地址获取 account_index"""
    url = f"{LIGHTER_BASE}/api/v1/account"
    params = {
        "by": "l1_address",
        "value": wallet_address
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # 返回主账户的 index
            accounts = data.get("accounts", [])
            for acc in accounts:
                if acc.get("account_type") == 0:
                    return acc.get("account_index")
            # 如果没有主账户，返回第一个
            if accounts:
                return accounts[0].get("account_index")
        return None
    except Exception:
        return None


def get_lighter_funding_history(market_id: int, days: int = 7):
    """查询 Lighter 历史资金费率

    Args:
        market_id: 市场ID
        days: 查询天数

    Returns:
        list: 资金费率记录列表
    """
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    start_time = int((now - timedelta(days=days)).timestamp())
    end_time = int(now.timestamp())

    url = f"{LIGHTER_BASE}/api/v1/fundings"
    params = {
        "market_id": market_id,
        "resolution": "1h",
        "start_timestamp": start_time,
        "end_timestamp": end_time,
        "count_back": days * 24  # 每小时一次
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


def get_lighter_position_funding(account_index: int, market_id: int = 255, limit: int = 100):
    """查询 Lighter 用户持仓资金费收入

    Args:
        account_index: 账户索引
        market_id: 市场ID，255表示全部
        limit: 返回记录数量

    Returns:
        list: 资金费收入记录列表
    """
    url = f"{LIGHTER_BASE}/api/v1/positionFunding"
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



def _get_lighter_position_funding_with_auth(account_index: int, api_secret: str, key_index: int, market_id: int = 255, days: int = 7):
    """使用认证获取用户资金费收入 (使用 requests 避免 brotli 问题，支持分页)"""
    import time
    from lighter.signer_client import get_signer

    # 创建底层 signer 并生成 auth token
    signer = get_signer()
    chain_id = 304  # mainnet

    # 创建 client (传入所有必需参数，api_secret 是私钥)
    err = signer.CreateClient(
        LIGHTER_BASE.encode("utf-8"),
        api_secret.encode("utf-8"),
        chain_id,
        key_index,
        account_index,
    )
    if err is not None:
        raise Exception(f"CreateClient 失败: {err.decode('utf-8')}")

    # 计算 deadline (10分钟后)
    deadline = int(time.time()) + 10 * 60

    # 创建 auth token
    result = signer.CreateAuthToken(deadline, key_index, account_index)
    auth_token = result.str.decode("utf-8") if result.str else None
    error = result.err.decode("utf-8") if result.err else None
    if error:
        raise Exception(f"创建认证token失败: {error}")

    # 计算截止时间
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    cutoff_time = int((now - timedelta(days=days)).timestamp())

    # 分页获取所有数据
    url = f"{LIGHTER_BASE}/api/v1/positionFunding"
    headers = {"Accept-Encoding": "gzip, deflate"}
    all_fundings = []
    cursor = None
    max_pages = 20  # 防止无限循环

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
                # 数据按时间倒序，遇到超出范围的就停止
                return type('Result', (), {'fundings': all_fundings})()

        # 获取下一页 cursor
        cursor = data.get("next_cursor")
        if not cursor:
            break

    return type('Result', (), {'fundings': all_fundings})()


def show_lighter_funding_history(user: str = "eb65"):
    """显示 Lighter 历史资金费率和实际收入"""
    import json

    # 获取市场信息
    print("\n正在获取市场信息...")
    markets = get_lighter_markets()
    if not markets:
        print("无法获取市场信息")
        return

    # 构建 market_id -> symbol 映射
    market_id_to_symbol = {v: k for k, v in markets.items()}

    # 显示可用市场（按字母排序，优先显示常见币种）
    common_coins = ["BTC", "ETH", "SOL", "DOGE", "XRP", "SUI", "PEPE", "WIF", "LINK", "AVAX", "LIT"]
    available_symbols = sorted(markets.keys())
    # 将常见币种放前面
    display_order = [c for c in common_coins if c in available_symbols]
    display_order += [s for s in available_symbols if s not in common_coins][:5]
    print(f"可用市场: {', '.join(display_order)}...")

    symbol = input("\n请输入币种 (如 BTC, ETH, LIT, 直接回车查询全部): ").strip().upper()

    days_str = input("查询天数 (默认7天): ").strip()
    days = int(days_str) if days_str.isdigit() else 7

    # 清理输入
    coin = symbol.replace("USDT", "").replace("_PERP", "").replace("/USDC", "") if symbol else ""
    target_market_id = markets.get(coin) if coin else 255  # 255 表示全部

    if coin and target_market_id is None:
        print(f"未找到 {coin} 市场")
        # 尝试模糊匹配
        matches = [s for s in markets.keys() if coin in s.upper()]
        if matches:
            print(f"你是否想查询: {', '.join(matches[:5])}")
        return

    # 尝试获取用户实际收入
    income_records = []
    account_index = None
    try:
        config = json.load(open("config.json"))
        user_data = config.get("users", {}).get(user, {})
        lighter_config = user_data.get("accounts", {}).get("lighter", {})
        wallet_address = lighter_config.get("wallet_address")
        api_secret = lighter_config.get("api_secret")  # 私钥，用于签名
        key_index = lighter_config.get("key_index", 0)

        if wallet_address and api_secret:
            # 获取 account_index
            account_index = get_lighter_account_index(wallet_address)
            if account_index is not None:
                print("\n正在获取实际资金费收入...")
                try:
                    result = _get_lighter_position_funding_with_auth(
                        account_index, api_secret, key_index, target_market_id, days=days
                    )
                    if result and hasattr(result, 'fundings'):
                        income_records = result.fundings or []
                except Exception as e:
                    print(f"获取收入失败: {e}")
    except Exception:
        pass

    # 如果指定了币种，获取费率数据
    rate_records = []
    if coin and target_market_id != 255:
        print(f"正在查询 {coin} 历史费率...")
        rate_records = get_lighter_funding_history(target_market_id, days)

    # 显示结果
    if coin and rate_records:
        show_lighter_rate_and_income(coin, rate_records, income_records, market_id_to_symbol, days)
    elif income_records:
        show_lighter_all_income(income_records, market_id_to_symbol, days)
    elif coin:
        print("没有费率数据")
    else:
        print("没有资金费收入记录")


def show_lighter_all_income(income_records: list, market_id_to_symbol: dict, days: int):
    """显示所有币种的资金费收入"""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    cutoff_time = int((now - timedelta(days=days)).timestamp())

    # 按币种和日期分组
    coin_daily_stats = {}
    for record in income_records:
        timestamp = int(record.timestamp) if hasattr(record, 'timestamp') else int(record.get("timestamp", 0))
        if timestamp < cutoff_time:
            continue

        change = float(record.change) if hasattr(record, 'change') else float(record.get("change", 0))
        market_id = record.market_id if hasattr(record, 'market_id') else record.get("market_id")
        coin = market_id_to_symbol.get(market_id, f"MARKET_{market_id}")

        dt = datetime.fromtimestamp(timestamp, tz=ZoneInfo("Asia/Shanghai"))
        date_str = dt.strftime("%Y-%m-%d")

        if coin not in coin_daily_stats:
            coin_daily_stats[coin] = {}
        if date_str not in coin_daily_stats[coin]:
            coin_daily_stats[coin][date_str] = {"sum": 0, "count": 0}

        coin_daily_stats[coin][date_str]["sum"] += change
        coin_daily_stats[coin][date_str]["count"] += 1

    if not coin_daily_stats:
        print("没有资金费收入记录")
        return

    print(f"\n{'=' * 70}")
    print(f"  Lighter 资金费收入 (最近 {days} 天)")
    print("=" * 70)

    grand_total = 0

    for coin in sorted(coin_daily_stats.keys()):
        daily_stats = coin_daily_stats[coin]
        print(f"\n {coin}")
        print("-" * 65)
        print(f"{'日期':<12} {'结算次数':<8} {'收入(USD)':<15}")
        print("-" * 65)

        coin_total = 0
        for date_str in sorted(daily_stats.keys(), reverse=True):
            stats = daily_stats[date_str]
            count = stats["count"]
            daily_sum = stats["sum"]
            coin_total += daily_sum
            print(f"{date_str:<12} {count:<8} ${daily_sum:>+.4f}")

        print("-" * 65)
        print(f"{'小计':<12} {'':<8} ${coin_total:>+.4f}")
        grand_total += coin_total

    print(f"\n{'=' * 70}")
    print(f"总收入: ${grand_total:>+.4f}")
    avg_daily = grand_total / days if days > 0 else 0
    print(f"日均收入: ${avg_daily:>+.4f}")
    print(f"年化收入: ${avg_daily * 365:>+.2f}")
    print("=" * 70)


def show_lighter_rate_and_income(coin: str, rate_records: list, income_records: list, market_id_to_symbol: dict, days: int):
    """显示费率和实际收入数据"""
    # 处理费率数据
    rate_data = {}
    for record in rate_records:
        funding_time = int(record.get("timestamp", 0))
        rate = float(record.get("rate", 0))
        if funding_time > 0:
            dt = datetime.fromtimestamp(funding_time, tz=ZoneInfo("Asia/Shanghai"))
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in rate_data:
                rate_data[date_str] = {"rates": [], "sum": 0, "count": 0}
            rate_data[date_str]["rates"].append(rate)
            rate_data[date_str]["sum"] += rate
            rate_data[date_str]["count"] += 1

    # 处理收入数据
    income_data = {}
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    cutoff_time = int((now - timedelta(days=days)).timestamp())

    for record in income_records:
        # SDK 返回的是对象
        timestamp = int(record.timestamp) if hasattr(record, 'timestamp') else int(record.get("timestamp", 0))
        if timestamp < cutoff_time:
            continue

        change = float(record.change) if hasattr(record, 'change') else float(record.get("change", 0))
        market_id = record.market_id if hasattr(record, 'market_id') else record.get("market_id")

        # 检查是否是目标币种
        record_symbol = market_id_to_symbol.get(market_id, "")
        if record_symbol != coin:
            continue

        dt = datetime.fromtimestamp(timestamp, tz=ZoneInfo("Asia/Shanghai"))
        date_str = dt.strftime("%Y-%m-%d")
        if date_str not in income_data:
            income_data[date_str] = {"sum": 0, "count": 0}
        income_data[date_str]["sum"] += change
        income_data[date_str]["count"] += 1

    if not rate_data:
        print("没有费率数据")
        return

    has_income = bool(income_data)

    print(f"\n{'=' * 70}")
    print(f"  {coin} 历史费率 (最近 {days} 天)")
    print("=" * 70)

    if has_income:
        print(f"{'日期':<12} {'次数':<6} {'累计费率':<12} {'年化费率':<12} {'实际收入':<12}")
    else:
        print(f"{'日期':<12} {'次数':<6} {'累计费率':<12} {'年化费率':<12}")
    print("-" * 65)

    total_rate = 0
    total_income = 0
    for date_str in sorted(rate_data.keys(), reverse=True):
        stats = rate_data[date_str]
        count = stats["count"]
        daily_rate = stats["sum"]
        total_rate += daily_rate
        annual_rate = daily_rate * 365

        if has_income:
            daily_income = income_data.get(date_str, {}).get("sum", 0)
            total_income += daily_income
            print(f"{date_str:<12} {count:<6} {daily_rate:>+.4f}%     {annual_rate:>+.2f}%      ${daily_income:>+.2f}")
        else:
            print(f"{date_str:<12} {count:<6} {daily_rate:>+.4f}%     {annual_rate:>+.2f}%")

    print("-" * 65)
    avg_daily_rate = total_rate / len(rate_data) if rate_data else 0
    annual_avg = avg_daily_rate * 365

    if has_income:
        avg_daily_income = total_income / len(rate_data) if rate_data else 0
        print(f"{'平均':<12} {'':<6} {avg_daily_rate:>+.4f}%     {annual_avg:>+.2f}%      ${avg_daily_income:>+.2f}")
        print("=" * 70)
        print(f"总收入: ${total_income:>+.2f}")
        print(f"年化收入: ${avg_daily_income * 365:>+.2f}")
    else:
        print(f"{'平均':<12} {'':<6} {avg_daily_rate:>+.4f}%     {annual_avg:>+.2f}%")
    print("=" * 70)


def show_funding_rate(exchange: str = None):
    """查询资金费率"""
    if not exchange:
        # 选择交易所
        exchanges = [
            ("bybit", "Bybit"),
            ("hyperliquid", "Hyperliquid"),
        ]
        display_names = [n for _, n in exchanges]
        idx = select_option("选择交易所:", display_names, allow_back=True)
        if idx == -1:
            return
        exchange = exchanges[idx][0]

    # 输入交易对
    symbol = input("\n请输入交易对 (如 BTC, ETH, 直接回车查询全部热门): ").strip().upper()

    print(f"\n正在查询 {exchange.upper()} 资金费率...")

    try:
        if symbol:
            output = run_on_ec2(f"funding_rate {exchange} {symbol}")
        else:
            output = run_on_ec2(f"funding_rate {exchange}")
        print(output)
    except SSHError as e:
        print(f"❌ 查询资金费率失败: {e}")


def show_funding_rate_menu():
    """资金费率查询菜单"""
    while True:
        action = select_option("资金费率查询:", [
            "Bybit 资金费率",
            "Hyperliquid 资金费率",
            "返回"
        ])

        if action == 0:
            show_funding_rate("bybit")
        elif action == 1:
            show_funding_rate("hyperliquid")
        else:
            break

        input("\n按回车继续...")


def get_funding_income_binance(exchange: str, days: int = 7):
    """获取 Binance 资金费收入数据（不显示，仅返回数据）"""
    import json
    try:
        output = run_on_ec2(f'binance_funding_income {exchange} "" {days}')
        income_records = json.loads(output.strip())
        if isinstance(income_records, dict) and "error" in income_records:
            return None, income_records.get("error")
        total = sum(float(r.get("income", 0)) for r in income_records)
        return total, None
    except Exception as e:
        return None, str(e)


def get_funding_income_aster(exchange: str, days: int = 7):
    """获取 Aster 资金费收入数据（不显示，仅返回数据）"""
    import json
    try:
        output = run_on_ec2(f'aster_funding_income {exchange} "" {days}')
        income_records = json.loads(output.strip())
        if isinstance(income_records, dict) and "error" in income_records:
            return None, income_records.get("error")
        total = sum(float(r.get("income", 0)) for r in income_records)
        return total, None
    except Exception as e:
        return None, str(e)


def get_funding_income_hyperliquid(wallet_address: str, days: int = 7):
    """获取 Hyperliquid 资金费收入数据（不显示，仅返回数据）"""
    try:
        records = get_hyperliquid_user_funding(wallet_address, None, days)
        if not records:
            return 0.0, None
        total = sum(float(r.get("delta", {}).get("usdc", 0)) for r in records)
        return total, None
    except Exception as e:
        return None, str(e)


def show_combined_funding_summary(user_id: str):
    """显示用户所有交易所的综合费率收益汇总"""
    import json
    from utils import load_config, get_user_accounts, get_ec2_exchange_key, get_exchange_base

    config = load_config()
    user_data = config.get("users", {}).get(user_id, {})
    user_name = user_data.get("name", user_id)
    accounts = user_data.get("accounts", {})

    if not accounts:
        print(f"\n用户 {user_name} 没有配置任何交易所账号")
        return

    days_str = input("\n查询天数 (默认7天): ").strip()
    days = int(days_str) if days_str.isdigit() else 7

    print(f"\n正在查询所有交易所的资金费收益...")
    print("=" * 70)
    print(f"  {user_name} - 综合费率收益汇总 (最近 {days} 天)")
    print("=" * 70)

    results = []
    grand_total = 0
    currency_totals = {}  # 按币种汇总

    for account_id, account_info in accounts.items():
        exchange_type = account_info.get("exchange", account_id)
        exchange_base = get_exchange_base(exchange_type)
        exchange_name = exchange_type.upper()

        income = None
        error = None
        currency = "USDT"

        print(f"\n  正在查询 {exchange_name}...", end=" ", flush=True)

        if exchange_base == "binance":
            ec2_key = get_ec2_exchange_key(user_id, account_id)
            income, error = get_funding_income_binance(ec2_key, days)
        elif exchange_base == "aster":
            ec2_key = get_ec2_exchange_key(user_id, account_id)
            income, error = get_funding_income_aster(ec2_key, days)
        elif exchange_base == "hyperliquid":
            wallet_address = account_info.get("wallet_address")
            if wallet_address:
                income, error = get_funding_income_hyperliquid(wallet_address, days)
                currency = "USDC"
            else:
                error = "未配置钱包地址"
        elif exchange_base == "lighter":
            # Lighter 的资金费直接计入持仓盈亏，无单独记录
            error = "费用计入盈亏"
        elif exchange_base in ("bybit", "bitget", "gate"):
            # 这些交易所需要添加 API 支持
            error = "待开发"
        else:
            error = "不支持"

        if income is not None:
            print(f"{income:+,.2f} {currency}")
            results.append({
                "exchange": exchange_name,
                "income": income,
                "currency": currency,
                "error": None
            })
            grand_total += income
            currency_totals[currency] = currency_totals.get(currency, 0) + income
        else:
            print(f"跳过 ({error})")
            results.append({
                "exchange": exchange_name,
                "income": None,
                "currency": currency,
                "error": error
            })

    # 显示汇总结果
    print("\n" + "=" * 70)
    print(f"{'交易所':<15} {'收入':<20} {'状态':<15}")
    print("-" * 70)

    for r in results:
        if r["income"] is not None:
            income_str = f"{r['income']:+,.4f} {r['currency']}"
            status = "OK"
        else:
            income_str = "-"
            status = r["error"] or "失败"
        print(f"{r['exchange']:<15} {income_str:<20} {status:<15}")

    print("-" * 70)

    # 按币种显示小计
    for currency, total in currency_totals.items():
        avg_daily = total / days if days > 0 else 0
        print(f"\n{currency} 汇总:")
        print(f"  总收入: {total:+,.4f} {currency}")
        print(f"  日均收入: {avg_daily:+,.4f} {currency}")
        print(f"  年化收入: {avg_daily * 365:+,.2f} {currency}")

    print("=" * 70)
