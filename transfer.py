#!/usr/bin/env python3
"""账户划转"""

import json
from utils import run_on_ec2, select_option, select_exchange, get_exchange_base, get_exchange_display_name, input_amount, SSHError


class TransferError(Exception):
    """划转操作错误"""
    pass


def do_bitget_subaccount_transfer(exchange: str):
    """Bitget 子账户 → 主账户划转"""
    display_name = get_exchange_display_name(exchange)

    # 获取子账户列表
    print("\n正在获取子账户列表...")
    try:
        output = run_on_ec2("bitget_list_subaccounts")
    except SSHError as e:
        print(f"❌ 获取子账户列表失败: {e}")
        return

    try:
        sub_accounts = json.loads(output.strip())
    except json.JSONDecodeError as e:
        print(f"❌ 解析子账户列表失败: {e}")
        print(f"   原始输出: {output[:200]}...")
        return
    
    if not sub_accounts:
        print("没有子账户或子账户无资产")
        return
    
    # 显示子账户列表供选择
    sub_names = []
    for s in sub_accounts:
        uid = s.get('userId', '')
        name = s.get('name', uid)  # 使用名称，没有则显示 UID
        # 计算该子账户总资产
        assets = s.get('assetsList', [])
        total = sum(float(a.get('available', 0)) for a in assets)
        if total > 0:
            sub_names.append(f"[{name}] UID: {uid} (有 {len(assets)} 种资产)")
        else:
            sub_names.append(f"[{name}] UID: {uid} (无资产)")
    
    sub_idx = select_option("选择子账户:", sub_names, allow_back=True)
    
    if sub_idx == -1:
        return
    
    selected_sub = sub_accounts[sub_idx]
    sub_uid = selected_sub.get('userId', '')  # API 划转需要用 userId
    sub_name = selected_sub.get('name', sub_uid)
    assets_list = selected_sub.get('assetsList', [])
    
    # 只查找 USDT 余额
    usdt_balance = 0
    for asset in assets_list:
        if asset.get('coin', '').upper() == 'USDT':
            usdt_balance = float(asset.get('available', 0))
            break
    
    if usdt_balance <= 0:
        print(f"\n子账户 [{sub_name}] 没有 USDT 可划转")
        return
    
    # 显示划转信息
    print(f"\n📤 从: 子账户 [{sub_name}] (UID: {sub_uid})")
    print(f"📥 到: 主账户")
    print(f"💰 USDT 可用: {usdt_balance}")
    
    # 输入数量
    amount = input_amount(f"请输入划转数量 (最大 {usdt_balance}):")
    if amount is None:
        return
    
    if amount > usdt_balance:
        print(f"数量超过最大可划转量 {usdt_balance}")
        return
    
    coin = "USDT"
    
    # 确认
    print("\n" + "=" * 50)
    print("请确认划转信息:")
    print(f"  交易所: {display_name}")
    print(f"  从: 子账户 [{sub_name}]")
    print(f"  到: 主账户")
    print(f"  数量: {amount} USDT")
    print("=" * 50)
    
    if select_option("确认划转?", ["确认", "取消"]) != 0:
        print("已取消")
        return
    
    print("\n正在划转...")
    try:
        output = run_on_ec2(f"bitget_subaccount_transfer {sub_uid} from {coin} {amount}")
        print(output)
        if "error" in output.lower() or "失败" in output:
            print("\n⚠️  划转可能失败，请检查交易所确认")
        elif "success" in output.lower() or "成功" in output:
            print("\n✅ 划转成功")
    except SSHError as e:
        print(f"❌ 划转失败: {e}")


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
    try:
        output = run_on_ec2("gate_list_subaccounts")
    except SSHError as e:
        print(f"❌ 获取子账户列表失败: {e}")
        return

    try:
        # 解析 JSON 格式的子账户列表
        sub_accounts = json.loads(output.strip())
    except json.JSONDecodeError as e:
        print(f"❌ 解析子账户列表失败: {e}")
        print(f"   原始输出: {output[:200]}...")
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
    try:
        output = run_on_ec2(f"gate_subaccount_transfer {sub_uid} {direction} {coin} {amount}")
        print(output)
        if "error" in output.lower() or "失败" in output:
            print("\n⚠️  划转可能失败，请检查交易所确认")
        elif "success" in output.lower() or "成功" in output:
            print("\n✅ 划转成功")
    except SSHError as e:
        print(f"❌ 划转失败: {e}")


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
    elif exchange_base == "bitget":
        # Bitget: 子账户 → 主账户
        do_bitget_subaccount_transfer(exchange)
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
    try:
        output = run_on_ec2(f"transfer {exchange} {from_type} {to_type} {coin} {amount}")
        print(output)
        if "error" in output.lower() or "失败" in output:
            print("\n⚠️  划转可能失败，请检查交易所确认")
        elif "success" in output.lower() or "成功" in output:
            print("\n✅ 划转成功")
    except SSHError as e:
        print(f"❌ 划转失败: {e}")
