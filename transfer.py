#!/usr/bin/env python3
"""账户划转"""

from utils import run_on_ec2, select_option, input_amount
from balance import get_coin_balance


def do_transfer():
    """账户划转"""
    ex_idx = select_option("请选择交易所:", ["BINANCE", "BYBIT"], allow_back=True)
    if ex_idx == -1:
        return
    exchanges = ["binance", "bybit"]
    exchange = exchanges[ex_idx]
    
    if exchange == "binance":
        account_types = ["SPOT", "FUNDING"]
        account_names = ["现货账户", "资金账户"]
    else:
        account_types = ["UNIFIED", "FUND"]
        account_names = ["统一账户", "资金账户"]
    
    # 选择划转方向
    from_options = [f"{account_names[i]} → {account_names[1-i]}" for i in range(2)]
    from_idx = select_option("选择划转方向:", from_options, allow_back=True)
    if from_idx == -1:
        return
    from_type = account_types[from_idx]
    to_type = account_types[1 - from_idx]
    
    print(f"\n📤 从: {account_names[from_idx]} ({from_type})")
    print(f"📥 到: {account_names[1-from_idx]} ({to_type})")
    
    # 输入币种
    coin = input("\n请输入币种 (如 USDT, 输入 0 返回): ").strip().upper()
    if not coin or coin == "0":
        return
    
    # 显示源账户余额
    print(f"\n正在查询 {from_type} 账户的 {coin} 余额...")
    if exchange == "bybit":
        output = run_on_ec2(f"account_balance bybit {from_type} {coin}")
        balance = output.strip()
    else:
        balance = get_coin_balance(exchange, coin)
    print(f"💰 {from_type} 账户 {coin} 余额: {balance}")
    
    # 输入数量
    amount = input_amount("请输入划转数量:")
    if amount is None:
        return
    
    # 确认
    print("\n" + "=" * 50)
    print("请确认划转信息:")
    print(f"  交易所: {exchange.upper()}")
    print(f"  从: {from_type}")
    print(f"  到: {to_type}")
    print(f"  币种: {coin}")
    print(f"  数量: {amount}")
    print("=" * 50)
    
    if select_option("确认划转?", ["确认", "取消"]) != 0:
        print("已取消")
        return
    
    print("\n正在划转...")
    output = run_on_ec2(f"transfer {exchange} {from_type} {to_type} {coin} {amount}")
    print(output)
