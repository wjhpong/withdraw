#!/usr/bin/env python3
"""余额查询"""

from utils import run_on_ec2, select_option


def show_balance():
    """查询余额"""
    ex_idx = select_option("请选择交易所:", ["BINANCE", "BYBIT"], allow_back=True)
    if ex_idx == -1:
        return
    
    exchanges = ["binance", "bybit"]
    exchange = exchanges[ex_idx]
    
    print(f"\n正在查询 {exchange.upper()} 余额...")
    
    # Bybit需要同时查询统一账户和资金账户
    if exchange == "bybit":
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
        # Binance直接查询
        output = run_on_ec2(f"balance {exchange}")
        print(output)
    
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
    
    if not has_balance and exchange != "bybit":
        print("\n⚠️  当前账户暂无余额")


def get_coin_balance(exchange: str, coin: str) -> str:
    """查询指定币种余额（Bybit包括统一账户和资金账户总和）"""
    if exchange == "bybit":
        # Bybit需要查询资金账户和统一账户的总和
        # 查询资金账户余额
        fund_output = run_on_ec2(f"balance {exchange}")
        coin_upper = coin.upper()
        fund_balance = 0.0
        
        for line in fund_output.split('\n'):
            line_upper = line.upper()
            if line_upper.startswith(coin_upper + '\t') or line_upper.startswith(coin_upper + ' '):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        fund_balance = float(parts[1])
                    except ValueError:
                        pass
                break
        
        # 查询统一账户余额
        unified_output = run_on_ec2(f"account_balance bybit UNIFIED {coin}").strip()
        unified_balance = 0.0
        if unified_output and not unified_output.startswith("用法") and not unified_output.startswith("未知"):
            try:
                unified_balance = float(unified_output)
            except ValueError:
                pass
        
        # 返回总和
        total_balance = fund_balance + unified_balance
        return str(total_balance)
    else:
        # Binance直接查询
        output = run_on_ec2(f"balance {exchange}")
        coin_upper = coin.upper()
        for line in output.split('\n'):
            line_upper = line.upper()
            if line_upper.startswith(coin_upper + '\t') or line_upper.startswith(coin_upper + ' '):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
        return "0"
