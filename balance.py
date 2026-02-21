#!/usr/bin/env python3
"""余额查询"""

import json
import requests
from utils import run_on_ec2, select_option, select_exchange, get_exchange_base, get_exchange_display_name, SSHError

# 稳定币列表，价格视为 1 USD
STABLECOINS = ['USDT', 'USDC', 'USD1', 'BUSD', 'TUSD', 'FDUSD']

# 最小显示价值 (USD)
MIN_DISPLAY_VALUE = 10


def get_coin_price(coin: str) -> float:
    """获取币种对 USDT 的价格，稳定币返回 1"""
    coin = coin.upper()
    if coin in STABLECOINS:
        return 1.0

    try:
        # 尝试 COIN/USDT 交易对
        resp = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data.get('price', 0))

        # 尝试 COIN/BUSD
        resp = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={coin}BUSD",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data.get('price', 0))
    except requests.exceptions.Timeout:
        print(f"⚠️  获取 {coin} 价格超时")
    except requests.exceptions.ConnectionError:
        print(f"⚠️  获取 {coin} 价格失败: 网络连接错误")
    except (KeyError, ValueError) as e:
        print(f"⚠️  解析 {coin} 价格失败: {e}")

    return 0.0


def filter_by_value(balances: dict, min_value: float = MIN_DISPLAY_VALUE) -> dict:
    """过滤掉市值小于指定美元价值的资产"""
    if not isinstance(balances, dict):
        return {}
    result = {}
    for coin, amount in balances.items():
        try:
            amount_float = float(amount)
            price = get_coin_price(coin)
            value = amount_float * price
            if value >= min_value:
                result[coin] = amount_float
        except (ValueError, TypeError):
            continue
    return result


def show_balance(exchange: str = None):
    """查询余额"""
    if not exchange:
        exchange = select_exchange()
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    exchange_base = get_exchange_base(exchange)

    print(f"\n正在查询 {display_name} 余额...")

    # EC2 上的 balance 命令已经格式化好输出，直接显示
    output = run_on_ec2(f"balance {exchange}")

    # 移除 EC2 返回的 "正在查询..." 行，避免重复显示
    lines = output.strip().split('\n')
    for line in lines:
        if '正在查询' not in line:
            print(line)

    # Bybit 额外查询统一账户
    if exchange_base == "bybit":
        print("\n" + "=" * 50)
        print("📦 统一账户余额 (UNIFIED):")
        print("=" * 50)
        # 查询常用币种的统一账户余额
        unified_coins = ["USDT", "USDC", "BTC", "ETH"]
        has_balance = False
        for coin in unified_coins:
            try:
                bal_output = run_on_ec2(f"account_balance {exchange} UNIFIED {coin}")
                bal_output = bal_output.strip()
                if bal_output:
                    bal = float(bal_output)
                    if bal > 0:
                        has_balance = True
                        print(f"  {coin}: {bal:.4f}")
            except SSHError as e:
                print(f"  ⚠️ 查询 {coin} 失败: {e}")
            except ValueError:
                print(f"  ⚠️ {coin} 返回异常值: '{bal_output}'")
        if not has_balance:
            print("  统一账户暂无余额")
    


