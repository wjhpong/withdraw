#!/usr/bin/env python3
"""账户划转"""

import json
from utils import run_on_ec2, select_option, select_exchange, get_exchange_base, get_exchange_display_name, input_amount


def do_gate_subaccount_transfer(exchange: str):
    """Gate.io 主账户 ↔ 子账户划转"""
    display_name = get_exchange_display_name(exchange)
    
    # 选择划转方向
    direction_idx = select_option("选择划转方向:", [
        "主账户 → 子账户",
        "子账户 → 主账户"
    ], allow_back=True)
    
    if direction_idx == -1:
        return
    
    direction = "to" if direction_idx == 0 else "from"
    
    # 获取子账户列表
    print("\n正在获取子账户列表...")
    output = run_on_ec2("gate_list_subaccounts")
    
    try:
        # 解析 JSON 格式的子账户列表
        sub_accounts = json.loads(output.strip())
    except json.JSONDecodeError:
        print(f"获取子账户列表失败: {output}")
        return
    
    if not sub_accounts:
        print("没有子账户")
        return
    
    # 显示子账户列表供选择
    sub_names = [f"{s['login_name']} (UID: {s['user_id']})" for s in sub_accounts]
    sub_idx = select_option("选择子账户:", sub_names, allow_back=True)
    
    if sub_idx == -1:
        return
    
    selected_sub = sub_accounts[sub_idx]
    sub_uid = selected_sub['user_id']
    sub_name = selected_sub['login_name']
    
    # 显示方向信息
    if direction == "to":
        print(f"\n📤 从: 主账户")
        print(f"📥 到: 子账户 [{sub_name}]")
        # 显示主账户余额
        print(f"\n正在查询主账户余额...")
        output = run_on_ec2(f"balance gate")
        print(output)
    else:
        print(f"\n📤 从: 子账户 [{sub_name}]")
        print(f"📥 到: 主账户")
        # 显示该子账户余额
        print(f"\n正在查询子账户 [{sub_name}] 余额...")
        output = run_on_ec2(f"gate_subaccount_balance {sub_uid}")
        print(output)
    
    # 输入币种
    coin = input("\n请输入要划转的币种 (如 USDT, 输入 0 返回): ").strip().upper()
    if not coin or coin == "0":
        return
    
    # 输入数量
    amount = input_amount("请输入划转数量:")
    if amount is None:
        return
    
    # 确认
    if direction == "to":
        from_str = "主账户"
        to_str = f"子账户 [{sub_name}]"
    else:
        from_str = f"子账户 [{sub_name}]"
        to_str = "主账户"
    
    print("\n" + "=" * 50)
    print("请确认划转信息:")
    print(f"  交易所: {display_name}")
    print(f"  从: {from_str}")
    print(f"  到: {to_str}")
    print(f"  币种: {coin}")
    print(f"  数量: {amount}")
    print("=" * 50)
    
    if select_option("确认划转?", ["确认", "取消"]) != 0:
        print("已取消")
        return
    
    print("\n正在划转...")
    output = run_on_ec2(f"gate_subaccount_transfer {sub_uid} {direction} {coin} {amount}")
    print(output)


def do_transfer(exchange: str = None):
    """账户划转"""
    if not exchange:
        exchange = select_exchange()
        if not exchange:
            return
    
    exchange_base = get_exchange_base(exchange)
    display_name = get_exchange_display_name(exchange)
    
    if exchange_base == "binance":
        # Binance 划转选项
        transfer_options = [
            ("MAIN", "PORTFOLIO_MARGIN", "现货 → 统一账户"),
            ("PORTFOLIO_MARGIN", "MAIN", "统一账户 → 现货"),
        ]
        option_names = [opt[2] for opt in transfer_options]
        transfer_idx = select_option("选择划转方向:", option_names, allow_back=True)
        if transfer_idx == -1:
            return
        from_type = transfer_options[transfer_idx][0]
        to_type = transfer_options[transfer_idx][1]
    elif exchange_base == "gate":
        # Gate.io: 主账户 ↔ 子账户
        do_gate_subaccount_transfer(exchange)
        return
    else:
        # Bybit: 统一账户 ↔ 资金账户
        transfer_options = [
            ("UNIFIED", "FUND", "统一账户 → 资金账户"),
            ("FUND", "UNIFIED", "资金账户 → 统一账户"),
        ]
        option_names = [opt[2] for opt in transfer_options]
        transfer_idx = select_option("选择划转方向:", option_names, allow_back=True)
        if transfer_idx == -1:
            return
        from_type = transfer_options[transfer_idx][0]
        to_type = transfer_options[transfer_idx][1]
    
    print(f"\n📤 从: {from_type}")
    print(f"📥 到: {to_type}")
    
    # 显示源账户余额
    print(f"\n正在查询 {from_type} 账户余额...")
    output = run_on_ec2(f"balance {exchange}")
    print(output)
    
    # 输入币种
    coin = input("\n请输入要划转的币种 (如 USDT, 输入 0 返回): ").strip().upper()
    if not coin or coin == "0":
        return
    
    # 输入数量
    amount = input_amount("请输入划转数量:")
    if amount is None:
        return
    
    # 确认
    print("\n" + "=" * 50)
    print("请确认划转信息:")
    print(f"  交易所: {display_name}")
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
