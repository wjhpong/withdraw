#!/usr/bin/env python3
"""BNB 工具 - 抵扣开关、小额资产转换、市价买入"""

from utils import run_on_ec2, select_option, select_exchange, input_amount, get_exchange_display_name


def toggle_bnb_burn(exchange: str = None):
    """BNB 抵扣开关"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return
    
    print(f"\n正在查询 BNB 抵扣状态...")
    output = run_on_ec2(f"bnb_burn_status {exchange}")
    print(output)
    
    action = select_option("选择操作:", [
        "开启现货手续费 BNB 抵扣",
        "关闭现货手续费 BNB 抵扣",
        "开启杠杆利息 BNB 抵扣",
        "关闭杠杆利息 BNB 抵扣",
        "返回"
    ], allow_back=True)
    
    if action == -1 or action == 4:
        return
    
    if action in [0, 1]:
        # 现货手续费
        enable = "true" if action == 0 else "false"
        print(f"\n正在{'开启' if action == 0 else '关闭'}现货手续费 BNB 抵扣...")
        output = run_on_ec2(f"bnb_burn_toggle {exchange} spot {enable}")
    else:
        # 杠杆利息
        enable = "true" if action == 2 else "false"
        print(f"\n正在{'开启' if action == 2 else '关闭'}杠杆利息 BNB 抵扣...")
        output = run_on_ec2(f"bnb_burn_toggle {exchange} interest {enable}")
    print(output)


def convert_dust_to_bnb(exchange: str = None):
    """小额资产转换 BNB"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return
    
    print(f"\n正在查询可转换的小额资产...")
    output = run_on_ec2(f"dust_list {exchange}")
    print(output)
    
    if "没有可转换" in output or "error" in output.lower():
        return
    
    confirm = select_option("确认将小额资产转换为 BNB?", ["确认转换", "取消"], allow_back=True)
    if confirm != 0:
        print("已取消")
        return
    
    print(f"\n正在转换小额资产...")
    output = run_on_ec2(f"dust_convert {exchange}")
    print(output)


def query_bnb_balance(exchange: str = None):
    """查询 BNB 持仓"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return
    
    display_name = get_exchange_display_name(exchange)
    
    print(f"\n正在查询 {display_name} BNB 持仓...")
    
    # 查询现货账户 BNB
    spot_bnb = run_on_ec2(f"account_balance {exchange} SPOT BNB").strip()
    
    # 查询统一账户 BNB
    unified_bnb = run_on_ec2(f"account_balance {exchange} UNIFIED BNB").strip()
    
    # 查询理财持仓 BNB
    earn_bnb = run_on_ec2(f"account_balance {exchange} EARN BNB").strip()
    
    # 查询 BNB 当前价格
    price_output = run_on_ec2(f"bnb_price {exchange} USDT").strip()
    bnb_price = 0.0
    if "价格:" in price_output:
        try:
            bnb_price = float(price_output.split("价格:")[1].split()[0])
        except:
            pass
    
    # 计算总量和价值
    try:
        spot_val = float(spot_bnb) if spot_bnb and spot_bnb != "0" else 0
        unified_val = float(unified_bnb) if unified_bnb and unified_bnb != "0" else 0
        earn_val = float(earn_bnb) if earn_bnb and earn_bnb != "0" else 0
        total = spot_val + unified_val + earn_val
    except:
        spot_val = unified_val = earn_val = total = 0
    
    print("\n" + "=" * 50)
    print(f"💎 {display_name} BNB 持仓")
    print("=" * 50)
    print(f"  📦 现货账户:     {spot_val:.8f} BNB")
    print(f"  📊 统一账户:     {unified_val:.8f} BNB")
    print(f"  💰 理财持仓:     {earn_val:.8f} BNB")
    print("-" * 50)
    print(f"  📋 总计:         {total:.8f} BNB")
    if bnb_price > 0:
        total_usd = total * bnb_price
        print(f"  💵 总价值:       ${total_usd:.2f} (BNB≈${bnb_price:.2f})")


def quick_buy_bnb_usdt(exchange: str = None):
    """快捷小额 USDT 买 BNB"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return
    
    # 查询 USDT 余额和 BNB 价格
    print(f"\n正在查询...")
    output = run_on_ec2(f"balance {exchange}")
    
    # 解析 USDT 余额
    usdt_balance = "0"
    for line in output.split('\n'):
        if line.upper().startswith("USDT"):
            parts = line.split()
            if len(parts) >= 2:
                usdt_balance = parts[1]
                break
    
    # 查询 BNB 价格
    price_output = run_on_ec2(f"bnb_price {exchange} USDT")
    print(f"💰 USDT 可用: {usdt_balance}")
    print(price_output)
    
    # 直接输入金额
    amount = input_amount("请输入 USDT 金额 (小额即可):")
    if amount is None:
        return
    
    # 确认
    confirm = select_option(f"确认用 {amount} USDT 市价买入 BNB?", ["确认买入", "取消"], allow_back=True)
    if confirm != 0:
        print("已取消")
        return
    
    print(f"\n正在市价买入 BNB...")
    output = run_on_ec2(f"buy_bnb {exchange} USDT {amount}")
    print(output)


def manage_bnb_tools(exchange: str = None):
    """BNB 工具菜单"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return
    
    while True:
        action = select_option("BNB 工具:", [
            "BNB 抵扣开关",
            "小额资产转 BNB",
            "小额 USDT 买 BNB",
            "BNB 持仓查询",
            "返回"
        ])
        
        if action == 0:
            toggle_bnb_burn(exchange)
        elif action == 1:
            convert_dust_to_bnb(exchange)
        elif action == 2:
            quick_buy_bnb_usdt(exchange)
        elif action == 3:
            query_bnb_balance(exchange)
        else:
            break
        
        input("\n按回车继续...")
