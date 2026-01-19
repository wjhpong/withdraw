#!/usr/bin/env python3
"""提现操作"""

from utils import run_on_ec2, select_option, input_amount, get_networks_for_type, detect_address_type
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
            addr_options.append(f"[{a['name']}] {a['address'][:25]}...")
    addr_options.append("输入新地址")
    
    addr_idx = select_option("请选择提现地址:", addr_options, allow_back=True)
    if addr_idx == -1:
        return
    if addr_idx < len(available_addresses):
        selected = available_addresses[addr_idx]

    # 输入币种
    if selected and selected.get('coins'):
        allowed_coins = selected['coins']
        coin_idx = select_option("请选择币种:", allowed_coins, allow_back=True)
        if coin_idx == -1:
            return
        coin = allowed_coins[coin_idx]
    else:
        coin = input("\n请输入币种 (如 USDT, 输入 0 返回): ").strip().upper()
        if not coin or coin == "0":
            return
    
    # 显示余额
    print(f"\n正在查询 {coin} 余额...")
    balance = get_coin_balance(exchange, coin)
    print(f"💰 {coin} 可用余额: {balance}")

    # 处理地址和网络
    if selected:
        address = selected['address']
        addr_type = selected.get('type', 'evm')
        memo = selected.get('memo')
        
        if selected.get('network'):
            network = selected['network']
            print(f"\n自动选择网络: {network}")
        else:
            networks = get_networks_for_type(addr_type)
            if len(networks) == 1:
                network = networks[0]
                print(f"\n自动选择网络: {network}")
            else:
                net_idx = select_option("请选择网络:", networks, allow_back=True)
                if net_idx == -1:
                    return
                network = networks[net_idx]
    else:
        address = input("\n请输入提现地址 (输入 0 返回): ").strip()
        if not address or address == "0":
            return
        
        addr_type = detect_address_type(address)
        if addr_type == "sui_apt":
            choice = select_option("SUI 和 APT 地址格式相同，请选择:", ["SUI", "APT (Aptos)"], allow_back=True)
            if choice == -1:
                return
            addr_type = "sui" if choice == 0 else "apt"
        
        networks = get_networks_for_type(addr_type)
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
    cmd = f'withdraw {exchange} {coin} {network} {address} {amount}'
    if memo:
        cmd += f' {memo}'
    
    output = run_on_ec2(cmd)
    print(output)
