#!/usr/bin/env python3
"""提现操作"""

import time
from utils import run_on_ec2, select_option, input_amount, get_networks_for_type, get_networks_for_coin, detect_address_type
from addresses import load_addresses
from balance import get_coin_balance


def do_withdraw():
    """执行提现"""
    addresses = load_addresses()
    
    # 选择交易所
    ex_idx = select_option("请选择交易所:", ["BINANCE", "BYBIT"], allow_back=True)
    if ex_idx == -1:
        return
    exchanges = ["binance", "bybit"]
    exchange = exchanges[ex_idx]

    # 过滤出当前交易所可用的地址
    available_addresses = [a for a in addresses if a.get('exchange') is None or a.get('exchange') == exchange]

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
    
    # 显示余额
    print(f"\n正在查询 {coin} 余额...")
    balance = get_coin_balance(exchange, coin)
    print(f"💰 {coin} 可用余额: {balance}")

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
    
    # Bybit自动从统一账户划转到资金账户（如果需要）
    if exchange == "bybit":
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
        
        # 如果资金账户余额不足（考虑手续费，预留2个单位），从统一账户划转
        required_amount = float(amount) + 2  # 预留手续费
        if fund_balance < required_amount:
            # 查询统一账户余额
            unified_output = run_on_ec2(f"account_balance bybit UNIFIED {coin}").strip()
            unified_balance = 0.0
            if unified_output and not unified_output.startswith("用法") and not unified_output.startswith("未知"):
                try:
                    unified_balance = float(unified_output)
                except ValueError:
                    pass
            
            # 如果需要划转
            if unified_balance > 0:
                transfer_amount = required_amount - fund_balance
                if transfer_amount > unified_balance:
                    transfer_amount = unified_balance  # 最多划转统一账户的全部余额
                
                print(f"\n⚠️  资金账户余额不足 ({fund_balance} {coin})，需要约 {required_amount} {coin}（含手续费）")
                print(f"   统一账户余额: {unified_balance} {coin}")
                print(f"   正在从统一账户划转 {transfer_amount} {coin} 到资金账户...")
                
                transfer_result = run_on_ec2(f"transfer bybit UNIFIED FUND {coin} {transfer_amount}")
                print(transfer_result)
                
                # 等待一下让划转完成
                time.sleep(1)

    # 确认
    print("\n" + "=" * 50)
    print("请确认提现信息:")
    print(f"  交易所: {exchange.upper()}")
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
    if exchange == "bybit":
        address = address.lower()
    cmd = f'withdraw {exchange} {coin} {network} {address} {amount}'
    if memo:
        cmd += f' {memo}'
    
    output = run_on_ec2(cmd)
    print(output)
