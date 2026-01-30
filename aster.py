#!/usr/bin/env python3
"""Aster 交易所专用功能"""

from utils import run_on_ec2, select_option, get_exchange_display_name, input_amount, SSHError


def show_aster_margin_ratio(exchange: str = "aster"):
    """查询 Aster 合约账户保证金率和持仓信息"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 合约账户状态...")

    try:
        output = run_on_ec2(f"aster_margin_ratio {exchange}")
        print(output)
    except SSHError as e:
        print(f"❌ 查询失败: {e}")


def do_aster_transfer(exchange: str):
    """Aster 现货 ↔ 合约划转"""
    display_name = get_exchange_display_name(exchange)

    # 选择划转方向
    transfer_options = [
        ("SPOT_FUTURE", "现货 → 合约"),
        ("FUTURE_SPOT", "合约 → 现货"),
    ]
    option_names = [opt[1] for opt in transfer_options]
    transfer_idx = select_option("选择划转方向:", option_names, allow_back=True)
    if transfer_idx == -1:
        return

    direction = transfer_options[transfer_idx][0]
    direction_display = transfer_options[transfer_idx][1]

    # 显示账户余额
    print(f"\n正在查询账户余额...")
    try:
        output = run_on_ec2(f"balance {exchange}")
        print(output)
    except SSHError as e:
        print(f"❌ 查询余额失败: {e}")

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
    print(f"  方向: {direction_display}")
    print(f"  币种: {coin}")
    print(f"  数量: {amount}")
    print("=" * 50)

    if select_option("确认划转?", ["确认", "取消"]) != 0:
        print("已取消")
        return

    print("\n正在划转...")
    try:
        output = run_on_ec2(f"aster_transfer {exchange} {direction} {coin} {amount}")
        print(output)
        if "error" in output.lower() or "失败" in output:
            print("\n⚠️  划转可能失败，请检查交易所确认")
        elif "tranId" in output or "成功" in output:
            print("\n✅ 划转成功")
    except SSHError as e:
        print(f"❌ 划转失败: {e}")
