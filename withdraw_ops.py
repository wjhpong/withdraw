#!/usr/bin/env python3
"""提现操作"""

import time
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from utils import run_on_ec2, select_option, select_exchange, get_exchange_base, get_exchange_display_name, input_amount, get_networks_for_type, get_networks_for_coin, detect_address_type, SSHError
from addresses import load_addresses, load_user_addresses
from balance import get_coin_balance


class WithdrawError(Exception):
    """提现操作错误"""
    pass


def _format_amount_for_transfer(amount: float, decimals: int = 6) -> str:
    """按精度向下截断金额，避免交易所精度报错"""
    try:
        q = Decimal(1).scaleb(-decimals)  # 10^-decimals
        value = Decimal(str(amount)).quantize(q, rounding=ROUND_DOWN)
        return format(value.normalize(), "f")
    except (InvalidOperation, ValueError, TypeError):
        return "0"


def _looks_like_error(output: str) -> bool:
    text = (output or "").lower()
    return (
        "error" in text
        or "失败" in output
        or "permission denied" in text
        or "accuracy err" in text
    )


def do_withdraw(exchange: str = None, user_id: str = None):
    """执行提现

    Args:
        exchange: 交易所 key
        user_id: 用户 ID，如果指定则使用用户专属地址簿
    """
    # 加载用户地址簿或全局地址簿
    if user_id:
        addresses = load_user_addresses(user_id)
    else:
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

    # eb65 的 Bybit 只能提现到 Circle 地址
    is_eb65_bybit = user_id == "eb65" and exchange_base == "bybit"

    # 选择地址
    selected = None
    addr_options = []
    for a in available_addresses:
        name_lower = a.get('name', '').lower()
        addr_type = a.get('type', '')

        if a.get('type') == 'fixed':
            coins_str = "/".join(a.get('coins', []))
            addr_options.append(f"[{a['name']}] {a.get('network', '')} - 仅{coins_str}")
        elif 'circle' in name_lower:
            # circle 相关地址，根据类型显示网络
            if addr_type == 'apt':
                addr_options.append(f"[{a['name']}] APT - 仅USDC")
            else:
                # EVM 类型的 circle 地址都走 SONIC
                addr_options.append(f"[{a['name']}] SONIC - 仅USDC")
        elif name_lower == 'reap':
            addr_options.append(f"[{a['name']}] MATIC - 仅USDC")
        else:
            addr_options.append(f"[{a['name']}] {a['address'][:25]}...")

    # eb65 的 Bybit 不允许输入新地址
    if not is_eb65_bybit:
        addr_options.append("输入新地址")
    
    addr_idx = select_option("请选择提现地址:", addr_options, allow_back=True)
    if addr_idx == -1:
        return
    if addr_idx < len(available_addresses):
        selected = available_addresses[addr_idx]
    else:
        selected = None

    # 输入币种
    # circle/circle2/reap/sonic-circle 地址只能提现USDC
    if selected:
        addr_name_lower = selected.get('name', '').lower().strip()
        # 这些地址只能提现USDC，自动设置，不要求输入
        is_circle_addr = addr_name_lower in ('circle', 'circle2', 'reap') or 'circle' in addr_name_lower
        if is_circle_addr:
            coin = 'USDC'
            print(f"\n⚠️  {selected['name']}地址只能提现USDC，已自动选择USDC")
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
    
    # 如果选择了circle/circle2地址但币种不是USDC，提示错误
    if selected and selected.get('name', '').lower() in ('circle', 'circle2') and coin.upper() != 'USDC':
        print(f"\n❌ 错误: circle地址只能提现USDC，不能提现{coin}")
        return
    
    # 如果选择了REAP地址但币种不是USDC，提示错误
    if selected and selected.get('name', '').lower() == 'reap' and coin.upper() != 'USDC':
        print(f"\n❌ 错误: REAP地址只能提现USDC，不能提现{coin}")
        return
    
    # 显示余额（同时查询现货和统一账户）
    print(f"\n正在查询 {coin} 余额...")
    
    def fmt_bal(bal):
        """格式化余额显示，避免科学计数法"""
        try:
            v = float(bal) if bal else 0
            return f"{v:.6f}".rstrip('0').rstrip('.') if v < 0.01 else f"{v:.2f}"
        except:
            return bal

    if exchange_base == "bybit":
        # Bybit: 查询 FUND 和 UNIFIED 账户
        fund_bal = get_coin_balance(exchange, coin, "FUND")
        unified_bal = get_coin_balance(exchange, coin, "UNIFIED")
        print(f"💰 {coin} 资金账户: {fmt_bal(fund_bal)}")
        print(f"💰 {coin} 统一账户: {fmt_bal(unified_bal)}")
    elif exchange_base == "binance":
        # Binance: 查询 SPOT 和 PM (Portfolio Margin) 账户
        spot_bal = get_coin_balance(exchange, coin, "SPOT")
        pm_bal = get_coin_balance(exchange, coin, "PM")
        print(f"💰 {coin} 现货账户: {fmt_bal(spot_bal)}")
        print(f"💰 {coin} 统一账户: {fmt_bal(pm_bal)}")
    elif exchange_base == "gate":
        # Gate.io: 查询 SPOT 现货账户
        spot_bal = get_coin_balance(exchange, coin, "SPOT")
        print(f"💰 {coin} 现货账户: {fmt_bal(spot_bal)}")
    elif exchange_base == "bitget":
        # Bitget: 查询现货账户
        spot_bal = get_coin_balance(exchange, coin, "SPOT")
        print(f"💰 {coin} 现货账户: {fmt_bal(spot_bal)}")

    # 处理地址和网络
    # 特殊地址强制使用固定网络
    addr_name_for_network = selected.get('name', '').lower() if selected else ''
    addr_type_for_network = selected.get('type', '') if selected else ''

    is_reap_address = addr_name_for_network == 'reap'
    is_circle_addr = 'circle' in addr_name_for_network
    is_circle_apt = is_circle_addr and addr_type_for_network == 'apt'
    is_circle_evm = is_circle_addr and addr_type_for_network == 'evm'

    if is_reap_address:
        network = "MATIC"
        print(f"\n⚠️  REAP地址只能使用Polygon网络，已自动选择MATIC")

        # 获取地址和memo
        address = selected['address']
        memo = selected.get('memo')
    elif is_circle_evm:
        # circle EVM 地址强制使用 SONIC 网络
        network = "SONIC"
        print(f"\n⚠️  {selected['name']}地址使用Sonic网络，已自动选择SONIC")
        address = selected['address']
        memo = selected.get('memo')
    elif is_circle_apt:
        # circle APT 地址强制使用 APT 网络
        network = "APT"
        print(f"\n⚠️  {selected['name']}地址使用Aptos网络，已自动选择APT")
        address = selected['address']
        memo = selected.get('memo')
    elif selected:
        address = selected['address']
        addr_type = selected.get('type', 'evm')
        memo = selected.get('memo')

        # 根据地址类型直接映射到网络
        type_to_network = {
            'sonic': 'SONIC',
            'polygon': 'MATIC',
            'sol': 'SOL',
            'sui': 'SUI',
            'apt': 'APT',
            'trc': 'TRC20',
            'atom': 'ATOM',
        }

        # EVM 地址需要选择具体网络
        # 包括: evm, eth, bsc, arb, op, matic, avax 等旧类型
        evm_types = ['evm', 'eth', 'bsc', 'arb', 'op', 'matic', 'avax', 'other']

        if addr_type in evm_types:
            # EVM 兼容地址，让用户选择网络
            evm_networks = ["ETH", "BSC", "ARBITRUM", "OPTIMISM", "MATIC", "AVAXC", "BASE", "LINEA", "MANTLE", "SONIC"]
            net_idx = select_option("请选择提现网络:", evm_networks, allow_back=True)
            if net_idx == -1:
                return
            network = evm_networks[net_idx]
        elif addr_type in type_to_network:
            network = type_to_network[addr_type]
            print(f"\n自动选择网络: {network}")
        elif selected.get('network'):
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
                    transfer_amount_str = _format_amount_for_transfer(transfer_amount, decimals=6)

                    print(f"\n⚠️  资金账户余额不足 ({fund_balance} {coin})，需要约 {required_amount} {coin}（含手续费）")
                    print(f"   统一账户余额: {unified_balance} {coin}")
                    print(f"   正在从统一账户划转 {transfer_amount_str} {coin} 到资金账户...")

                    if float(transfer_amount_str) > 0:
                        transfer_result = run_on_ec2(f"transfer {exchange} UNIFIED FUND {coin} {transfer_amount_str}")
                        print(transfer_result)
                        if _looks_like_error(transfer_result):
                            print("⚠️  自动划转失败，将继续按当前资金账户余额尝试提现")
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

    # 自动划转后再次检查资金账户余额，至少要覆盖提现数量
    if exchange_base == "bybit":
        latest_fund_balance = float(get_coin_balance(exchange, coin, "FUND") or 0)
        if latest_fund_balance < float(amount):
            print(f"❌ 资金账户余额不足: 当前 {latest_fund_balance} {coin}，提现需要 {amount} {coin}")
            print("   请先手动划转到资金账户后重试")
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
        if "permission denied" in output_lower:
            print("\n❌ 提现权限不足：请在 Bybit API 设置中开启 Withdraw 权限，并确认 IP 白名单包含 EC2 出口 IP")
        elif "error" in output_lower or "failed" in output_lower or "失败" in output:
            print("\n⚠️  提现可能失败，请检查交易所确认")
        elif "success" in output_lower or "成功" in output:
            print("\n✅ 提现请求已提交")
    except SSHError as e:
        print(f"\n❌ 提现请求失败: {e}")
