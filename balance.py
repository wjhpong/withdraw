#!/usr/bin/env python3
"""余额查询"""

import requests
from utils import run_on_ec2, select_option, select_exchange, get_exchange_base, get_exchange_display_name

# 稳定币列表，价格视为 1 USD
STABLECOINS = ['USDT', 'USDC', 'USD1', 'BUSD', 'TUSD', 'FDUSD']

# 最小显示价值 (USD)
MIN_DISPLAY_VALUE = 10


def get_coin_price(coin: str) -> float:
    """获取币种对 USDT 的价格，稳定币返回 1"""
    coin = coin.upper()
    if coin in STABLECOINS:
        return 1.0

    try:
        # 尝试 COIN/USDT 交易对
        resp = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT",
            timeout=5
        )
        if resp.status_code == 200:
            return float(resp.json()['price'])

        # 尝试 COIN/BUSD
        resp = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={coin}BUSD",
            timeout=5
        )
        if resp.status_code == 200:
            return float(resp.json()['price'])
    except:
        pass

    return 0.0


def filter_by_value(balances: dict, min_value: float = MIN_DISPLAY_VALUE) -> dict:
    """过滤掉市值小于指定美元价值的资产"""
    result = {}
    for coin, amount in balances.items():
        price = get_coin_price(coin)
        value = amount * price
        if value >= min_value:
            result[coin] = amount
    return result


def show_balance(exchange: str = None):
    """查询余额"""
    if not exchange:
        exchange = select_exchange()
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 余额...")

    # EC2 上的 balance 命令已经格式化好输出，直接显示
    output = run_on_ec2(f"balance {exchange}")

    # 移除 EC2 返回的 "正在查询..." 行，避免重复显示
    lines = output.strip().split('\n')
    for line in lines:
        if '正在查询' not in line:
            print(line)


def show_pm_ratio(exchange: str = None):
    """查询统一保证金率"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 统一保证金率...")

    output = run_on_ec2(f"pm_ratio {exchange}")
    print(output)


def show_gate_subaccounts():
    """查询 Gate.io 子账户资产"""
    print("\n正在查询 Gate.io 子账户...")
    output = run_on_ec2("gate_subaccounts")
    
    # 移除 EC2 返回的 "正在查询..." 行
    lines = output.strip().split('\n')
    for line in lines:
        if '正在查询' not in line:
            print(line)


def get_coin_balance(exchange: str, coin: str, account_type: str = "SPOT") -> str:
    """查询指定币种余额
    
    Args:
        exchange: 交易所
        coin: 币种
        account_type: 账户类型 (SPOT/UNIFIED/FUND/EARN)
    """
    exchange_base = get_exchange_base(exchange)
    coin_upper = coin.upper()
    
    if exchange_base == "bybit":
        if account_type == "UNIFIED":
            output = run_on_ec2(f"account_balance bybit UNIFIED {coin}").strip()
            if output and not output.startswith("用法") and not output.startswith("未知"):
                try:
                    return str(float(output))
                except ValueError:
                    pass
            return "0"
        else:
            # 资金账户
            fund_output = run_on_ec2(f"balance {exchange}")
            for line in fund_output.split('\n'):
                line_upper = line.upper()
                if line_upper.startswith(coin_upper + '\t') or line_upper.startswith(coin_upper + ' '):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            return parts[1]
                        except:
                            pass
                    break
            return "0"
    elif exchange_base == "gate":
        # Gate.io - 从 balance 输出中解析
        output = run_on_ec2(f"balance {exchange}")
        for line in output.split('\n'):
            line_upper = line.upper()
            if line_upper.startswith(coin_upper + '\t') or line_upper.startswith(coin_upper + ' '):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return parts[1]
                    except:
                        pass
                break
        return "0"
    elif exchange_base == "bitget":
        # Bitget - 从 balance 输出中解析
        output = run_on_ec2(f"balance {exchange}")
        for line in output.split('\n'):
            line_upper = line.upper()
            if line_upper.startswith(coin_upper + '\t') or line_upper.startswith(coin_upper + ' '):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return parts[1]
                    except:
                        pass
                break
        return "0"
    else:
        # Binance - 使用 account_balance 命令精确查询
        output = run_on_ec2(f"account_balance {exchange} {account_type} {coin}").strip()
        if output and not output.startswith("用法") and not output.startswith("未知") and not output.startswith("错误"):
            try:
                return str(float(output))
            except ValueError:
                pass
        return "0"
