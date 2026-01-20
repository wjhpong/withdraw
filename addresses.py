#!/usr/bin/env python3
"""地址簿管理"""

import json
import os
from utils import ADDRESSES_FILE, select_option, detect_address_type, EXCHANGES, get_exchange_base


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


def manage_addresses(exchange: str = None):
    """管理地址簿"""
    # 获取当前交易所类型
    exchange_base = get_exchange_base(exchange) if exchange else None
    
    while True:
        addresses = load_addresses()
        
        # 过滤当前交易所的地址
        if exchange_base:
            filtered = [a for a in addresses if a.get('exchange') == exchange_base]
            exchange_name = dict(EXCHANGES).get(exchange, exchange.upper())
            title = f"📋 {exchange_name} 地址簿"
        else:
            filtered = addresses
            title = "📋 所有地址"
        
        print("\n" + "=" * 50)
        print(title)
        print("=" * 50)
        if filtered:
            for i, addr in enumerate(filtered, 1):
                addr_type = addr.get('type', 'unknown').upper()
                memo_str = f" (Memo: {addr['memo']})" if addr.get('memo') else ""
                # circle和REAP地址显示特殊标记
                coin_restriction = ""
                if addr.get('name', '').lower() == 'circle':
                    coin_restriction = " - 仅USDC"
                elif addr.get('name', '').lower() == 'reap':
                    coin_restriction = " - 仅USDC"
                print(f"  {i}. [{addr['name']}] ({addr_type}) {addr['address'][:25]}...{coin_restriction}{memo_str}")
        else:
            if exchange_base:
                print(f"  (暂无 {exchange_name} 的保存地址)")
            else:
                print("  (暂无保存的地址)")
        
        action = select_option("请选择操作:", ["添加新地址", "删除地址", "查看所有交易所地址", "返回"])
        
        if action == 0:  # 添加新地址
            _add_address(addresses, exchange_base)
        elif action == 1:  # 删除地址
            _delete_address(addresses, filtered)
        elif action == 2:  # 查看所有
            _show_all_addresses(addresses)
        else:
            break


def _add_address(addresses: list, default_exchange: str = None):
    """添加新地址"""
    # 选择交易所
    print("\n选择地址绑定的交易所:")
    exchange_bases = list(set(get_exchange_base(k) for k, _ in EXCHANGES))
    exchange_names = {"binance": "Binance", "bybit": "Bybit", "gate": "Gate.io"}
    exchange_options = [exchange_names.get(e, e) for e in exchange_bases]
    
    if default_exchange and default_exchange in exchange_bases:
        default_idx = exchange_bases.index(default_exchange)
        print(f"(当前交易所: {exchange_options[default_idx]})")
    
    ex_idx = select_option("选择交易所:", exchange_options, allow_back=True)
    if ex_idx == -1:
        return
    selected_exchange = exchange_bases[ex_idx]
    
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
        "memo": memo,
        "exchange": selected_exchange
    })
    save_addresses(addresses)
    print(f"\n✅ 地址 [{name}] 已保存到 {exchange_names.get(selected_exchange, selected_exchange)}!")


def _delete_address(addresses: list, filtered: list):
    """删除地址"""
    if not filtered:
        print("\n没有可删除的地址")
        return
    
    addr_options = [f"[{a['name']}] {a['address'][:25]}..." for a in filtered]
    addr_options.append("取消")
    del_idx = select_option("选择要删除的地址:", addr_options)
    
    if del_idx < len(filtered):
        # 找到在原始列表中的索引
        to_delete = filtered[del_idx]
        for i, a in enumerate(addresses):
            if a['name'] == to_delete['name'] and a['address'] == to_delete['address']:
                deleted = addresses.pop(i)
                save_addresses(addresses)
                print(f"\n✅ 地址 [{deleted['name']}] 已删除!")
                break


def _show_all_addresses(addresses: list):
    """显示所有交易所的地址"""
    exchange_names = {"binance": "Binance", "bybit": "Bybit", "gate": "Gate.io"}
    
    print("\n" + "=" * 50)
    print("📋 所有交易所地址")
    print("=" * 50)
    
    # 按交易所分组
    by_exchange = {}
    for addr in addresses:
        ex = addr.get('exchange', '未指定')
        if ex not in by_exchange:
            by_exchange[ex] = []
        by_exchange[ex].append(addr)
    
    for ex, addrs in by_exchange.items():
        ex_display = exchange_names.get(ex, ex)
        print(f"\n【{ex_display}】")
        for addr in addrs:
            addr_type = addr.get('type', 'unknown').upper()
            print(f"  - [{addr['name']}] ({addr_type}) {addr['address'][:25]}...")
    
    if not addresses:
        print("  (暂无保存的地址)")
    
    input("\n按回车返回...")
