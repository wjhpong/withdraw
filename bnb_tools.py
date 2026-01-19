#!/usr/bin/env python3
"""BNB 工具 - 抵扣开关和小额资产转换"""

from utils import run_on_ec2, select_option, select_exchange


def toggle_bnb_burn():
    """BNB 抵扣开关"""
    exchange = select_exchange(binance_only=True)
    if not exchange:
        return
    
    print(f"\n正在查询 BNB 抵扣状态...")
    output = run_on_ec2(f"bnb_burn_status {exchange}")
    print(output)
    
    action = select_option("选择操作:", [
        "开启现货手续费 BNB 抵扣",
        "关闭现货手续费 BNB 抵扣",
        "返回"
    ], allow_back=True)
    
    if action == -1 or action == 2:
        return
    
    enable = "true" if action == 0 else "false"
    
    print(f"\n正在{'开启' if action == 0 else '关闭'} BNB 抵扣...")
    output = run_on_ec2(f"bnb_burn_toggle {exchange} {enable}")
    print(output)


def convert_dust_to_bnb():
    """小额资产转换 BNB"""
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


def manage_bnb_tools():
    """BNB 工具菜单"""
    while True:
        action = select_option("BNB 工具:", [
            "BNB 抵扣开关",
            "小额资产转 BNB",
            "返回主菜单"
        ])
        
        if action == 0:
            toggle_bnb_burn()
        elif action == 1:
            convert_dust_to_bnb()
        else:
            break
        
        input("\n按回车继续...")
