#!/usr/bin/env python3
"""交易功能 - 稳定币交易、撤单、市价卖出、永续平仓"""

import json
import requests
from decimal import Decimal, ROUND_DOWN
from utils import (
    run_on_ec2, select_option, input_amount, select_exchange,
    get_exchange_display_name, get_exchange_base, SSHError
)
from balance import get_coin_price

# 稳定币列表
STABLECOINS = ['USDT', 'USDC', 'USD1', 'BUSD', 'TUSD', 'FDUSD', 'DAI', 'USDD']
# 最小显示价值
MIN_DISPLAY_VALUE = 10

# 缓存交易对信息
_symbol_info_cache = {}


def get_binance_lot_size(symbol: str) -> dict:
    """获取 Binance 交易对的 LOT_SIZE 信息"""
    if symbol in _symbol_info_cache:
        return _symbol_info_cache[symbol]

    try:
        url = f"https://api.binance.com/api/v3/exchangeInfo?symbol={symbol}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for s in data.get("symbols", []):
                if s.get("symbol") == symbol:
                    for f in s.get("filters", []):
                        if f.get("filterType") == "LOT_SIZE":
                            info = {
                                "stepSize": f.get("stepSize", "1"),
                                "minQty": f.get("minQty", "0"),
                                "maxQty": f.get("maxQty", "99999999")
                            }
                            _symbol_info_cache[symbol] = info
                            return info
    except Exception:
        pass
    return None


