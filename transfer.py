#!/usr/bin/env python3
"""账户划转"""

import json
from utils import run_on_ec2, select_option, select_exchange, get_exchange_base, get_exchange_display_name, input_amount, SSHError


class TransferError(Exception):
    """划转操作错误"""
    pass


def _show_bybit_unified_balances(exchange: str):
    """显示 Bybit 统一账户常用币种余额"""
    print("\n" + "=" * 50)
    print("📦 统一账户余额 (UNIFIED):")
    print("=" * 50)
    common_coins = ["USDT", "USDC", "BTC", "ETH"]
    has_balance = False
    for coin in common_coins:
        try:
            output = run_on_ec2(f"account_balance {exchange} UNIFIED {coin}").strip()
            if not output:
                continue
            bal = float(output)
            if bal > 0:
                has_balance = True
                print(f"  {coin}: {bal:.8f}".rstrip("0").rstrip("."))
        except (SSHError, ValueError):
            continue

    if not has_balance:
        print("  统一账户暂无余额")


def _show_binance_sub_assets(exchange: str, sub_email: str):
    """查询并显示 Binance 子账户资产"""
    try:
        bal_output = run_on_ec2(f"binance_subaccount_assets {exchange} {sub_email}")
        try:
            parsed = json.loads(bal_output.strip())
            # 兼容不同返回格式：可能是 {"balances": [...]} 或直接 [...]
            if isinstance(parsed, dict):
                assets = parsed.get('balances', parsed.get('assets', []))
            elif isinstance(parsed, list):
                assets = parsed
            else:
                assets = []
            if assets:
                print(f"\n子账户 [{sub_email}] 资产:")
                for asset in assets:
                    if isinstance(asset, dict):
                        asset_name = asset.get('asset', '')
                        free = float(asset.get('free', 0))
                        if free > 0:
                            if asset_name == "BTC":
                                print(f"  {asset_name}: {free:,.8f}")
                            else:
                                print(f"  {asset_name}: {free:,.4f}")
                    else:
                        print(f"  {asset}")
            else:
                print("  (无资产)")
        except json.JSONDecodeError:
            print(bal_output)
    except SSHError as e:
        print(f"查询子账户资产失败: {e}")


def do_binance_subaccount_transfer(exchange: str):
    """Binance 子账户划转 (子账户→主账户 / 主账户→子账户 / 子账户→子账户)"""
    display_name = get_exchange_display_name(exchange)

    # Dennis 的子账户列表
    sub_accounts = [
        "matrons_indigo2l@icloud.com",
        "back-bulldog6k@icloud.com",
        "panic_chisel_1h@icloud.com",
    ]

    # 选择划转方向
    direction_idx = select_option("选择划转方向:", [
        "子账户 → 主账户",
        "主账户 → 子账户",
        "子账户 → 子账户",
    ], allow_back=True)

    if direction_idx == -1:
        return

    # 选择来源
    if direction_idx == 0:
        # 子账户 → 主账户
        from_idx = select_option("选择来源子账户:", sub_accounts, allow_back=True)
        if from_idx == -1:
            return
        from_email = sub_accounts[from_idx]
        to_email = None
        from_str = f"子账户 [{from_email}]"
        to_str = "主账户"
    elif direction_idx == 1:
        # 主账户 → 子账户
        to_idx = select_option("选择目标子账户:", sub_accounts, allow_back=True)
        if to_idx == -1:
            return
        from_email = None
        to_email = sub_accounts[to_idx]
        from_str = "主账户"
        to_str = f"子账户 [{to_email}]"
    else:
        # 子账户 → 子账户
        from_idx = select_option("选择来源子账户:", sub_accounts, allow_back=True)
        if from_idx == -1:
            return
        from_email = sub_accounts[from_idx]
        # 目标子账户排除来源
        to_options = [s for i, s in enumerate(sub_accounts) if i != from_idx]
        to_idx = select_option("选择目标子账户:", to_options, allow_back=True)
        if to_idx == -1:
            return
        to_email = to_options[to_idx]
        from_str = f"子账户 [{from_email}]"
        to_str = f"子账户 [{to_email}]"

    print(f"\n📤 从: {from_str}")
    print(f"📥 到: {to_str}")

    # 查询来源账户资产
    if from_email:
        print(f"\n正在查询 {from_str} 资产...")
        _show_binance_sub_assets(exchange, from_email)
    else:
        print(f"\n正在查询主账户余额...")
        try:
            output = run_on_ec2(f"balance {exchange}")
            print(output)
        except SSHError as e:
            print(f"查询余额失败: {e}")

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
    print(f"  从: {from_str}")
    print(f"  到: {to_str}")
    print(f"  币种: {coin}")
    print(f"  数量: {amount}")
    print("=" * 50)

    if select_option("确认划转?", ["确认", "取消"]) != 0:
        print("已取消")
        return

    # 构建命令参数: binance_subaccount_transfer {exchange} {from_email} {to_email} {coin} {amount}
    # from_email 为空时用 "MAIN" 表示主账户
    from_param = from_email if from_email else "MAIN"
    to_param = to_email if to_email else "MAIN"

    print("\n正在划转...")
    try:
        output = run_on_ec2(f"binance_subaccount_transfer {exchange} {from_param} {to_param} {coin} {amount}")
        print(output)
        if "error" in output.lower() or "失败" in output:
            print("\n⚠️  划转可能失败，请检查交易所确认")
        elif "success" in output.lower() or "成功" in output:
            print("\n✅ 划转成功")
    except SSHError as e:
        print(f"❌ 划转失败: {e}")


