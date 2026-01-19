#!/usr/bin/env python3
"""BNB 工具 - 抵扣开关、小额资产转换、市价买入"""

from utils import run_on_ec2, select_option, select_exchange, input_amount


def toggle_bnb_burn():
    """BNB 抵扣开关"""
    exchange = select_exchange(binance_only=True)
    if not exchange:
        return
    
    print(f"\n正在查询 BNB 抵扣状态...")
    output = run_on_ec2(f"bnb_burn_status {exchange}")
    print(output)
    
    action = select_option("选择操作:", [
        "开启现货手续费 BNB 抵扣",
        "关闭现货手续费 BNB 抵扣",
        "开启杠杆利息 BNB 抵扣",
        "关闭杠杆利息 BNB 抵扣",
        "返回"
    ], allow_back=True)
    
    if action == -1 or action == 4:
        return
    
    if action in [0, 1]:
        # 现货手续费
        enable = "true" if action == 0 else "false"
        print(f"\n正在{'开启' if action == 0 else '关闭'}现货手续费 BNB 抵扣...")
        output = run_on_ec2(f"bnb_burn_toggle {exchange} spot {enable}")
    else:
        # 杠杆利息
        enable = "true" if action == 2 else "false"
        print(f"\n正在{'开启' if action == 2 else '关闭'}杠杆利息 BNB 抵扣...")
        output = run_on_ec2(f"bnb_burn_toggle {exchange} interest {enable}")
    print(output)


def convert_dust_to_bnb():
    """小额资产转换 BNB"""
    exchange = select_exchange(binance_only=True)
    if not exchange:
        return
    
    print(f"\n正在查询可转换的小额资产...")
    output = run_on_ec2(f"dust_list {exchange}")
    print(output)
    
    if "没有可转换" in output or "error" in output.lower():
        return
    
    confirm = select_option("确认将小额资产转换为 BNB?", ["确认转换", "取消"], allow_back=True)
    if confirm != 0:
        print("已取消")
        return
    
    print(f"\n正在转换小额资产...")
    output = run_on_ec2(f"dust_convert {exchange}")
    print(output)


def buy_bnb_market():
    """市价单买入 BNB"""
    exchange = select_exchange(binance_only=True)
    if not exchange:
        return
    
    # 选择支付币种
    pay_coin_idx = select_option("选择支付币种:", ["USDT", "USDC", "FDUSD"], allow_back=True)
    if pay_coin_idx == -1:
        return
    pay_coins = ["USDT", "USDC", "FDUSD"]
    pay_coin = pay_coins[pay_coin_idx]
    
    # 查询余额
    print(f"\n正在查询 {pay_coin} 余额...")
    output = run_on_ec2(f"balance {exchange}")
    
    # 解析余额
    balance = "0"
    for line in output.split('\n'):
        if line.upper().startswith(pay_coin):
            parts = line.split()
            if len(parts) >= 2:
                balance = parts[1]
                break
    print(f"💰 {pay_coin} 可用余额: {balance}")
    
    # 查询 BNB 当前价格
    print(f"\n正在查询 BNB/{pay_coin} 价格...")
    output = run_on_ec2(f"bnb_price {exchange} {pay_coin}")
    print(output)
    
    # 输入金额
    amount = input_amount(f"请输入支付 {pay_coin} 金额:")
    if amount is None:
        return
    
    # 确认
    confirm = select_option(f"确认用 {amount} {pay_coin} 市价买入 BNB?", ["确认买入", "取消"], allow_back=True)
    if confirm != 0:
        print("已取消")
        return
    
    print(f"\n正在市价买入 BNB...")
    output = run_on_ec2(f"buy_bnb {exchange} {pay_coin} {amount}")
    print(output)


def manage_bnb_tools():
    """BNB 工具菜单"""
    while True:
        action = select_option("BNB 工具:", [
            "BNB 抵扣开关",
            "小额资产转 BNB",
            "市价买入 BNB",
            "返回主菜单"
        ])
        
        if action == 0:
            toggle_bnb_burn()
        elif action == 1:
            convert_dust_to_bnb()
        elif action == 2:
            buy_bnb_market()
        else:
            break
        
        input("\n按回车继续...")