def adjust_quantity_for_lot_size(qty: float, symbol: str, exchange_base: str) -> float:
    """根据 LOT_SIZE 调整数量"""
    if exchange_base != "binance":
        return qty

    lot_info = get_binance_lot_size(symbol)
    if not lot_info:
        return qty

    step_size = Decimal(lot_info["stepSize"])
    qty_decimal = Decimal(str(qty))

    # 向下取整到 stepSize 的倍数
    adjusted = (qty_decimal // step_size) * step_size

    return float(adjusted)


# ===================== 稳定币交易 =====================

def do_stablecoin_trade(exchange: str = None):
    """稳定币交易"""
    print("\n=== 稳定币交易 ===")

    if exchange:
        exchange_base = get_exchange_base(exchange)
        if exchange_base == "binance":
            # Binance 支持多个稳定币交易对
            pair_idx = select_option("选择交易对:", [
                "USDC/USDT",
                "BFUSD/USDT",
                "USD1/USDT",
                "返回"
            ])
            if pair_idx == 0:
                trade_usdc_usdt_binance(exchange)
            elif pair_idx == 1:
                trade_bfusd_usdt(exchange)
            elif pair_idx == 2:
                trade_usd1_usdt(exchange)
            return
        elif exchange_base == "bybit":
            # Bybit 只支持 USDC/USDT
            trade_usdc_usdt(exchange)
            return

    pair_idx = select_option("选择交易对:", [
        "USDC/USDT (Bybit)",
        "BFUSD/USDT (Binance)",
        "USD1/USDT (Binance)",
        "返回"
    ])

    if pair_idx == 3:
        return

    if pair_idx == 0:
        exchange = select_exchange(bybit_only=True)
        if exchange:
            trade_usdc_usdt(exchange)
    elif pair_idx == 1:
        trade_bfusd_usdt()
    elif pair_idx == 2:
        trade_usd1_usdt()


def trade_usdc_usdt(exchange: str):
    """Bybit USDC/USDT 交易"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n=== {display_name} USDC/USDT 交易 ===")

    while True:
        print("\n正在获取 USDC/USDT 深度...")
        try:
            output = run_on_ec2(f"orderbook {exchange}")
            print(output)
        except SSHError as e:
            print(f"获取深度失败: {e}")

        print("正在查询账户余额...")
        try:
            funding_output = run_on_ec2(f"account_balance {exchange} FUND USDT")
            funding_balance = float(funding_output.strip())
        except SSHError as e:
            print(f"⚠️ 查询资金账户失败: {e}")
            funding_balance = 0.0
        except ValueError:
            print(f"⚠️ 资金账户返回异常: {funding_output}")
            funding_balance = 0.0
        try:
            unified_output = run_on_ec2(f"account_balance {exchange} UNIFIED USDT")
            unified_balance = float(unified_output.strip())
        except SSHError as e:
            print(f"⚠️ 查询统一账户失败: {e}")
            unified_balance = 0.0
        except ValueError:
            print(f"⚠️ 统一账户返回异常: {unified_output}")
            unified_balance = 0.0
        print(f"💰 资金账户 USDT: {funding_balance:.4f}")
        print(f"💰 统一账户 USDT: {unified_balance:.4f}")
        print(f"💰 合计 USDT: {funding_balance + unified_balance:.4f}")

        action = select_option("选择操作:", ["市价买入 USDC", "限价买入 USDC", "撤单", "刷新深度", "返回"])

        if action == 4:  # 返回
            break
        elif action == 3:  # 刷新深度
            continue
        elif action == 2:  # 撤单
            _cancel_bybit_usdc_orders(exchange)
            input("\n按回车继续...")
            continue

        amount = input_amount("请输入买入 USDC 数量:")
        if amount is None:
            continue

        required_usdt = float(amount) * 1.001
        if unified_balance < required_usdt:
            need_transfer = required_usdt - unified_balance + 1
            if funding_balance >= need_transfer:
                print(f"\n⚠️ 统一账户余额不足，自动从资金账户划转 {need_transfer:.2f} USDT...")
                try:
                    transfer_output = run_on_ec2(f"transfer {exchange} FUND UNIFIED USDT {need_transfer:.2f}")
                    print(transfer_output)
                    unified_balance += need_transfer
                    funding_balance -= need_transfer
                except SSHError as e:
                    print(f"划转失败: {e}")
                    continue
            else:
                total = funding_balance + unified_balance
                print(f"\n❌ 余额不足! 需要约 {required_usdt:.2f} USDT，合计只有 {total:.2f} USDT")
                continue

        if action == 0:
            if select_option(f"确认市价买入 {amount} USDC?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"buy_usdc {exchange} market {amount}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        elif action == 1:
            price_str = input("请输入限价 (如 1.0002, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价买入 {amount} USDC?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"buy_usdc {exchange} limit {amount} {price}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        input("\n按回车继续...")


def _cancel_bybit_usdc_orders(exchange: str):
    """撤销 Bybit USDC/USDT 挂单"""
    print("\n正在查询 USDC/USDT 挂单...")
    try:
        output = run_on_ec2(f"open_orders {exchange} USDCUSDT")
        print(output)

        if "没有" in output or "无" in output or not output.strip():
            print("没有 USDC/USDT 挂单")
            return

        action = select_option("选择操作:", ["撤销所有 USDC/USDT 挂单", "返回"])
        if action == 0:
            print("\n正在撤销所有挂单...")
            cancel_output = run_on_ec2(f"cancel_all {exchange} USDCUSDT")
            print(cancel_output)
    except SSHError as e:
        print(f"操作失败: {e}")


def trade_usdc_usdt_binance(exchange: str = None):
    """Binance USDC/USDT 交易"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n=== {display_name} USDC/USDT 交易 ===")

    while True:
        print("\n正在获取 USDC/USDT 深度...")
        try:
            output = run_on_ec2(f"orderbook {exchange} USDCUSDT")
            print(output)
        except SSHError as e:
            print(f"获取深度失败: {e}")

        print(f"正在查询 {display_name} 现货账户余额...")
        usdt_balance = "0"
        usdc_balance = "0"
        try:
            output = run_on_ec2(f"account_balance {exchange} SPOT USDT")
            usdt_balance = output.strip()
            output2 = run_on_ec2(f"account_balance {exchange} SPOT USDC")
            usdc_balance = output2.strip()
            print(f"USDT 余额: {usdt_balance}")
            print(f"USDC 余额: {usdc_balance}")
        except SSHError as e:
            print(f"查询余额失败: {e}")

        action = select_option("选择操作:", ["市价买入 USDC", "限价买入 USDC", "市价卖出 USDC", "限价卖出 USDC", "刷新深度", "返回"])

        if action == 5:  # 返回
            break
        elif action == 4:  # 刷新深度
            continue

        # 买入操作
        if action == 0:  # 市价买入
            amount = input_amount("请输入买入 USDC 数量:")
            if amount is None:
                continue
            if select_option(f"确认市价买入 {amount} USDC?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"buy_usdc {exchange} market {amount}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        elif action == 1:  # 限价买入
            amount = input_amount("请输入买入 USDC 数量:")
            if amount is None:
                continue
            price_str = input("请输入限价 (如 0.9998, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价买入 {amount} USDC?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"buy_usdc {exchange} limit {amount} {price}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        # 卖出操作
        elif action == 2:  # 市价卖出
            amount = input_amount("请输入卖出 USDC 数量:")
            if amount is None:
                continue
            if select_option(f"确认市价卖出 {amount} USDC?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"sell_usdc {exchange} market {amount}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        elif action == 3:  # 限价卖出
            amount = input_amount("请输入卖出 USDC 数量:")
            if amount is None:
                continue
            price_str = input("请输入限价 (如 1.0002, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价卖出 {amount} USDC?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"sell_usdc {exchange} limit {amount} {price}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        input("\n按回车继续...")


def trade_bfusd_usdt(exchange: str = None):
    """Binance BFUSD/USDT 交易"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n=== {display_name} BFUSD/USDT 交易 ===")

    while True:
        print("\n正在获取 BFUSD/USDT 深度...")
        try:
            output = run_on_ec2(f"orderbook {exchange} BFUSDUSDT")
            print(output)
        except SSHError as e:
            print(f"获取深度失败: {e}")

        print(f"正在查询 {display_name} 现货账户余额...")
        usdt_balance = "0"
        bfusd_balance = "0"
        try:
            output = run_on_ec2(f"account_balance {exchange} SPOT USDT")
            usdt_balance = output.strip()
            output2 = run_on_ec2(f"account_balance {exchange} SPOT BFUSD")
            bfusd_balance = output2.strip()
            print(f"USDT 余额: {usdt_balance}")
            print(f"BFUSD 余额: {bfusd_balance}")
        except SSHError as e:
            print(f"查询余额失败: {e}")

        action = select_option("选择操作:", ["市价买入 BFUSD", "限价买入 BFUSD", "市价卖出 BFUSD", "限价卖出 BFUSD", "刷新深度", "返回"])

        if action == 5:  # 返回
            break
        elif action == 4:  # 刷新深度
            continue

        # 买入操作
        if action == 0:  # 市价买入
            amount = input_amount("请输入买入 BFUSD 数量:")
            if amount is None:
                continue
            if select_option(f"确认市价买入 {amount} BFUSD?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"buy_bfusd {exchange} market {amount}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        elif action == 1:  # 限价买入
            amount = input_amount("请输入买入 BFUSD 数量:")
            if amount is None:
                continue
            price_str = input("请输入限价 (如 1.0002, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价买入 {amount} BFUSD?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"buy_bfusd {exchange} limit {amount} {price}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        # 卖出操作
        elif action == 2:  # 市价卖出
            amount = input_amount("请输入卖出 BFUSD 数量:")
            if amount is None:
                continue
            if select_option(f"确认市价卖出 {amount} BFUSD?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"sell_bfusd {exchange} market {amount}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        elif action == 3:  # 限价卖出
            amount = input_amount("请输入卖出 BFUSD 数量:")
            if amount is None:
                continue
            price_str = input("请输入限价 (如 1.0008, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价卖出 {amount} BFUSD?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"sell_bfusd {exchange} limit {amount} {price}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        input("\n按回车继续...")


def trade_usd1_usdt(exchange: str = None):
    """Binance USD1/USDT 交易"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n=== {display_name} USD1/USDT 交易 ===")

    while True:
        print("\n正在获取 USD1/USDT 深度...")
        try:
            output = run_on_ec2(f"orderbook {exchange} USD1USDT")
            print(output)
        except SSHError as e:
            print(f"获取深度失败: {e}")

        print(f"正在查询 {display_name} 现货账户余额...")
        usdt_balance = "0"
        usd1_balance = "0"
        try:
            output = run_on_ec2(f"account_balance {exchange} SPOT USDT")
            usdt_balance = output.strip()
            output2 = run_on_ec2(f"account_balance {exchange} SPOT USD1")
            usd1_balance = output2.strip()
            print(f"USDT 余额: {usdt_balance}")
            print(f"USD1 余额: {usd1_balance}")
        except SSHError as e:
            print(f"查询余额失败: {e}")

        action = select_option("选择操作:", ["市价买入 USD1", "限价买入 USD1", "市价卖出 USD1", "限价卖出 USD1", "刷新深度", "返回"])

        if action == 5:  # 返回
            break
        elif action == 4:  # 刷新深度
            continue

        # 买入操作
        if action == 0:  # 市价买入
            amount = input_amount("请输入买入 USD1 数量:")
            if amount is None:
                continue
            if select_option(f"确认市价买入 {amount} USD1?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"buy_usd1 {exchange} market {amount}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        elif action == 1:  # 限价买入
            amount = input_amount("请输入买入 USD1 数量:")
            if amount is None:
                continue
            price_str = input("请输入限价 (如 1.0002, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价买入 {amount} USD1?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"buy_usd1 {exchange} limit {amount} {price}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        # 卖出操作
        elif action == 2:  # 市价卖出
            amount = input_amount("请输入卖出 USD1 数量:")
            if amount is None:
                continue
            if select_option(f"确认市价卖出 {amount} USD1?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"sell_usd1 {exchange} market {amount}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        elif action == 3:  # 限价卖出
            amount = input_amount("请输入卖出 USD1 数量:")
            if amount is None:
                continue
            price_str = input("请输入限价 (如 1.0008, 输入 0 返回): ").strip()
            if not price_str or price_str == "0":
                continue
            try:
                price = float(price_str)
                if price <= 0:
                    print("价格必须大于0")
                    continue
            except ValueError:
                print("请输入有效的数字")
                continue

            if select_option(f"确认以 {price} 限价卖出 {amount} USD1?", ["确认", "取消"]) == 0:
                print("\n正在下单...")
                try:
                    output = run_on_ec2(f"sell_usd1 {exchange} limit {amount} {price}")
                    print(output)
                    if "error" in output.lower() or "失败" in output:
                        print("\n下单可能失败，请检查交易所确认")
                except SSHError as e:
                    print(f"下单失败: {e}")

        input("\n按回车继续...")


# ===================== 撤单功能 =====================

def get_spot_open_orders(exchange: str) -> list:
    """获取现货挂单"""
    exchange_base = get_exchange_base(exchange)

    try:
        if exchange_base == "binance":
            output = run_on_ec2(f"spot_orders {exchange}")
            orders = json.loads(output.strip())
            if isinstance(orders, dict) and "error" in orders:
                print(f"获取现货挂单失败: {orders['error']}")
                return []
            return [{
                'symbol': o.get('symbol', ''),
                'side': o.get('side', ''),
                'price': o.get('price', ''),
                'qty': o.get('origQty', ''),
                'orderId': o.get('orderId', '')
            } for o in orders]
        elif exchange_base == "gate":
            output = run_on_ec2(f"gate_spot_orders {exchange}")
            orders = json.loads(output.strip())
            if isinstance(orders, dict) and "error" in orders:
                print(f"获取现货挂单失败: {orders['error']}")
                return []
            return [{
                'symbol': o.get('currency_pair', ''),
                'side': o.get('side', '').upper(),
                'price': o.get('price', ''),
                'qty': o.get('amount', ''),
                'orderId': o.get('id', '')
            } for o in orders]
        elif exchange_base == "bitget":
            output = run_on_ec2(f"bitget_spot_orders {exchange}")
            orders = json.loads(output.strip())
            if isinstance(orders, dict) and "error" in orders:
                print(f"获取现货挂单失败: {orders['error']}")
                return []
            return [{
                'symbol': o.get('symbol', ''),
                'side': o.get('side', '').upper(),
                'price': o.get('price', ''),
                'qty': o.get('size', ''),
                'orderId': o.get('orderId', '')
            } for o in orders]
        else:
            print(f"暂不支持 {exchange_base} 交易所的现货撤单")
            return []
    except json.JSONDecodeError as e:
        print(f"解析响应失败: {e}")
        return []
    except Exception as e:
        print(f"获取现货挂单失败: {e}")
        return []


def get_futures_open_orders(exchange: str, use_portfolio: bool = True) -> list:
    """获取永续挂单"""
    exchange_base = get_exchange_base(exchange)

    try:
        if exchange_base == "binance":
            if use_portfolio:
                output = run_on_ec2(f"portfolio_um_orders {exchange}")
            else:
                output = run_on_ec2(f"futures_orders {exchange}")

            orders = json.loads(output.strip())
            if isinstance(orders, dict) and "error" in orders:
                print(f"获取永续挂单失败: {orders['error']}")
                return []

            return [{
                'symbol': o.get('symbol', ''),
                'side': o.get('side', ''),
                'price': o.get('price', ''),
                'qty': o.get('origQty', ''),
                'orderId': o.get('orderId', ''),
                'source': 'portfolio' if use_portfolio else 'futures'
            } for o in orders]

        elif exchange_base == "aster":
            output = run_on_ec2(f"aster_orders {exchange}")
            orders = json.loads(output.strip())
            if isinstance(orders, dict) and "error" in orders:
                print(f"获取永续挂单失败: {orders['error']}")
                return []

            return [{
                'symbol': o.get('symbol', ''),
                'side': o.get('side', ''),
                'price': o.get('price', ''),
                'qty': o.get('origQty', ''),
                'orderId': o.get('orderId', ''),
                'source': 'aster'
            } for o in orders]

        else:
            print(f"暂不支持 {exchange_base} 交易所的永续撤单")
            return []
    except json.JSONDecodeError as e:
        print(f"解析响应失败: {e}")
        return []
    except Exception as e:
        print(f"获取永续挂单失败: {e}")
        return []


def display_orders(orders: list, order_type: str) -> None:
    """显示订单列表"""
    if not orders:
        print(f"\n没有{order_type}挂单")
        return

    print(f"\n{'=' * 60}")
    print(f"  {order_type}挂单列表")
    print("=" * 60)

    for i, order in enumerate(orders, 1):
        symbol = order.get('symbol', 'N/A')
        side = order.get('side', 'N/A')
        price = order.get('price', 'N/A')
        qty = order.get('qty', 'N/A')
        order_id = order.get('orderId', 'N/A')

        side_upper = str(side).upper()
        side_indicator = "[买]" if side_upper == "BUY" else "[卖]"
        print(f"  {i}. {side_indicator} {symbol} | {side} | 价格: {price} | 数量: {qty} | ID: {order_id}")


def cancel_single_order(exchange: str, order_type: str, symbol: str, order_id: str, use_portfolio: bool = True) -> bool:
    """撤销单个订单"""
    exchange_base = get_exchange_base(exchange)

    try:
        if exchange_base == "binance":
            if order_type == "spot":
                output = run_on_ec2(f"cancel_spot {exchange} {symbol} {order_id}")
            elif use_portfolio:
                output = run_on_ec2(f"cancel_portfolio_um {exchange} {symbol} {order_id}")
            else:
                output = run_on_ec2(f"cancel_futures {exchange} {symbol} {order_id}")

            result = json.loads(output.strip())
            return 'orderId' in result or 'status' in result

        elif exchange_base == "gate":
            output = run_on_ec2(f"gate_cancel_spot {exchange} {symbol} {order_id}")
            result = json.loads(output.strip())
            # Gate API 返回成功撤单时包含 id 字段
            return 'id' in result or 'status' in result

        elif exchange_base == "bitget":
            output = run_on_ec2(f"bitget_cancel_spot {exchange} {symbol} {order_id}")
            result = json.loads(output.strip())
            # Bitget API 返回成功撤单时包含 orderId 字段
            return 'orderId' in result or result.get('code') == '00000'

        elif exchange_base == "aster":
            output = run_on_ec2(f"aster_cancel {exchange} {symbol} {order_id}")
            result = json.loads(output.strip())
            return 'orderId' in result or 'status' in result

        else:
            print(f"暂不支持 {exchange_base} 交易所的撤单")
            return False
    except json.JSONDecodeError:
        return False
    except Exception as e:
        print(f"撤单失败: {e}")
        return False


def cancel_spot_orders(exchange: str):
    """撤销现货订单"""
    print(f"\n=== 现货撤单 ===")
    print("\n正在获取现货挂单...")

    orders = get_spot_open_orders(exchange)
    display_orders(orders, "现货")

    if not orders:
        return

    options = ["撤销单个订单", "撤销全部订单", "返回"]
    action = select_option("选择操作:", options)

    if action == 2:
        return

    if action == 0:
        order_names = []
        for order in orders:
            symbol = order.get('symbol', 'N/A')
            side = order.get('side', 'N/A')
            price = order.get('price', 'N/A')
            qty = order.get('qty', 'N/A')
            order_names.append(f"{symbol} | {side} | {price} x {qty}")

        order_idx = select_option("选择要撤销的订单:", order_names, allow_back=True)
        if order_idx == -1:
            return

        selected_order = orders[order_idx]
        symbol = selected_order.get('symbol', '')
        order_id = str(selected_order.get('orderId', ''))

        if select_option(f"确认撤销订单 {symbol} (ID: {order_id})?", ["确认", "取消"]) == 0:
            print("\n正在撤单...")
            if cancel_single_order(exchange, "spot", symbol, order_id):
                print("撤单成功")
            else:
                print("撤单可能失败，请检查交易所确认")

    elif action == 1:
        if select_option(f"确认撤销全部 {len(orders)} 个现货挂单?", ["确认", "取消"]) == 0:
            print("\n正在撤销全部订单...")
            success_count = 0
            for order in orders:
                symbol = order.get('symbol', '')
                order_id = str(order.get('orderId', ''))
                if cancel_single_order(exchange, "spot", symbol, order_id):
                    success_count += 1
                    print(f"  撤销 {symbol} #{order_id}")
                else:
                    print(f"  撤销失败 {symbol} #{order_id}")

            if success_count == len(orders):
                print("全部撤单成功")
            else:
                print("部分撤单可能失败，请检查交易所确认")


def cancel_futures_orders(exchange: str, use_portfolio: bool = True):
    """撤销永续订单"""
    exchange_base = get_exchange_base(exchange)

    if exchange_base == "binance":
        account_type = "统一账户" if use_portfolio else "U本位合约"
        print(f"\n=== 永续撤单 ({account_type}) ===")
    else:
        print(f"\n=== 永续撤单 ===")

    print("\n正在获取永续挂单...")

    orders = get_futures_open_orders(exchange, use_portfolio=use_portfolio)
    display_orders(orders, "永续")

    if not orders:
        return

    options = ["撤销单个订单", "撤销全部订单", "返回"]
    action = select_option("选择操作:", options)

    if action == 2:
        return

    if action == 0:
        order_names = []
        for order in orders:
            symbol = order.get('symbol', 'N/A')
            side = order.get('side', 'N/A')
            price = order.get('price', 'N/A')
            qty = order.get('qty', 'N/A')
            order_names.append(f"{symbol} | {side} | {price} x {qty}")

        order_idx = select_option("选择要撤销的订单:", order_names, allow_back=True)
        if order_idx == -1:
            return

        selected_order = orders[order_idx]
        symbol = selected_order.get('symbol', '')
        order_id = str(selected_order.get('orderId', ''))

        if select_option(f"确认撤销订单 {symbol} (ID: {order_id})?", ["确认", "取消"]) == 0:
            print("\n正在撤单...")
            if cancel_single_order(exchange, "futures", symbol, order_id, use_portfolio=use_portfolio):
                print("撤单成功")
            else:
                print("撤单可能失败，请检查交易所确认")

    elif action == 1:
        if select_option(f"确认撤销全部 {len(orders)} 个永续挂单?", ["确认", "取消"]) == 0:
            print("\n正在撤销全部订单...")
            success_count = 0
            for order in orders:
                symbol = order.get('symbol', '')
                order_id = str(order.get('orderId', ''))
                if cancel_single_order(exchange, "futures", symbol, order_id, use_portfolio=use_portfolio):
                    success_count += 1
                    print(f"  撤销 {symbol} #{order_id}")
                else:
                    print(f"  撤销失败 {symbol} #{order_id}")

            if success_count == len(orders):
                print("全部撤单成功")
            else:
                print("部分撤单可能失败，请检查交易所确认")


def cancel_orders_menu(exchange: str):
    """撤单菜单"""
    exchange_base = get_exchange_base(exchange)

    while True:
        print(f"\n=== 撤单 ===")

        if exchange_base == "binance":
            options = ["现货撤单", "永续撤单 (统一账户)", "返回"]
            action = select_option("选择订单类型:", options)

            if action == 2:
                return
            elif action == 0:
                cancel_spot_orders(exchange)
            elif action == 1:
                cancel_futures_orders(exchange, use_portfolio=True)

        elif exchange_base == "aster":
            options = ["永续撤单", "返回"]
            action = select_option("选择订单类型:", options)

            if action == 1:
                return
            elif action == 0:
                cancel_futures_orders(exchange, use_portfolio=False)

        elif exchange_base == "gate":
            # Gate.io 目前只支持现货撤单
            cancel_spot_orders(exchange)
            return

        elif exchange_base == "bitget":
            # Bitget 目前只支持现货撤单
            cancel_spot_orders(exchange)
            return

        else:
            options = ["现货撤单", "永续撤单", "返回"]
            action = select_option("选择订单类型:", options)

            if action == 2:
                return
            elif action == 0:
                cancel_spot_orders(exchange)
            elif action == 1:
                cancel_futures_orders(exchange)

        input("\n按回车继续...")


# ===================== 市价卖出 =====================

def get_spot_balances(exchange: str) -> list:
    """获取现货余额（通过 EC2）"""
    exchange_base = get_exchange_base(exchange)
    balances = []

    try:
        # Bitget/Gate 使用专门的命令获取所有可卖出资产
        if exchange_base == "bitget":
            output = run_on_ec2(f"bitget_spot_assets {exchange}")
            try:
                assets = json.loads(output.strip())
                if isinstance(assets, list):
                    return [a for a in assets if a.get('free', 0) > 0]
                elif isinstance(assets, dict) and 'error' in assets:
                    print(f"获取资产失败: {assets['error']}")
                    return []
            except json.JSONDecodeError:
                print(f"解析资产数据失败")
                return []

        if exchange_base == "gate":
            output = run_on_ec2(f"gate_spot_assets {exchange}")
            try:
                assets = json.loads(output.strip())
                if isinstance(assets, list):
                    return [a for a in assets if a.get('free', 0) > 0]
                elif isinstance(assets, dict) and 'error' in assets:
                    print(f"获取资产失败: {assets['error']}")
                    return []
            except json.JSONDecodeError:
                print(f"解析资产数据失败")
                return []

        # Binance 使用专门的命令获取现货余额
        if exchange_base == "binance":
            output = run_on_ec2(f"spot_balance {exchange}")
            try:
                assets = json.loads(output.strip())
                if isinstance(assets, list):
                    for a in assets:
                        asset = a.get('asset', '').upper()
                        free = float(a.get('free', 0))
                        if asset in STABLECOINS or free <= 0:
                            continue
                        price = get_coin_price(asset)
                        value = free * price
                        if value >= MIN_DISPLAY_VALUE:
                            balances.append({
                                'asset': asset,
                                'free': free,
                                'value': value
                            })
                    balances.sort(key=lambda x: x['value'], reverse=True)
                    return balances
                elif isinstance(assets, dict) and 'error' in assets:
                    print(f"获取资产失败: {assets['error']}")
                    return []
            except json.JSONDecodeError:
                print(f"解析资产数据失败")
                return []

        # 其他交易所使用 balance 命令
        output = run_on_ec2(f"balance {exchange}")

        raw_balances = []
        for line in output.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            parts = line.split(':')
            if len(parts) >= 2:
                asset = parts[0].strip().upper()
                try:
                    amount_str = parts[1].strip().split()[0]
                    amount = float(amount_str)
                    if amount > 0:
                        raw_balances.append({'asset': asset, 'free': amount})
                except (ValueError, IndexError):
                    continue

        for b in raw_balances:
            asset = b.get('asset', '').upper()
            free = float(b.get('free', 0))

            if asset in STABLECOINS or free <= 0:
                continue

            price = get_coin_price(asset)
            value = free * price

            if value >= MIN_DISPLAY_VALUE:
                balances.append({
                    'asset': asset,
                    'free': free,
                    'value': value
                })

        balances.sort(key=lambda x: x['value'], reverse=True)
        return balances

    except Exception as e:
        print(f"获取余额失败: {e}")
        return []


def display_balances(balances: list) -> None:
    """显示余额列表"""
    if not balances:
        print(f"\n没有可卖出的资产")
        return

    print(f"\n{'=' * 50}")
    print(f"  可卖出资产列表")
    print("=" * 50)

    for i, balance in enumerate(balances, 1):
        asset = balance['asset']
        free = balance['free']
        print(f"  {i}. {asset}: {free:.6f}")


def market_sell_spot(exchange: str, symbol: str, qty: float) -> bool:
    """现货市价卖出（通过 EC2）"""
    exchange_base = get_exchange_base(exchange)

    try:
        if exchange_base == "binance":
            output = run_on_ec2(f"market_sell {exchange} {symbol} {qty}")
            result = json.loads(output.strip())
            if 'orderId' in result:
                print(f"  订单ID: {result['orderId']}")
                print(f"  成交数量: {result.get('executedQty', 'N/A')}")
                return True
            else:
                print(f"  错误: {result.get('msg', result)}")
                return False
        elif exchange_base == "gate":
            output = run_on_ec2(f"gate_market_sell {exchange} {symbol} {qty}")
            result = json.loads(output.strip())
            if 'id' in result:
                print(f"  订单ID: {result['id']}")
                print(f"  成交数量: {result.get('amount', 'N/A')}")
                return True
            else:
                print(f"  错误: {result.get('message', result)}")
                return False
        elif exchange_base == "bitget":
            output = run_on_ec2(f"bitget_market_sell {exchange} {symbol} {qty}")
            result = json.loads(output.strip())
            data = result.get('data') or {}
            if result.get('code') == '00000' or 'orderId' in data:
                print(f"  订单ID: {data.get('orderId', 'N/A')}")
                return True
            else:
                print(f"  错误: {result.get('msg', result)}")
                return False
        else:
            print(f"暂不支持 {exchange_base} 交易所的市价卖出")
            return False
    except json.JSONDecodeError as e:
        print(f"解析响应失败: {e}")
        return False
    except Exception as e:
        print(f"卖出失败: {e}")
        return False


def buy_gt(exchange: str):
    """Gate 市价买入 GT"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n=== {display_name} - 买入 GT ===")

    amount = input_amount("请输入花费的 USDT 数量:")
    if amount is None:
        return

    confirm = select_option(f"确认用 {amount} USDT 市价买入 GT?", ["确认", "取消"])
    if confirm != 0:
        print("已取消")
        return

    print("\n正在下单...")
    try:
        output = run_on_ec2(f"gate_market_buy {exchange} GT_USDT {amount}")
        result = json.loads(output.strip())
        if isinstance(result, dict) and 'id' in result:
            print(f"  ✅ 下单成功!")
            print(f"  订单ID: {result['id']}")
            fill_price = result.get('fill_price', result.get('avg_deal_price', ''))
            if fill_price:
                print(f"  成交均价: {fill_price}")
            left = result.get('left', '')
            amount_field = result.get('amount', '')
            if amount_field and left:
                filled = float(amount_field) - float(left)
                if filled > 0:
                    print(f"  花费 USDT: {filled}")
        elif isinstance(result, dict) and ('message' in result or 'error' in result):
            print(f"  ❌ 下单失败: {result.get('message', result.get('error', result))}")
        else:
            print(f"  返回: {result}")
    except json.JSONDecodeError:
        print(output)
    except SSHError as e:
        print(f"  ❌ 下单失败: {e}")


def market_sell_menu(exchange: str):
    """市价卖出菜单"""
    exchange_base = get_exchange_base(exchange)

    while True:
        print(f"\n=== 市价卖出 ===")

        mode = select_option("选择操作方式:", [
            "从余额列表选择",
            "手动输入币种",
            "返回"
        ])

        if mode == 2:
            return

        if mode == 0:
            print("\n正在获取现货余额...")
            balances = get_spot_balances(exchange)
            display_balances(balances)

            if not balances:
                input("\n按回车继续...")
                continue

            asset_names = []
            for balance in balances:
                asset = balance['asset']
                free = balance['free']
                value = balance['value']
                asset_names.append(f"{asset} (可用: {free:.6f}, 约${value:.2f})")

            asset_idx = select_option("选择要卖出的资产:", asset_names, allow_back=True)
            if asset_idx == -1:
                continue

            selected = balances[asset_idx]
            asset = selected['asset']
            available = selected['free']

            if exchange_base == "gate":
                symbol = f"{asset}_USDT"
            else:
                symbol = f"{asset}USDT"

            print(f"\n卖出: {asset}")
            print(f"可用数量: {available}")
            print(f"交易对: {symbol}")

            qty_option = select_option("选择卖出数量:", [
                "全部卖出",
                "输入数量",
                "返回"
            ])

            if qty_option == 2:
                continue

            if qty_option == 0:
                qty = available
            else:
                qty = input_amount(f"请输入卖出数量 (最大 {available}):")
                if qty is None:
                    continue
                if qty > available:
                    print(f"数量超过可用余额 {available}")
                    continue

        else:
            asset = input("\n请输入要卖出的币种 (如 BTC, 输入 0 返回): ").strip().upper()
            if not asset or asset == "0":
                continue

            if exchange_base == "gate":
                symbol = f"{asset}_USDT"
            else:
                symbol = f"{asset}USDT"

            qty = input_amount("请输入卖出数量:")
            if qty is None:
                continue

        # 根据 LOT_SIZE 调整数量
        adjusted_qty = adjust_quantity_for_lot_size(qty, symbol, exchange_base)
        if adjusted_qty != qty:
            print(f"\n注意: 根据交易规则，数量已调整为 {adjusted_qty}")
            qty = adjusted_qty

        if qty <= 0:
            print("调整后数量为 0，无法卖出")
            continue

        print("\n" + "=" * 50)
        print("请确认市价卖出:")
        print(f"  交易对: {symbol}")
        print(f"  方向: 卖出 (SELL)")
        print(f"  数量: {qty}")
        print(f"  类型: 市价单")
        print("=" * 50)

        if select_option("确认卖出?", ["确认", "取消"]) != 0:
            print("已取消")
            continue

        print("\n正在下单...")
        if market_sell_spot(exchange, symbol, qty):
            print("卖出成功")
        else:
            print("卖出可能失败，请检查交易所确认")

        input("\n按回车继续...")


# ===================== 永续平仓 =====================

def get_um_positions(exchange: str) -> list:
    """获取 U本位永续合约持仓（通过 EC2）"""
    exchange_base = get_exchange_base(exchange)

    try:
        if exchange_base == "binance":
            output = run_on_ec2(f"portfolio_um_positions {exchange}")
            positions = json.loads(output.strip())

            if isinstance(positions, dict) and "msg" in positions:
                print(f"API 错误: {positions.get('msg')}")
                return []

            result = []
            for p in positions:
                symbol = p.get("symbol", "")
                position_amt = float(p.get("positionAmt", 0))
                entry_price = float(p.get("entryPrice", 0))
                mark_price = float(p.get("markPrice", 0))
                unrealized_pnl = float(p.get("unRealizedProfit", 0))

                if position_amt == 0:
                    continue

                notional = abs(position_amt * mark_price)

                result.append({
                    "symbol": symbol,
                    "positionAmt": position_amt,
                    "entryPrice": entry_price,
                    "markPrice": mark_price,
                    "unrealizedPnl": unrealized_pnl,
                    "notional": notional,
                    "side": "LONG" if position_amt > 0 else "SHORT"
                })

            result.sort(key=lambda x: x["notional"], reverse=True)
            return result
        else:
            print(f"暂不支持 {exchange_base} 交易所的永续持仓查询")
            return []

    except json.JSONDecodeError as e:
        print(f"解析响应失败: {e}")
        return []
    except Exception as e:
        print(f"获取持仓失败: {e}")
        return []


def display_positions(positions: list) -> None:
    """显示持仓列表"""
    if not positions:
        print("\n没有持仓")
        return

    print(f"\n{'=' * 60}")
    print("  U本位永续合约持仓")
    print("=" * 60)

    for i, pos in enumerate(positions, 1):
        symbol = pos["symbol"]
        side = pos["side"]
        amt = pos["positionAmt"]
        entry = pos["entryPrice"]
        mark = pos["markPrice"]
        pnl = pos["unrealizedPnl"]
        notional = pos["notional"]

        side_str = "多" if side == "LONG" else "空"
        pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"

        print(f"  {i}. {symbol} [{side_str}]")
        print(f"     数量: {amt:.4f} | 价值: ${notional:.2f}")
        print(f"     开仓: {entry:.4f} | 现价: {mark:.4f}")
        print(f"     未实现盈亏: ${pnl_str}")
        print()


def market_close_position(exchange: str, symbol: str, quantity: float, position_side: str) -> bool:
    """市价平仓（通过 EC2）"""
    exchange_base = get_exchange_base(exchange)

    try:
        if exchange_base == "binance":
            close_side = "SELL" if position_side == "LONG" else "BUY"

            output = run_on_ec2(f"portfolio_um_close {exchange} {symbol} {quantity} {close_side}")
            result = json.loads(output.strip())

            if "orderId" in result:
                print(f"  订单ID: {result['orderId']}")
                print(f"  状态: {result.get('status', 'N/A')}")
                print(f"  成交数量: {result.get('executedQty', 'N/A')}")
                return True
            else:
                print(f"  错误: {result.get('msg', result)}")
                return False
        else:
            print(f"暂不支持 {exchange_base} 交易所的永续平仓")
            return False

    except json.JSONDecodeError as e:
        print(f"解析响应失败: {e}")
        return False
    except Exception as e:
        print(f"平仓失败: {e}")
        return False


def futures_close_menu(exchange: str):
    """永续平仓菜单"""

    while True:
        print(f"\n=== 永续合约平仓 ===")

        mode = select_option("选择操作方式:", [
            "从持仓列表选择",
            "手动输入交易对",
            "返回"
        ])

        if mode == 2:
            return

        if mode == 0:
            print("\n正在获取持仓...")
            positions = get_um_positions(exchange)
            display_positions(positions)

            if not positions:
                input("\n按回车继续...")
                continue

            pos_names = []
            for pos in positions:
                symbol = pos["symbol"]
                side = "多" if pos["side"] == "LONG" else "空"
                amt = pos["positionAmt"]
                notional = pos["notional"]
                pos_names.append(f"{symbol} [{side}] 数量:{amt:.4f} 价值:${notional:,.2f}")

            pos_idx = select_option("选择要平仓的持仓:", pos_names, allow_back=True)
            if pos_idx == -1:
                continue

            selected = positions[pos_idx]
            symbol = selected["symbol"]
            position_amt = selected["positionAmt"]
            position_side = selected["side"]
            available = abs(position_amt)

            print(f"\n交易对: {symbol}")
            print(f"方向: {'多仓' if position_side == 'LONG' else '空仓'}")
            print(f"持仓数量: {position_amt}")

            qty_option = select_option("选择平仓数量:", [
                "全部平仓",
                "输入数量",
                "返回"
            ])

            if qty_option == 2:
                continue

            if qty_option == 0:
                qty = available
            else:
                qty = input_amount(f"请输入平仓数量 (最大 {available}):")
                if qty is None:
                    continue
                if qty > available:
                    print(f"数量超过持仓数量 {available}")
                    continue

        else:
            symbol = input("\n请输入交易对 (如 BTCUSDT, 输入 0 返回): ").strip().upper()
            if not symbol or symbol == "0":
                continue

            if not symbol.endswith("USDT"):
                symbol = symbol + "USDT"

            side_idx = select_option("选择仓位方向:", ["多仓 (平仓卖出)", "空仓 (平仓买入)"], allow_back=True)
            if side_idx == -1:
                continue
            position_side = "LONG" if side_idx == 0 else "SHORT"

            qty = input_amount("请输入平仓数量:")
            if qty is None:
                continue

        close_action = "卖出" if position_side == "LONG" else "买入"
        print("\n" + "=" * 50)
        print("请确认市价平仓:")
        print(f"  交易对: {symbol}")
        print(f"  仓位: {'多仓' if position_side == 'LONG' else '空仓'}")
        print(f"  平仓方向: {close_action}")
        print(f"  数量: {qty}")
        print(f"  类型: 市价单 (reduceOnly)")
        print("=" * 50)

        if select_option("确认平仓?", ["确认", "取消"]) != 0:
            print("已取消")
            continue

        print("\n正在平仓...")
        if market_close_position(exchange, symbol, qty, position_side):
            print("平仓成功")
        else:
            print("平仓可能失败，请检查交易所确认")

        input("\n按回车继续...")