def do_bitget_subaccount_transfer(exchange: str):
    """Bitget 主账户 ↔ 子账户划转"""
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
        output = run_on_ec2(f"bitget_list_subaccounts {exchange}")
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
        print("没有子账户")
        return

    # 显示子账户列表供选择
    sub_names = []
    for s in sub_accounts:
        uid = s.get('userId', '')
        name = s.get('name', uid)
        assets = s.get('assetsList', [])
        # 计算 USDT 余额
        usdt_bal = 0
        for a in assets:
            if a.get('coin', '').upper() == 'USDT':
                usdt_bal = float(a.get('available', 0))
                break
        sub_names.append(f"{name} (USDT: {usdt_bal:,.2f})")

    sub_idx = select_option("选择子账户:", sub_names, allow_back=True)

    if sub_idx == -1:
        return

    selected_sub = sub_accounts[sub_idx]
    sub_uid = selected_sub.get('userId', '')
    sub_name = selected_sub.get('name', sub_uid)
    assets_list = selected_sub.get('assetsList', [])

    # 显示方向信息
    if direction == "to":
        print(f"\n📤 从: 主账户")
        print(f"📥 到: 子账户 [{sub_name}]")
        # 显示主账户余额
        print(f"\n正在查询主账户余额...")
        try:
            bal_output = run_on_ec2(f"balance {exchange}")
            print(bal_output)
        except SSHError as e:
            print(f"查询余额失败: {e}")
    else:
        print(f"\n📤 从: 子账户 [{sub_name}]")
        print(f"📥 到: 主账户")
        # 显示该子账户余额
        print(f"\n子账户 [{sub_name}] 资产:")
        for asset in assets_list:
            coin_name = asset.get('coin', '')
            available = float(asset.get('available', 0))
            if available > 0:
                print(f"  {coin_name}: {available}")

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
        output = run_on_ec2(f"bitget_subaccount_transfer {exchange} {sub_uid} {direction} {coin} {amount}")
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
    elif exchange_base == "aster":
        # Aster: 现货 ↔ 合约 (使用 aster.py)
        from aster import do_aster_transfer
        do_aster_transfer(exchange)
        return
    else:
        # Bybit: 统一账户 ↔ 现货账户
        transfer_options = [
            ("UNIFIED", "FUND", "统一账户 → 现货账户"),
            ("FUND", "UNIFIED", "现货账户 → 统一账户"),
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
    if exchange_base == "bybit" and from_type == "UNIFIED":
        _show_bybit_unified_balances(exchange)
    else:
        output = run_on_ec2(f"balance {exchange}")
        print(output)

    # Binance PM 划转时显示最大可划转金额
    if exchange_base == "binance" and from_type == "PORTFOLIO_MARGIN":
        try:
            pm_output = run_on_ec2(f"pm_max_withdraw {exchange}")
            pm_data = json.loads(pm_output.strip())
            if "totalAvailableBalance" in pm_data:
                max_withdraw = float(pm_data["totalAvailableBalance"])
                print(f"\n💡 统一账户最大可划转金额: ${max_withdraw:,.2f}")
                print("   (受持仓保证金和维持保证金限制)")
        except:
            pass
    
    # 输入币种
    coin = input("\n请输入要划转的币种 (如 USDT, 输入 0 返回): ").strip().upper()
    if not coin or coin == "0":
        return
    
    # 输入数量
    amount = input_amount("请输入划转数量:")
    if amount is None:
        return
    
    # 确认
    # 显示友好的账户名称
    from_display = {"FUND": "现货账户", "UNIFIED": "统一账户", "SPOT": "现货账户", "PORTFOLIO_MARGIN": "统一账户"}.get(from_type, from_type)
    to_display = {"FUND": "现货账户", "UNIFIED": "统一账户", "SPOT": "现货账户", "PORTFOLIO_MARGIN": "统一账户"}.get(to_type, to_type)

    print(f"\n确认划转 {amount} {coin}: {from_display} → {to_display}")

    if select_option("", ["确认", "取消"]) != 0:
        print("已取消")
        return

    print("正在划转...")
    try:
        output = run_on_ec2(f"transfer {exchange} {from_type} {to_type} {coin} {amount}")
        # 只显示关键结果
        if "成功" in output or "✅" in output:
            print("✅ 划转成功")
        elif "失败" in output or "❌" in output or "error" in output.lower():
            # 提取错误信息
            for line in output.split('\n'):
                if "失败" in line or "❌" in line or "error" in line.lower():
                    print(line)
    except SSHError as e:
        print(f"❌ 划转失败: {e}")
