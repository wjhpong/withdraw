#!/usr/bin/env python3
"""稳定币交易"""

from utils import run_on_ec2, select_option, input_amount, select_exchange, get_exchange_display_name


def do_stablecoin_trade(exchange: str = None):
    """稳定币交易"""
    print("\n=== 稳定币交易 ===")

    # 如果已选择交易所，直接进入对应交易
    if exchange:
        if exchange.startswith("binance"):
            trade_bfusd_usdt(exchange)
        elif exchange == "bybit":
            trade_usdc_usdt()
        return

    # 否则选择交易对
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

        # 显示资金账户和统一账户 USDT 余额
        print("正在查询账户余额...")
        funding_output = run_on_ec2("account_balance bybit FUND USDT")
        unified_output = run_on_ec2("account_balance bybit UNIFIED USDT")
        
        try:
            funding_balance = float(funding_output.strip())
        except:
            funding_balance = 0.0
        try:
            unified_balance = float(unified_output.strip())
        except:
            unified_balance = 0.0
        
        print(f"💰 资金账户 USDT: {funding_balance:.4f}")
        print(f"💰 统一账户 USDT: {unified_balance:.4f}")
        print(f"💰 合计 USDT: {funding_balance + unified_balance:.4f}")

        action = select_option("选择操作:", ["市价买入 USDC", "限价买入 USDC", "刷新深度", "返回"])

        if action == 3:
            break
        elif action == 2:
            continue

        amount = input_amount("请输入买入 USDC 数量:")
        if amount is None:
            continue

        # 检查统一账户余额是否足够，不够则自动划转
        required_usdt = float(amount) * 1.001  # 预留0.1%滑点
        if unified_balance < required_usdt:
            need_transfer = required_usdt - unified_balance + 1  # 多转1U作为缓冲
            if funding_balance >= need_transfer:
                print(f"\n⚠️ 统一账户余额不足，需要从资金账户划转 {need_transfer:.2f} USDT")
                if select_option("是否自动划转?", ["确认划转", "取消"]) == 0:
                    print("正在划转...")
                    transfer_output = run_on_ec2(f"transfer bybit USDT FUND UNIFIED {need_transfer:.2f}")
                    print(transfer_output)
                    # 更新余额
                    unified_balance += need_transfer
                    funding_balance -= need_transfer
                else:
                    continue
            else:
                total = funding_balance + unified_balance
                print(f"\n❌ 余额不足! 需要约 {required_usdt:.2f} USDT，合计只有 {total:.2f} USDT")
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


def trade_bfusd_usdt(exchange: str = None):
    """Binance BFUSD/USDT 交易"""
    # 先选择账号
    if not exchange:
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
