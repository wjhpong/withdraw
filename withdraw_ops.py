#!/usr/bin/env python3
"""提现操作"""

import time
from utils import run_on_ec2, select_option, select_exchange, get_exchange_base, get_exchange_display_name, input_amount, get_networks_for_type, get_networks_for_coin, detect_address_type, SSHError
from addresses import load_addresses
from balance import get_coin_balance


class WithdrawError(Exception):
    """提现操作错误"""
    pass


def do_withdraw(exchange: str = None):
    """执行提现"""
    addresses = load_addresses()
    
    # 选择交易所
    if not exchange:
        exchange = select_exchange()
        if not exchange:
            return
    
    exchange_base = get_exchange_base(exchange)

    # 过滤出当前交易所可用的地址
    available_addresses = []
    for a in addresses:
        addr_exchange = a.get('exchange', '')
        # 检查地址的交易所是否匹配当前选择的交易所
        if addr_exchange:
            # 地址指定了交易所，检查是否匹配
            if addr_exchange == exchange_base or addr_exchange == exchange:
                available_addresses.append(a)
        # 如果有 accounts 限制，检查当前账户是否在列表中
        elif a.get('accounts'):
            if exchange in a['accounts']:
                available_addresses.append(a)

    # 选择地址
    selected = None
    addr_options = []
    for a in available_addresses:
        if a.get('type') == 'fixed':
            coins_str = "/".join(a.get('coins', []))
            addr_options.append(f"[{a['name']}] {a.get('network', '')} - 仅{coins_str}")
        else:
            # 检查是否是circle或REAP地址，显示特殊标记
            if a.get('name', '').lower() == 'circle':
                addr_options.append(f"[{a['name']}] {a['address'][:25]}... - 仅USDC")
            elif a.get('name', '').lower() == 'reap':
                addr_options.append(f"[{a['name']}] {a['address'][:25]}... - 仅USDC")
            else:
                addr_options.append(f"[{a['name']}] {a['address'][:25]}...")
    addr_options.append("输入新地址")
    
    addr_idx = select_option("请选择提现地址:", addr_options, allow_back=True)
    if addr_idx == -1:
        return
    if addr_idx < len(available_addresses):
        selected = available_addresses[addr_idx]
    else:
        selected = None

    # 输入币种
    # circle地址只能提现USDC，REAP地址只能提现USDC
    if selected:
        addr_name_lower = selected.get('name', '').lower().strip()
        # circle地址只能提现USDC，自动设置，不要求输入
        if addr_name_lower == 'circle':
            coin = 'USDC'
            print(f"\n⚠️  circle地址只能提现USDC，已自动选择USDC")
            # 跳过币种输入，直接继续
        elif addr_name_lower == 'reap':
            # REAP地址只能提现USDC，自动设置，不要求输入
            coin = 'USDC'
            print(f"\n⚠️  REAP地址只能提现USDC，已自动选择USDC")
            # 跳过币种输入，直接继续
        elif selected.get('coins'):
            # 地址有币种限制，显示选择菜单
            allowed_coins = selected['coins']
            coin_idx = select_option("请选择币种:", allowed_coins, allow_back=True)
            if coin_idx == -1:
                return
            coin = allowed_coins[coin_idx]
        else:
            # 普通地址，要求输入币种
            coin = input("\n请输入币种 (如 USDT, 输入 0 返回): ").strip().upper()
            if not coin or coin == "0":
                return
    else:
        # 输入新地址，要求输入币种
        coin = input("\n请输入币种 (如 USDT, 输入 0 返回): ").strip().upper()
        if not coin or coin == "0":
            return
    
    # 如果选择了circle地址但币种不是USDC，提示错误
    if selected and selected.get('name', '').lower() == 'circle' and coin.upper() != 'USDC':
        print(f"\n❌ 错误: circle地址只能提现USDC，不能提现{coin}")
        return
    
    # 如果选择了REAP地址但币种不是USDC，提示错误
    if selected and selected.get('name', '').lower() == 'reap' and coin.upper() != 'USDC':
        print(f"\n❌ 错误: REAP地址只能提现USDC，不能提现{coin}")
        return
    
    # 显示余额（同时查询现货和统一账户）
    print(f"\n正在查询 {coin} 余额...")
    
    if exchange_base == "bybit":
        # Bybit: 查询 FUND 和 UNIFIED 账户
        fund_bal = get_coin_balance(exchange, coin, "FUND")
        unified_bal = get_coin_balance(exchange, coin, "UNIFIED")
        print(f"💰 {coin} 资金账户: {fund_bal}")
        print(f"💰 {coin} 统一账户: {unified_bal}")
    elif exchange_base == "binance":
        # Binance: 查询 SPOT 和 PM (Portfolio Margin) 账户
        spot_bal = get_coin_balance(exchange, coin, "SPOT")
        pm_bal = get_coin_balance(exchange, coin, "PM")
        print(f"💰 {coin} 现货账户: {spot_bal}")
        print(f"💰 {coin} 统一账户: {pm_bal}")
    elif exchange_base == "gate":
        # Gate.io: 查询 SPOT 现货账户
        spot_bal = get_coin_balance(exchange, coin, "SPOT")
        print(f"💰 {coin} 现货账户: {spot_bal}")
    elif exchange_base == "bitget":
        # Bitget: 查询现货账户
        spot_bal = get_coin_balance(exchange, coin, "SPOT")
        print(f"💰 {coin} 现货账户: {spot_bal}")

    # 处理地址和网络
    # REAP地址强制使用Polygon网络，优先处理，不进入任何网络选择逻辑
    is_reap_address = selected and selected.get('name', '').lower() == 'reap'
    
    if is_reap_address:
        network = "MATIC"
        print(f"\n⚠️  REAP地址只能使用Polygon网络，已自动选择MATIC")
        
        # 获取地址和memo
        address = selected['address']
        memo = selected.get('memo')
    elif selected:
        address = selected['address']
        addr_type = selected.get('type', 'evm')
        memo = selected.get('memo')
        
        if selected.get('network'):
            network = selected['network']
            print(f"\n自动选择网络: {network}")
        else:
            networks = get_networks_for_coin(coin, addr_type)
            if not networks:
                print(f"\n❌ 错误: 无法获取可用网络")
                return
            if len(networks) == 1:
                network = networks[0]
                print(f"\n自动选择网络: {network}")
            else:
                net_idx = select_option("请选择网络:", networks, allow_back=True)
                if net_idx == -1:
                    return
                network = networks[net_idx]
    else:
        # 输入新地址的情况
        address = input("\n请输入提现地址 (输入 0 返回): ").strip()
        if not address or address == "0":
            return
        
        addr_type = detect_address_type(address)
        if addr_type == "sui_apt":
            choice = select_option("SUI 和 APT 地址格式相同，请选择:", ["SUI", "APT (Aptos)"], allow_back=True)
            if choice == -1:
                return
            addr_type = "sui" if choice == 0 else "apt"
        
        networks = get_networks_for_coin(coin, addr_type)
        if not networks:
            print(f"\n❌ 错误: 无法获取可用网络")
            return
        if len(networks) == 1:
            network = networks[0]
            print(f"\n自动选择网络: {network}")
        else:
            net_idx = select_option("请选择网络:", networks, allow_back=True)
            if net_idx == -1:
                return
            network = networks[net_idx]
            if network == "其他":
                network = input("请输入网络名称 (输入 0 返回): ").strip().upper()
                if not network or network == "0":
                    return
        
        memo = input("请输入 Memo/Tag (没有直接回车跳过): ").strip() or None

    # 输入数量
    amount = input_amount("请输入提现数量:")
    if amount is None:
        return
    
    # 自动从统一账户划转到现货/资金账户（如果需要）
    try:
        required_amount = float(amount) + 2  # 预留手续费
    except (ValueError, TypeError):
        print(f"❌ 无效的数量: {amount}")
        return

    try:
        if exchange_base == "bybit":
            # Bybit: 查询资金账户余额
            fund_balance = float(get_coin_balance(exchange, coin, "FUND") or 0)

            # 如果资金账户余额不足，从统一账户划转
            if fund_balance < required_amount:
                unified_balance = float(get_coin_balance(exchange, coin, "UNIFIED") or 0)

                if unified_balance > 0:
                    transfer_amount = required_amount - fund_balance
                    if transfer_amount > unified_balance:
                        transfer_amount = unified_balance

                    print(f"\n⚠️  资金账户余额不足 ({fund_balance} {coin})，需要约 {required_amount} {coin}（含手续费）")
                    print(f"   统一账户余额: {unified_balance} {coin}")
                    print(f"   正在从统一账户划转 {transfer_amount} {coin} 到资金账户...")

                    transfer_result = run_on_ec2(f"transfer bybit UNIFIED FUND {coin} {transfer_amount}")
                    print(transfer_result)
                    time.sleep(1)

        elif exchange_base == "binance":
            # Binance: 查询现货账户余额
            spot_balance = float(get_coin_balance(exchange, coin, "SPOT") or 0)

            # 如果现货账户余额不足，从统一账户(Portfolio Margin)划转
            if spot_balance < required_amount:
                pm_balance = float(get_coin_balance(exchange, coin, "PM") or 0)

                if pm_balance > 0:
                    transfer_amount = required_amount - spot_balance
                    if transfer_amount > pm_balance:
                        transfer_amount = pm_balance

                    print(f"\n⚠️  现货账户余额不足 ({spot_balance} {coin})，需要约 {required_amount} {coin}（含手续费）")
                    print(f"   统一账户余额: {pm_balance} {coin}")
                    print(f"   正在从统一账户划转 {transfer_amount} {coin} 到现货账户...")

                    # Binance 使用 PORTFOLIO_MARGIN 和 MAIN 作为类型名
                    transfer_result = run_on_ec2(f"transfer {exchange} PORTFOLIO_MARGIN MAIN {coin} {transfer_amount}")
                    print(transfer_result)
                    time.sleep(1)

    except SSHError as e:
        print(f"❌ 自动划转失败: {e}")
        print("   请手动划转后重试")
        return
    except ValueError as e:
        print(f"❌ 余额解析错误: {e}")
        return

    # 确认
    display_name = get_exchange_display_name(exchange)
    print("\n" + "=" * 50)
    print("请确认提现信息:")
    print(f"  交易所: {display_name}")
    print(f"  币种: {coin}")
    print(f"  网络: {network}")
    print(f"  地址: {address}")
    print(f"  数量: {amount}")
    if memo:
        print(f"  Memo: {memo}")
    print("=" * 50)

    if select_option("确认提现?", ["确认提现", "取消"]) != 0:
        print("已取消")
        return

    # 执行提现
    print("\n正在提交提现请求...")
    # Bybit 地址需要小写（与保存的地址格式匹配）
    if exchange_base == "bybit":
        address = address.lower()
    cmd = f'withdraw {exchange} {coin} {network} {address} {amount}'
    if memo:
        cmd += f' {memo}'

    try:
        output = run_on_ec2(cmd)
        print(output)

        # 检查常见错误
        output_lower = output.lower()
        if "error" in output_lower or "failed" in output_lower or "失败" in output:
            print("\n⚠️  提现可能失败，请检查交易所确认")
        elif "success" in output_lower or "成功" in output:
            print("\n✅ 提现请求已提交")
    except SSHError as e:
        print(f"\n❌ 提现请求失败: {e}")
