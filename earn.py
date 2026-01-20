#!/usr/bin/env python3
"""币安理财操作"""

from utils import run_on_ec2, select_option, select_exchange, get_exchange_display_name, input_amount
from balance import get_coin_balance, get_coin_price

# 显示余额的最小价值阈值
SPOT_MIN_VALUE = 20


def show_spot_balances(exchange: str):
    """显示现货余额 (≥20U)"""
    print(f"\n正在查询现货余额...")
    output = run_on_ec2(f"balance {exchange}")
    
    # 只解析现货账户部分（在"📦 现货账户余额"和下一个"=="之间）
    balances = []
    in_spot_section = False
    
    for line in output.strip().split('\n'):
        # 检测进入现货账户部分
        if '现货账户余额' in line or 'SPOT' in line.upper() and '📦' in line:
            in_spot_section = True
            continue
        
        # 检测离开现货账户部分（遇到下一个账户标题）
        if in_spot_section and ('📊' in line or '💰' in line or '统一账户' in line or '理财持仓' in line):
            break
        
        # 跳过标题行和分隔线
        if not in_spot_section or '正在查询' in line or '===' in line or '---' in line or '币种' in line:
            continue
        
        if not line.strip():
            continue
            
        parts = line.split()
        if len(parts) >= 2:
            try:
                coin = parts[0].upper()
                amount = float(parts[1])
                price = get_coin_price(coin)
                value = amount * price
                if value >= SPOT_MIN_VALUE:
                    balances.append((coin, amount, value))
            except (ValueError, IndexError):
                continue
    
    if balances:
        # 按市值降序排列
        balances.sort(key=lambda x: x[2], reverse=True)
        print(f"\n💰 现货余额 (≥{SPOT_MIN_VALUE}U):")
        for coin, amount, value in balances:
            print(f"   {coin}: {amount:.4f} (≈${value:.2f})")
    else:
        print(f"\n💰 没有≥{SPOT_MIN_VALUE}U的现货余额")


def show_earn_position(exchange: str):
    """查询理财持仓"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 理财持仓...")
    output = run_on_ec2(f"earn position {exchange}")
    print(output)


def do_earn_subscribe(exchange: str):
    """申购理财"""
    coin = input("\n请输入币种 (如 USDT, 输入 0 返回): ").strip().upper()
    if not coin or coin == "0":
        return
    
    # 查询理财产品信息和剩余额度
    print(f"\n正在查询 {coin} 活期理财信息...")
    output = run_on_ec2(f"earn quota {exchange} {coin}")
    print(output)
    
    if "没有找到" in output or "错误" in output:
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


def manage_earn(exchange: str = None):
    """理财管理菜单"""
    # 选择 Binance 账号
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n已选择账号: {display_name}")
    
    # 自动显示现货余额
    show_spot_balances(exchange)

    while True:
        action = select_option(f"币安理财 [{display_name}]:", ["查询持仓", "申购活期", "赎回活期", "返回"])
        
        if action == 0:
            show_earn_position(exchange)
        elif action == 1:
            do_earn_subscribe(exchange)
        elif action == 2:
            do_earn_redeem(exchange)
        else:
            break

        input("\n按回车继续...")
