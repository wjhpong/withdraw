#!/usr/bin/env python3
"""稳定币交易"""

from utils import run_on_ec2, select_option, input_amount, select_exchange, get_exchange_display_name


def do_stablecoin_trade():
    """稳定币交易"""
    print("\n=== 稳定币交易 ===")

    # 选择交易对
    pair_idx = select_option("选择交易对:", [
        "USDC/USDT (Bybit)",
        "BFUSD/USDT (Binance)",
        "返回"
    ])

    if pair_idx == 2:
        return

    if pair_idx == 0:
        trade_usdc_usdt()
    elif pair_idx == 1:
        trade_bfusd_usdt()


def trade_usdc_usdt():
    """Bybit USDC/USDT 交易"""
    print("\n=== Bybit USDC/USDT 交易 ===")

    while True:
        # 显示深度
        print("\n正在获取 USDC/USDT 深度...")
        output = run_on_ec2("orderbook bybit")
        print(output)

        # 显示 USDT 余额
        print("正在查询统一账户 USDT 余额...")
        output = run_on_ec2("account_balance bybit UNIFIED USDT")
        balance = output.strip()
        print(f"💰 统一账户 USDT 余额: {balance}")

        action = select_option("选择操作:", ["市价买入 USDC", "限价买入 USDC", "刷新深度", "返回"])

        if action == 3:
            break
        elif action == 2:
            continue

        amount = input_amount("请输入买入 USDC 数量:")
        if amount is None:
            continue

        if action == 0:  # 市价
            if select_option(f"确认市价买入 {amount} USDC?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                output = run_on_ec2(f"buy_usdc bybit market {amount}")
                print(output)

        elif action == 1:  # 限价
            price_str = input("请输入限价 (如 1.0002, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价买入 {amount} USDC?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                output = run_on_ec2(f"buy_usdc bybit limit {amount} {price}")
                print(output)

        input("\n按回车继续...")


def trade_bfusd_usdt():
    """Binance BFUSD/USDT 交易"""
    # 先选择账号
    exchange = select_exchange(binance_only=True)
    if not exchange:
        return

    display_name = get_exchange_display_name(exchange)
    print(f"\n=== {display_name} BFUSD/USDT 交易 ===")

    while True:
        # 显示深度
        print("\n正在获取 BFUSD/USDT 深度...")
        output = run_on_ec2("orderbook binance BFUSDUSDT")
        print(output)

        # 显示 USDT 余额
        print(f"正在查询 {display_name} 现货账户 USDT 余额...")
        output = run_on_ec2(f"account_balance {exchange} SPOT USDT")
        balance = output.strip()
        print(f"💰 现货账户 USDT 余额: {balance}")

        action = select_option("选择操作:", ["市价买入 BFUSD", "限价买入 BFUSD", "刷新深度", "返回"])

        if action == 3:
            break
        elif action == 2:
            continue

        amount = input_amount("请输入买入 BFUSD 数量:")
        if amount is None:
            continue

        if action == 0:  # 市价
            if select_option(f"确认市价买入 {amount} BFUSD?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                output = run_on_ec2(f"buy_bfusd {exchange} market {amount}")
                print(output)

        elif action == 1:  # 限价
            price_str = input("请输入限价 (如 1.0002, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价买入 {amount} BFUSD?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                output = run_on_ec2(f"buy_bfusd {exchange} limit {amount} {price}")
                print(output)

        input("\n按回车继续...")
