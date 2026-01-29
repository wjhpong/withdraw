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
            data = resp.json()
            return float(data.get('price', 0))

        # 尝试 COIN/BUSD
        resp = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={coin}BUSD",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data.get('price', 0))
    except requests.exceptions.Timeout:
        print(f"⚠️  获取 {coin} 价格超时")
    except requests.exceptions.ConnectionError:
        print(f"⚠️  获取 {coin} 价格失败: 网络连接错误")
    except (KeyError, ValueError) as e:
        print(f"⚠️  解析 {coin} 价格失败: {e}")

    return 0.0


def filter_by_value(balances: dict, min_value: float = MIN_DISPLAY_VALUE) -> dict:
    """过滤掉市值小于指定美元价值的资产"""
    if not isinstance(balances, dict):
        return {}
    result = {}
    for coin, amount in balances.items():
        try:
            amount_float = float(amount)
            price = get_coin_price(coin)
            value = amount_float * price
            if value >= min_value:
                result[coin] = amount_float
        except (ValueError, TypeError):
            continue
    return result


def show_balance(exchange: str = None):
    """查询余额"""
    if not exchange:
        exchange = select_exchange()
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    exchange_base = get_exchange_base(exchange)
    
    print(f"\n正在查询 {display_name} 余额...")

    # EC2 上的 balance 命令已经格式化好输出，直接显示
    output = run_on_ec2(f"balance {exchange}")

    # 移除 EC2 返回的 "正在查询..." 行，避免重复显示
    lines = output.strip().split('\n')
    for line in lines:
        if '正在查询' not in line:
            print(line)
    
    # 对于 BYBIT，额外查询统一账户余额
    if exchange_base == "bybit":
        try:
            # 尝试查询统一账户余额
            unified_output = run_on_ec2(f"balance {exchange} UNIFIED")
            # 移除 EC2 返回的 "正在查询..." 行
            unified_lines = unified_output.strip().split('\n')
            unified_printed = False
            for line in unified_lines:
                if '正在查询' not in line:
                    if line.strip():  # 只打印非空行
                        if not unified_printed:
                            # 在统一账户余额前添加分隔线和标题
                            print("\n" + "=" * 50)
                            print("📊 统一账户余额 (UNIFIED):")
                            print("=" * 50)
                            unified_printed = True
                        print(line)
        except Exception:
            # 如果查询统一账户失败，忽略错误（可能 EC2 上没有这个命令）
            pass


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


def _parse_balance_from_output(output: str, coin: str) -> str:
    """从 balance 命令输出中解析指定币种余额"""
    coin_upper = coin.upper()
    for line in output.split('\n'):
        line_upper = line.upper()
        if line_upper.startswith(coin_upper + '\t') or line_upper.startswith(coin_upper + ' '):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    # 验证是否为有效数字
                    float(parts[1])
                    return parts[1]
                except (ValueError, IndexError):
                    pass
            break
    return "0"


def get_coin_balance(exchange: str, coin: str, account_type: str = "SPOT") -> str:
    """查询指定币种余额

    Args:
        exchange: 交易所
        coin: 币种
        account_type: 账户类型 (SPOT/UNIFIED/FUND/EARN)

    Returns:
        余额字符串，失败返回 "0"
    """
    from utils import SSHError

    exchange_base = get_exchange_base(exchange)

    try:
        if exchange_base == "bybit":
            if account_type == "UNIFIED":
                output = run_on_ec2(f"account_balance bybit UNIFIED {coin}").strip()
                if output and not output.startswith(("用法", "未知", "错误")):
                    try:
                        return str(float(output))
                    except ValueError:
                        pass
                return "0"
            else:
                # 资金账户
                output = run_on_ec2(f"balance {exchange}")
                return _parse_balance_from_output(output, coin)

        elif exchange_base in ("gate", "bitget"):
            output = run_on_ec2(f"balance {exchange}")
            return _parse_balance_from_output(output, coin)

        else:
            # Binance - 使用 account_balance 命令精确查询
            output = run_on_ec2(f"account_balance {exchange} {account_type} {coin}").strip()
            if output and not output.startswith(("用法", "未知", "错误")):
                try:
                    return str(float(output))
                except ValueError:
                    pass
            return "0"

    except SSHError as e:
        print(f"❌ 查询余额失败: {e}")
        return "0"
