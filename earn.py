#!/usr/bin/env python3
"""币安理财操作"""

from utils import run_on_ec2, select_option, select_exchange, input_amount
from balance import get_coin_balance


def show_earn_position(exchange: str):
    """查询理财持仓"""
    print(f"\n正在查询 {exchange.upper()} 理财持仓...")
    output = run_on_ec2(f"earn position {exchange}")
    print(output)


def do_earn_subscribe(exchange: str):
    """申购理财"""
    coin = input("\n请输入币种 (如 USDT, 输入 0 返回): ").strip().upper()
    if not coin or coin == "0":
        return
    
    print(f"\n正在查询 {coin} 现货余额...")
    balance = get_coin_balance(exchange, coin)
    print(f"💰 {coin} 现货余额: {balance}")
    
    amount = input_amount("请输入申购数量:")
    if amount is None:
        return
    
    if select_option(f"确认申购 {amount} {coin} 到活期理财?", ["确认", "取消"]) != 0:
        print("已取消")
        return
    
    print("\n正在申购...")
    output = run_on_ec2(f"earn subscribe {exchange} {coin} {amount}")
    print(output)


def do_earn_redeem(exchange: str):
    """赎回理财"""
    print("\n正在查询理财持仓...")
    output = run_on_ec2(f"earn position {exchange}")
    print(output)
    
    coin = input("\n请输入要赎回的币种 (输入 0 返回): ").strip().upper()
    if not coin or coin == "0":
        return
    
    amount_str = input("请输入赎回数量 (直接回车=全部, 输入 0 返回): ").strip()
    if amount_str == "0":
        return
    
    if amount_str:
        try:
            amount = float(amount_str)
        except ValueError:
            print("无效的数量")
            return
        if select_option(f"确认赎回 {amount} {coin}?", ["确认", "取消"]) != 0:
            print("已取消")
            return
        cmd = f"earn redeem {exchange} {coin} {amount}"
    else:
        if select_option(f"确认全部赎回 {coin}?", ["确认", "取消"]) != 0:
            print("已取消")
            return
        cmd = f"earn redeem {exchange} {coin}"
    
    print("\n正在赎回...")
    output = run_on_ec2(cmd)
    print(output)


def manage_earn():
    """理财管理菜单"""
    # 选择 Binance 账号
    exchange = select_exchange(binance_only=True)
    if not exchange:
        return
    
    print(f"\n已选择账号: {exchange.upper()}")
    
    while True:
        action = select_option("币安理财操作:", ["查询持仓", "申购活期", "赎回活期", "返回主菜单"])
        
        if action == 0:
            show_earn_position(exchange)
        elif action == 1:
            do_earn_subscribe(exchange)
        elif action == 2:
            do_earn_redeem(exchange)
        else:
            break
        
        input("\n按回车继续...")
