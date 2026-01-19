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


def show_balance():
    """查询余额"""
    exchange = select_exchange()
    if not exchange:
        return
    
    exchange_base = get_exchange_base(exchange)
    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 余额...")
    
    # Bybit需要同时查询统一账户和资金账户
    if exchange_base == "bybit":
        # 查询资金账户余额
        fund_output = run_on_ec2(f"balance {exchange}")
        
        # 解析资金账户中的币种和余额
        fund_lines = fund_output.strip().split('\n')
        fund_balances = {}
        for line in fund_lines:
            # 跳过标题行和分隔线
            if '币种' in line or '---' in line or not line.strip() or '正在查询' in line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    # 尝试解析数字，如果能解析说明是余额数据行
                    balance_val = float(parts[1])
                    coin = parts[0].strip()
                    if coin and coin not in ['币种', '可用', '冻结']:
                        fund_balances[coin] = balance_val
                except (ValueError, IndexError):
                    continue
        
        # 查询统一账户余额 - 查询常用币种
        common_coins = ['USDC', 'USDT', 'BTC', 'ETH']
        # 合并资金账户中的币种
        all_coins = list(set(common_coins + list(fund_balances.keys())))
        
        unified_balances = {}
        for coin in all_coins:
            unified_balance = run_on_ec2(f"account_balance bybit UNIFIED {coin}").strip()
            if unified_balance and not unified_balance.startswith("用法") and not unified_balance.startswith("未知"):
                try:
                    balance_val = float(unified_balance)
                    if balance_val > 0:
                        unified_balances[coin] = balance_val
                except ValueError:
                    pass
        
        # 过滤小于 10U 的资产
        fund_balances = filter_by_value(fund_balances)
        unified_balances = filter_by_value(unified_balances)

        # 显示资金账户余额
        print("\n" + "=" * 50)
        print("📦 资金账户余额 (FUND):")
        print("=" * 50)
        if fund_balances:
            print("币种\t\t可用")
            print("-" * 50)
            for coin, balance in fund_balances.items():
                print(f"{coin}\t\t{balance}")
        else:
            print("资金账户暂无余额")

        # 显示统一账户余额
        print("\n" + "=" * 50)
        print("📊 统一账户余额 (UNIFIED):")
        print("=" * 50)
        if unified_balances:
            print("币种\t\t可用")
            print("-" * 50)
            for coin, balance in unified_balances.items():
                print(f"{coin}\t\t{balance}")
        else:
            print("统一账户暂无余额")

        output = fund_output
    else:
        # Binance: 分别显示现货账户和统一账户
        # 查询现货账户余额
        spot_output = run_on_ec2(f"balance {exchange}")

        # 解析现货账户中的币种和余额
        spot_lines = spot_output.strip().split('\n')
        spot_balances = {}
        for line in spot_lines:
            if '币种' in line or '---' in line or not line.strip() or '正在查询' in line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    balance_val = float(parts[1])
                    coin = parts[0].strip()
                    if coin and coin not in ['币种', '可用', '冻结']:
                        spot_balances[coin] = balance_val
                except (ValueError, IndexError):
                    continue

        # 查询统一账户余额 - 查询常用币种
        common_coins = ['USDC', 'USDT', 'BTC', 'ETH', 'BNB', 'USD1']
        all_coins = list(set(common_coins + list(spot_balances.keys())))

        unified_balances = {}
        for coin in all_coins:
            unified_balance = run_on_ec2(f"account_balance {exchange} UNIFIED {coin}").strip()
            if unified_balance and not unified_balance.startswith("用法") and not unified_balance.startswith("未知"):
                try:
                    balance_val = float(unified_balance)
                    if balance_val > 0:
                        unified_balances[coin] = balance_val
                except ValueError:
                    pass

        # 过滤小于 10U 的资产
        spot_balances = filter_by_value(spot_balances)
        unified_balances = filter_by_value(unified_balances)

        # 显示现货账户余额
        print("\n" + "=" * 50)
        print("📦 现货账户余额 (SPOT):")
        print("=" * 50)
        if spot_balances:
            print("币种\t\t可用")
            print("-" * 50)
            for coin, balance in spot_balances.items():
                print(f"{coin}\t\t{balance}")
        else:
            print("现货账户暂无余额")

        # 显示统一账户余额
        print("\n" + "=" * 50)
        print("📊 统一账户余额 (PORTFOLIO MARGIN):")
        print("=" * 50)
        if unified_balances:
            print("币种\t\t可用")
            print("-" * 50)
            for coin, balance in unified_balances.items():
                print(f"{coin}\t\t{balance}")
        else:
            print("统一账户暂无余额")

        output = spot_output
    
    # 检查是否有余额数据
    lines = output.strip().split('\n')
    has_balance = False
    for line in lines:
        # 跳过标题行和分隔线
        if '币种' in line or '---' in line or not line.strip():
            continue
        # 如果有非空的数据行，说明有余额
        parts = line.split()
        if len(parts) >= 2:
            try:
                # 尝试解析数字，如果能解析说明是余额数据
                float(parts[1])
                has_balance = True
                break
            except (ValueError, IndexError):
                continue
    
    if not has_balance and exchange_base != "bybit":
        print("\n⚠️  当前账户暂无余额")


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
    else:
        # Binance - 使用 account_balance 命令精确查询
        output = run_on_ec2(f"account_balance {exchange} {account_type} {coin}").strip()
        if output and not output.startswith("用法") and not output.startswith("未知") and not output.startswith("错误"):
            try:
                return str(float(output))
            except ValueError:
                pass
        return "0"
