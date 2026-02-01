#!/usr/bin/env python3
"""资金费率查询"""

import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils import run_on_ec2, select_option, SSHError

BINANCE_BASE = "https://fapi.binance.com"
ASTER_BASE = "https://fapi.asterdex.com"
HYPERLIQUID_BASE = "https://api.hyperliquid.xyz"


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
