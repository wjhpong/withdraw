#!/usr/bin/env python3
"""账户划转"""

from utils import run_on_ec2, select_option, select_exchange, get_exchange_base, get_exchange_display_name, input_amount


def do_transfer():
    """账户划转"""
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
        # Gate.io: 现货 ↔ 合约
        transfer_options = [
            ("SPOT", "FUTURES", "现货 → 合约"),
            ("FUTURES", "SPOT", "合约 → 现货"),
        ]
        option_names = [opt[2] for opt in transfer_options]
        transfer_idx = select_option("选择划转方向:", option_names, allow_back=True)
        if transfer_idx == -1:
            return
        from_type = transfer_options[transfer_idx][0]
        to_type = transfer_options[transfer_idx][1]
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
