#!/usr/bin/env python3
"""地址簿管理"""

import json
import os
from utils import ADDRESSES_FILE, select_option, detect_address_type


def load_addresses() -> list:
    """加载地址簿"""
    if os.path.exists(ADDRESSES_FILE):
        with open(ADDRESSES_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("addresses", [])
    return []


def save_addresses(addresses: list):
    """保存地址簿"""
    with open(ADDRESSES_FILE, "w", encoding="utf-8") as f:
        json.dump({"addresses": addresses}, f, ensure_ascii=False, indent=2)


def manage_addresses():
    """管理地址簿"""
    while True:
        addresses = load_addresses()
        
        print("\n" + "=" * 50)
        print("当前保存的地址:")
        print("=" * 50)
        if addresses:
            for i, addr in enumerate(addresses, 1):
                addr_type = addr.get('type', 'unknown').upper()
                memo_str = f" (Memo: {addr['memo']})" if addr.get('memo') else ""
                print(f"  {i}. [{addr['name']}] ({addr_type}) {addr['address'][:25]}...{memo_str}")
        else:
            print("  (暂无保存的地址)")
        
        action = select_option("请选择操作:", ["添加新地址", "删除地址", "返回主菜单"])
        
        if action == 0:  # 添加新地址
            _add_address(addresses)
        elif action == 1:  # 删除地址
            _delete_address(addresses)
        else:
            break


def _add_address(addresses: list):
    """添加新地址"""
    name = input("\n请输入地址备注名 (如 'jiaojiao'): ").strip()
    if not name:
        print("已取消")
        return
    
    address = input("请输入地址: ").strip()
    if not address:
        print("已取消")
        return
    
    # 自动检测地址类型
    addr_type = detect_address_type(address)
    type_names = {
        "evm": "EVM (以太坊/BSC/ARB等)", 
        "trc": "TRC (波场)", 
        "sol": "SOL (Solana)",
        "sui": "SUI",
        "apt": "APT (Aptos)",
        "sui_apt": "SUI 或 APT (需要选择)",
        "other": "其他"
    }
    print(f"\n检测到地址类型: {type_names.get(addr_type, addr_type)}")
    
    type_options = ["EVM (0x短地址)", "TRC (T地址)", "SOL (Solana)", "SUI", "APT (Aptos)", "其他"]
    type_map = ["evm", "trc", "sol", "sui", "apt", "other"]
    
    if addr_type == "sui_apt":
        print("SUI 和 APT 地址格式相同，请选择:")
        confirm_type = select_option("选择地址类型:", ["SUI", "APT (Aptos)"])
        addr_type = "sui" if confirm_type == 0 else "apt"
    else:
        confirm_type = select_option("确认地址类型:", type_options)
        addr_type = type_map[confirm_type]
    
    memo = input("请输入 Memo/Tag (没有直接回车跳过): ").strip() or None
    
    addresses.append({
        "name": name,
        "address": address,
        "type": addr_type,
        "memo": memo
    })
    save_addresses(addresses)
    print(f"\n✅ 地址 [{name}] 已保存!")


def _delete_address(addresses: list):
    """删除地址"""
    if not addresses:
        print("\n没有可删除的地址")
        return
    
    addr_options = [f"[{a['name']}] {a['address'][:25]}..." for a in addresses]
    addr_options.append("取消")
    del_idx = select_option("选择要删除的地址:", addr_options)
    
    if del_idx < len(addresses):
        deleted = addresses.pop(del_idx)
        save_addresses(addresses)
        print(f"\n✅ 地址 [{deleted['name']}] 已删除!")
