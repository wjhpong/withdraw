#!/usr/bin/env python3
"""地址簿管理 - 支持按用户分类"""

import json
import os
from utils import ADDRESSES_FILE, select_option, detect_address_type, EXCHANGES, get_exchange_base


class AddressError(Exception):
    """地址簿操作错误"""
    pass


def load_addresses_data() -> dict:
    """加载完整地址簿数据"""
    if not os.path.exists(ADDRESSES_FILE):
        return {"addresses": [], "user_addresses": {}}

    try:
        with open(ADDRESSES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                print(f"⚠️  地址簿格式错误，应为 JSON 对象")
                return {"addresses": [], "user_addresses": {}}
            # 兼容旧格式
            if "user_addresses" not in data:
                data["user_addresses"] = {}
            return data
    except json.JSONDecodeError as e:
        print(f"❌ 地址簿 JSON 格式错误: {e}")
        return {"addresses": [], "user_addresses": {}}
    except IOError as e:
        print(f"❌ 读取地址簿失败: {e}")
        return {"addresses": [], "user_addresses": {}}


def load_addresses() -> list:
    """加载地址簿（兼容旧代码）"""
    return load_addresses_data().get("addresses", [])


def load_user_addresses(user_id: str) -> list:
    """加载用户的地址簿"""
    data = load_addresses_data()
    return data.get("user_addresses", {}).get(user_id, [])


def save_addresses_data(data: dict):
    """保存完整地址簿数据"""
    try:
        with open(ADDRESSES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"❌ 保存地址簿失败: {e}")
        raise AddressError(f"保存失败: {e}")


def save_addresses(addresses: list):
    """保存地址簿（兼容旧代码）"""
    data = load_addresses_data()
    data["addresses"] = addresses
    save_addresses_data(data)


def save_user_addresses(user_id: str, addresses: list):
    """保存用户的地址簿"""
    data = load_addresses_data()
    if "user_addresses" not in data:
        data["user_addresses"] = {}
    data["user_addresses"][user_id] = addresses
    save_addresses_data(data)


def manage_addresses(exchange: str = None, user_id: str = None):
    """管理地址簿

    Args:
        exchange: 交易所 key
        user_id: 用户 ID，如果指定则使用用户专属地址簿
    """
    from utils import load_config

    # 获取当前交易所类型
    exchange_base = get_exchange_base(exchange) if exchange else None

    # 获取用户名用于显示
    user_name = None
    if user_id:
        config = load_config()
        user_name = config.get("users", {}).get(user_id, {}).get("name", user_id)

    while True:
        # 加载用户地址簿或全局地址簿
        if user_id:
            addresses = load_user_addresses(user_id)
        else:
            addresses = load_addresses()

        # 过滤当前交易所的地址
        if exchange_base:
            filtered = [a for a in addresses if a.get('exchange') == exchange_base]
            exchange_name = dict(EXCHANGES).get(exchange, exchange.upper())
            if user_name:
                title = f"📋 {user_name} - {exchange_name} 地址簿"
            else:
                title = f"📋 {exchange_name} 地址簿"
        else:
            filtered = addresses
            if user_name:
                title = f"📋 {user_name} 的地址簿"
            else:
                title = "📋 所有地址"

        print("\n" + "=" * 50)
        print(title)
        print("=" * 50)
        if filtered:
            for i, addr in enumerate(filtered, 1):
                addr_type = addr.get('type', 'unknown').upper()
                memo_str = f" (Memo: {addr['memo']})" if addr.get('memo') else ""
                # 显示币种限制
                coin_restriction = ""
                coins = addr.get('coins', [])
                if coins:
                    coin_restriction = f" - 仅{'/'.join(coins)}"
                elif addr.get('name', '').lower() == 'circle':
                    coin_restriction = " - 仅USDC"
                print(f"  {i}. [{addr['name']}] ({addr_type}) {addr['address'][:25]}...{coin_restriction}{memo_str}")
        else:
            if exchange_base:
                print(f"  (暂无保存地址)")
            else:
                print("  (暂无保存的地址)")

        action = select_option("请选择操作:", ["添加新地址", "删除地址", "查看所有地址", "返回"])

        if action == 0:  # 添加新地址
            _add_address(addresses, exchange_base, user_id)
        elif action == 1:  # 删除地址
            _delete_address(addresses, filtered, user_id)
        elif action == 2:  # 查看所有
            _show_all_addresses(addresses, user_name)
        else:
            break


def _add_address(addresses: list, default_exchange: str = None, user_id: str = None):
    """添加新地址"""
    # 选择交易所
    print("\n选择地址绑定的交易所:")
    exchange_bases = list(set(get_exchange_base(k) for k, _ in EXCHANGES))
    exchange_names = {"binance": "Binance", "bybit": "Bybit", "gate": "Gate.io", "bitget": "Bitget"}
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

    # 检查名称是否已存在
    for addr in addresses:
        if addr.get('name', '').lower() == name.lower() and addr.get('exchange') == selected_exchange:
            print(f"❌ 该交易所已存在同名地址 [{name}]")
            return

    address = input("请输入地址: ").strip()
    if not address:
        print("已取消")
        return

    # 基本地址格式验证
    if len(address) < 20:
        print(f"❌ 地址太短，请检查")
        return

    # 自动检测地址类型
    addr_type = detect_address_type(address)
    type_names = {
        "evm": "EVM (0x地址)",
        "sol": "SOL (Solana)",
        "sui": "SUI",
        "apt": "APT (Aptos)",
        "sui_apt": "SUI 或 APT (需要选择)",
        "other": "其他"
    }
    print(f"\n检测到地址类型: {type_names.get(addr_type, addr_type)}")

    # Binance 支持的常用网络
    type_options = [
        "ETH (ERC20)",
        "BSC (BEP20)",
        "ARB (Arbitrum)",
        "OP (Optimism)",
        "MATIC (Polygon)",
        "SOL (Solana)",
        "TRX (TRC20)",
        "AVAX (Avalanche C-Chain)",
        "ATOM (Cosmos)",
        "SUI",
        "APT (Aptos)",
        "Sonic",
        "其他"
    ]
    type_map = ["eth", "bsc", "arb", "op", "matic", "sol", "trx", "avax", "atom", "sui", "apt", "sonic", "other"]

    if addr_type == "sui_apt":
        print("SUI 和 APT 地址格式相同，请选择:")
        confirm_type = select_option("选择地址类型:", ["SUI", "APT (Aptos)"])
        addr_type = "sui" if confirm_type == 0 else "apt"
    else:
        confirm_type = select_option("选择网络:", type_options)
        addr_type = type_map[confirm_type]

    memo = input("请输入 Memo/Tag (没有直接回车跳过): ").strip() or None

    addresses.append({
        "name": name,
        "address": address,
        "type": addr_type,
        "memo": memo,
        "exchange": selected_exchange
    })

    try:
        if user_id:
            save_user_addresses(user_id, addresses)
        else:
            save_addresses(addresses)
        print(f"\n✅ 地址 [{name}] 已保存到 {exchange_names.get(selected_exchange, selected_exchange)}!")
    except AddressError:
        # 回滚添加
        addresses.pop()
        print("   地址未添加")


def _delete_address(addresses: list, filtered: list, user_id: str = None):
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
                try:
                    if user_id:
                        save_user_addresses(user_id, addresses)
                    else:
                        save_addresses(addresses)
                    print(f"\n✅ 地址 [{deleted['name']}] 已删除!")
                except AddressError:
                    # 回滚删除
                    addresses.insert(i, deleted)
                    print("   地址未删除")
                break


def _show_all_addresses(addresses: list, user_name: str = None):
    """显示所有交易所的地址"""
    exchange_names = {"binance": "Binance", "bybit": "Bybit", "gate": "Gate.io", "bitget": "Bitget"}

    print("\n" + "=" * 50)
    if user_name:
        print(f"📋 {user_name} 的所有地址")
    else:
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