def show_pm_ratio(exchange: str = None):
    """查询统一保证金率"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 统一保证金率...")

    output = run_on_ec2(f"pm_ratio {exchange}")
    print(output)


def show_gate_subaccounts():
    """查询 Gate.io 子账户资产"""
    print("\n正在查询 Gate.io 子账户...")
    output = run_on_ec2("gate_subaccounts")
    
    # 移除 EC2 返回的 "正在查询..." 行
    lines = output.strip().split('\n')
    for line in lines:
        if '正在查询' not in line:
            print(line)


def _parse_balance_from_output(output: str, coin: str) -> str:
    """从 balance 命令输出中解析指定币种余额"""
    coin_upper = coin.upper()
    for line in output.split('\n'):
        line_upper = line.upper()
        if line_upper.startswith(coin_upper + '\t') or line_upper.startswith(coin_upper + ' '):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    # 验证是否为有效数字
                    float(parts[1])
                    return parts[1]
                except (ValueError, IndexError):
                    pass
            break
    return "0"


def show_position_analysis(exchange: str = None):
    """持仓分析 - 显示永续合约持仓金额、浮盈亏、距离平仓线"""
    if not exchange:
        exchange = select_exchange(binance_only=True)
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n正在分析 {display_name} 永续合约持仓...")

    # 获取永续合约持仓
    try:
        output = run_on_ec2(f"portfolio_um_positions {exchange}")
        positions = json.loads(output.strip())

        if isinstance(positions, dict) and "msg" in positions:
            print(f"API 错误: {positions.get('msg')}")
            return
    except json.JSONDecodeError:
        print("解析持仓数据失败")
        return
    except SSHError as e:
        print(f"获取持仓失败: {e}")
        return

    # 过滤有持仓的
    active_positions = []
    for p in positions:
        position_amt = float(p.get("positionAmt", 0))
        if position_amt == 0:
            continue

        symbol = p.get("symbol", "")
        entry_price = float(p.get("entryPrice", 0))
        mark_price = float(p.get("markPrice", 0))
        unrealized_pnl = float(p.get("unRealizedProfit", 0))
        liquidation_price = float(p.get("liquidationPrice", 0))
        notional = abs(position_amt * mark_price)
        side = "LONG" if position_amt > 0 else "SHORT"

        # 计算距离强平价格的百分比
        if liquidation_price > 0 and mark_price > 0:
            if side == "LONG":
                distance_pct = (mark_price - liquidation_price) / mark_price * 100
            else:
                distance_pct = (liquidation_price - mark_price) / mark_price * 100
        else:
            distance_pct = None

        active_positions.append({
            "symbol": symbol,
            "side": side,
            "positionAmt": position_amt,
            "entryPrice": entry_price,
            "markPrice": mark_price,
            "unrealizedPnl": unrealized_pnl,
            "notional": notional,
            "liquidationPrice": liquidation_price,
            "distancePct": distance_pct,
        })

    active_positions.sort(key=lambda x: x["notional"], reverse=True)

    if not active_positions:
        print("\n没有永续合约持仓")
        return

    # 显示持仓分析
    total_notional = sum(p["notional"] for p in active_positions)
    total_pnl = sum(p["unrealizedPnl"] for p in active_positions)

    print(f"\n{'=' * 65}")
    print(f"  永续合约持仓分析")
    print(f"{'=' * 65}")

    for i, pos in enumerate(active_positions, 1):
        symbol = pos["symbol"]
        side = "多" if pos["side"] == "LONG" else "空"
        amt = pos["positionAmt"]
        notional = pos["notional"]
        entry = pos["entryPrice"]
        mark = pos["markPrice"]
        pnl = pos["unrealizedPnl"]
        liq = pos["liquidationPrice"]
        dist = pos["distancePct"]

        pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"

        print(f"\n  {i}. {symbol} [{side}]")
        print(f"     持仓金额: ${notional:,.2f} | 数量: {amt}")
        print(f"     开仓价: {entry} | 标记价: {mark}")
        print(f"     浮动盈亏: ${pnl_str}")
        if liq > 0 and dist is not None:
            print(f"     强平价格: {liq} | 距平仓线: {dist:.2f}%")
        elif liq > 0:
            print(f"     强平价格: {liq}")
        else:
            print(f"     强平价格: N/A (统一保证金账户级别)")

    print(f"\n{'─' * 65}")
    total_pnl_str = f"+{total_pnl:.2f}" if total_pnl >= 0 else f"{total_pnl:.2f}"
    print(f"  总持仓金额: ${total_notional:,.2f}")
    print(f"  总浮动盈亏: ${total_pnl_str}")
    print(f"{'=' * 65}")


def get_coin_balance(exchange: str, coin: str, account_type: str = "SPOT") -> str:
    """查询指定币种余额

    Args:
        exchange: 交易所
        coin: 币种
        account_type: 账户类型 (SPOT/UNIFIED/FUND/EARN)

    Returns:
        余额字符串，失败返回 "0"
    """
    from utils import SSHError

    exchange_base = get_exchange_base(exchange)

    try:
        if exchange_base == "bybit":
            if account_type == "UNIFIED":
                output = run_on_ec2(f"account_balance {exchange} UNIFIED {coin}").strip()
                if output and not output.startswith(("用法", "未知", "错误")):
                    try:
                        return str(float(output))
                    except ValueError:
                        pass
                return "0"
            else:
                # 资金账户
                output = run_on_ec2(f"balance {exchange}")
                return _parse_balance_from_output(output, coin)

        elif exchange_base in ("gate", "bitget"):
            output = run_on_ec2(f"balance {exchange}")
            return _parse_balance_from_output(output, coin)

        else:
            # Binance - 使用 account_balance 命令精确查询
            output = run_on_ec2(f"account_balance {exchange} {account_type} {coin}").strip()
            if output and not output.startswith(("用法", "未知", "错误")):
                try:
                    return str(float(output))
                except ValueError:
                    pass
            return "0"

    except SSHError as e:
        print(f"❌ 查询余额失败: {e}")
        return "0"
