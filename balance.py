#!/usr/bin/env python3
"""余额查询"""

import json
import subprocess
import requests
from utils import (run_on_ec2, select_option, select_exchange, get_exchange_base,
                   get_exchange_display_name, get_user_accounts, get_ec2_exchange_key,
                   load_config, SSHError, get_ssh_config, run_bybit_api_script)

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


def show_bybit_margin_ratio(exchange: str = None):
    """查询 Bybit 统一账户保证金率"""
    if not exchange:
        exchange = select_exchange(bybit_only=True)
        if not exchange:
            return

    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 统一保证金率...")

    from funding import _BYBIT_SIGNED_GET_SCRIPT
    script = _BYBIT_SIGNED_GET_SCRIPT + r"""
import sys

# 查询统一账户钱包余额
data = signed_get("/v5/account/wallet-balance", {"accountType": "UNIFIED"})
if data.get("retCode") != 0:
    print(json.dumps({"error": data.get("retMsg", str(data.get("retCode")))}))
    sys.exit(0)

accounts = data.get("result", {}).get("list", [])
if not accounts:
    print(json.dumps({"error": "无账户数据"}))
    sys.exit(0)

acc = accounts[0]
result = {
    "totalEquity": acc.get("totalEquity", "0"),
    "totalMarginBalance": acc.get("totalMarginBalance", "0"),
    "totalInitialMargin": acc.get("totalInitialMargin", "0"),
    "totalMaintenanceMargin": acc.get("totalMaintenanceMargin", "0"),
    "totalAvailableBalance": acc.get("totalAvailableBalance", "0"),
    "totalPerpUPL": acc.get("totalPerpUPL", "0"),
    "accountIMRate": acc.get("accountIMRate", "0"),
    "accountMMRate": acc.get("accountMMRate", "0"),
}

# 查询持仓
pos_data = signed_get("/v5/position/list", {"category": "linear", "limit": "200", "settleCoin": "USDT"})
positions = []
if pos_data.get("retCode") == 0:
    for p in pos_data.get("result", {}).get("list", []):
        size = float(p.get("size", 0))
        if size == 0:
            continue
        positions.append({
            "symbol": p.get("symbol", ""),
            "side": p.get("side", ""),
            "size": p.get("size", "0"),
            "positionValue": p.get("positionValue", "0"),
            "leverage": p.get("leverage", "0"),
            "markPrice": p.get("markPrice", "0"),
            "unrealisedPnl": p.get("unrealisedPnl", "0"),
            "liqPrice": p.get("liqPrice", ""),
        })

result["positions"] = positions
print(json.dumps(result))
"""

    try:
        output = run_bybit_api_script(exchange, script)
        data = json.loads(output)
        if "error" in data:
            print(f"查询失败: {data['error']}")
            return

        equity = float(data.get("totalEquity", 0))
        margin_bal = float(data.get("totalMarginBalance", 0))
        init_margin = float(data.get("totalInitialMargin", 0))
        maint_margin = float(data.get("totalMaintenanceMargin", 0))
        avail_bal = float(data.get("totalAvailableBalance", 0))
        perp_upl = float(data.get("totalPerpUPL", 0))
        im_rate = float(data.get("accountIMRate", 0)) * 100
        mm_rate = float(data.get("accountMMRate", 0)) * 100

        print(f"\n{'=' * 55}")
        print(f"  {display_name} 统一账户概览")
        print(f"{'=' * 55}")
        print(f"  账户权益:     ${equity:>12,.2f} USD")
        print(f"  保证金余额:   ${margin_bal:>12,.2f} USD")
        print(f"  可用余额:     ${avail_bal:>12,.2f} USD")
        print(f"  初始保证金:   ${init_margin:>12,.2f} USD")
        print(f"  维持保证金:   ${maint_margin:>12,.2f} USD")
        print(f"  未实现盈亏:   ${perp_upl:>+12,.2f} USD")
        print(f"  初始保证金率: {im_rate:>8.2f}%")
        print(f"  维持保证金率: {mm_rate:>8.2f}%", end="  ")
        if mm_rate < 30:
            print("安全")
        elif mm_rate < 60:
            print("注意")
        elif mm_rate < 80:
            print("警告")
        else:
            print("危险")

        positions = data.get("positions", [])
        if positions:
            positions.sort(key=lambda x: abs(float(x.get("positionValue", 0))), reverse=True)
            print(f"\n{'─' * 55}")
            print(f"  持仓明细 ({len(positions)} 个)")
            print(f"{'─' * 55}")
            for p in positions:
                symbol = p["symbol"].replace("USDT", "")
                side = "多" if p["side"] == "Buy" else "空"
                value = float(p.get("positionValue", 0))
                leverage = p.get("leverage", "?")
                upl = float(p.get("unrealisedPnl", 0))
                liq = p.get("liqPrice", "")
                liq_str = f"强平: {float(liq):.4f}" if liq else "强平: --"
                print(f"  {symbol:<10} [{side}] {leverage}x  价值: ${value:>10,.2f}  盈亏: ${upl:>+8,.2f}  {liq_str}")

        print(f"{'=' * 55}")
    except SSHError as e:
        print(f"查询失败: {e}")
    except Exception as e:
        print(f"查询失败: {e}")


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
                raw = parts[1].strip()
                try:
                    return str(_parse_number(raw))
                except ValueError:
                    pass
            break
    return "0"


def _parse_number(s: str) -> float:
    """解析数字字符串，支持 K/M/B 后缀和逗号"""
    s = s.strip().replace(",", "")
    suffixes = {"K": 1e3, "M": 1e6, "B": 1e9}
    if s and s[-1].upper() in suffixes:
        return float(s[:-1]) * suffixes[s[-1].upper()]
    return float(s)


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
        leverage = int(p.get("leverage", 0))
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
            "leverage": leverage,
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

        lev = pos["leverage"]
        lev_str = f" {lev}x" if lev > 0 else ""
        print(f"\n  {i}. {symbol} [{side}]{lev_str}")
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

    # 修改杠杆倍数
    while True:
        action = select_option("\n是否修改杠杆倍数?", ["修改杠杆", "返回"], allow_back=True)
        if action != 0:
            break

        # 选择要修改的仓位
        pos_options = []
        for p in active_positions:
            side_str = "多" if p["side"] == "LONG" else "空"
            pos_options.append(f"{p['symbol']} [{side_str}] 当前 {p['leverage']}x")
        idx = select_option("选择要修改的仓位:", pos_options, allow_back=True)
        if idx == -1:
            continue

        pos = active_positions[idx]
        new_lev = input(f"请输入新杠杆倍数 (当前 {pos['leverage']}x, 范围 1-125, 输入 0 返回): ").strip()
        if not new_lev or new_lev == "0":
            continue

        try:
            new_lev_int = int(new_lev)
            if new_lev_int < 1 or new_lev_int > 125:
                print("杠杆倍数必须在 1-125 之间")
                continue
        except ValueError:
            print("请输入有效的数字")
            continue

        side_str = "多" if pos["side"] == "LONG" else "空"
        print(f"\n确认修改 {pos['symbol']} [{side_str}] 杠杆: {pos['leverage']}x → {new_lev_int}x")
        confirm = select_option("确认?", ["确认", "取消"])
        if confirm != 0:
            print("已取消")
            continue

        try:
            output = run_on_ec2(f"change_leverage {exchange} {pos['symbol']} {new_lev_int}")
            try:
                result = json.loads(output.strip())
                if "error" in result:
                    print(f"❌ 修改失败: {result.get('error', result.get('msg', str(result)))}")
                elif "leverage" in result:
                    print(f"✅ {pos['symbol']} 杠杆已修改为 {result['leverage']}x")
                    pos["leverage"] = int(result["leverage"])
                else:
                    print(output)
            except json.JSONDecodeError:
                print(output)
        except SSHError as e:
            print(f"❌ 修改失败: {e}")


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


def show_multi_exchange_balance(user_id: str):
    """查询用户所有交易所的稳定币余额汇总 (USDT/USD1/USDC)"""
    config = load_config()
    user_name = config.get("users", {}).get(user_id, {}).get("name", user_id)
    accounts = get_user_accounts(user_id)

    if not accounts:
        print(f"\n{user_name} 没有配置任何交易所账号")
        return

    print(f"\n正在查询 {user_name} 所有交易所稳定币余额...")
    print(f"\n{'=' * 55}")
    print(f"  {user_name} - 多交易所稳定币余额")
    print(f"{'=' * 55}")

    total_usdt = 0.0
    results = []

    for account_id, exchange_name in accounts:
        ec2_exchange = get_ec2_exchange_key(user_id, account_id)
        exchange_base = get_exchange_base(ec2_exchange)

        # Hyperliquid 使用本地查询
        if exchange_base == "hyperliquid":
            try:
                from hyperliquid_ops import get_hyperliquid_config
                from hyperliquid.info import Info
                from hyperliquid.utils import constants
                wallet_address, _ = get_hyperliquid_config()
                info = Info(constants.MAINNET_API_URL, skip_ws=True)
                user_state = info.user_state(wallet_address)
                usdt = float(user_state.get("withdrawable", 0))
                results.append((exchange_name, usdt, None))
                total_usdt += usdt
            except Exception as e:
                results.append((exchange_name, None, str(e)))
            continue

        # Lighter 使用本地查询
        if exchange_base == "lighter":
            try:
                import asyncio
                from lighter_ops import get_lighter_config, _get_account_info
                wallet_address, _, _ = get_lighter_config(ec2_exchange)
                account_info = asyncio.run(_get_account_info(wallet_address))
                usdt = 0.0
                if account_info and account_info.accounts:
                    for acc in account_info.accounts:
                        if acc.account_type == 0:
                            usdt = float(acc.available_balance) if acc.available_balance else 0
                            break
                results.append((exchange_name, usdt, None))
                total_usdt += usdt
            except Exception as e:
                results.append((exchange_name, None, str(e)))
            continue

        # 通过 EC2 查询
        try:
            if exchange_base == "bybit":
                # Bybit 统一账户查 USDT
                output = run_on_ec2(f"account_balance {ec2_exchange} UNIFIED USDT").strip()
                try:
                    usdt = float(output)
                except ValueError:
                    usdt = 0.0
                # 再查资金账户
                fund_output = run_on_ec2(f"balance {ec2_exchange}")
                fund_usdt = float(_parse_balance_from_output(fund_output, "USDT"))
                usdt += fund_usdt
            elif exchange_base in ("gate", "bitget"):
                output = run_on_ec2(f"balance {ec2_exchange}")
                usdt = float(_parse_balance_from_output(output, "USDT"))
            elif exchange_base == "aster":
                # Aster - 从 balance 输出解析合约账户和现货的 USDT
                output = run_on_ec2(f"balance {ec2_exchange}")
                usdt = 0.0
                for line in output.split('\n'):
                    parts = line.split()
                    # 合约账户格式: "USDT      余额:      64937.7085  可提:   45445.7974"
                    if len(parts) >= 2 and parts[0] == "USDT" and "余额:" in line:
                        for j, p in enumerate(parts):
                            if p == "余额:" and j + 1 < len(parts):
                                try:
                                    usdt += float(parts[j + 1])
                                except ValueError:
                                    pass
                    # 现货格式: "USDT     可用:      1000.0  冻结:     0.0"
                    elif len(parts) >= 2 and parts[0] == "USDT" and "可用:" in line:
                        for j, p in enumerate(parts):
                            if p == "可用:" and j + 1 < len(parts):
                                try:
                                    usdt += float(parts[j + 1])
                                except ValueError:
                                    pass
            else:
                # Binance 等 - 查现货和理财
                output = run_on_ec2(f"account_balance {ec2_exchange} SPOT USDT").strip()
                try:
                    usdt = float(output)
                except ValueError:
                    usdt = 0.0
                # Binance 只统计现货 (SPOT)，不含理财和统一账户

            results.append((exchange_name, usdt, None))
            total_usdt += usdt

        except SSHError as e:
            results.append((exchange_name, None, str(e)))

    # 显示结果
    for exchange_name, usdt, error in results:
        if error:
            print(f"  {exchange_name:<18} ⚠️  查询失败: {error}")
        elif usdt is not None:
            print(f"  {exchange_name:<18} {usdt:>14,.2f} USDT")
        else:
            print(f"  {exchange_name:<18} ⚠️  未知错误")

    print(f"{'─' * 55}")
    print(f"  {'合计':<18} {total_usdt:>14,.2f} USDT")
    print(f"{'=' * 55}")

    # 查询合约持仓分布
    _show_position_distribution(user_id, accounts)


def _show_position_distribution(user_id: str, accounts: list):
    """查询并展示用户所有交易所的合约持仓分布"""
    config = load_config()
    user_name = config.get("users", {}).get(user_id, {}).get("name", user_id)

    all_positions = []  # [(symbol, notional, quantity), ...]

    print(f"\n正在查询合约持仓...")

    for account_id, exchange_name in accounts:
        ec2_exchange = get_ec2_exchange_key(user_id, account_id)
        exchange_base = get_exchange_base(ec2_exchange)

        # Binance - 通过 EC2 查询 portfolio_um_positions
        if exchange_base == "binance":
            try:
                output = run_on_ec2(f"portfolio_um_positions {ec2_exchange}")
                positions = json.loads(output.strip())
                if isinstance(positions, list):
                    for p in positions:
                        amt = float(p.get("positionAmt", 0))
                        if amt == 0:
                            continue
                        symbol = p.get("symbol", "").replace("USDT", "")
                        mark = float(p.get("markPrice", 0))
                        notional = abs(amt * mark)
                        all_positions.append((symbol, notional, abs(amt)))
            except (json.JSONDecodeError, SSHError):
                pass

        # Hyperliquid - 本地查询
        elif exchange_base == "hyperliquid":
            try:
                from hyperliquid_ops import get_hyperliquid_config
                from hyperliquid.info import Info
                from hyperliquid.utils import constants
                wallet_address, _ = get_hyperliquid_config()
                info = Info(constants.MAINNET_API_URL, skip_ws=True)
                user_state = info.user_state(wallet_address)
                all_mids = info.all_mids()
                for pos in user_state.get("assetPositions", []):
                    position = pos.get("position", {})
                    szi = float(position.get("szi", 0))
                    if szi == 0:
                        continue
                    coin = position.get("coin", "")
                    current_px = float(all_mids.get(coin, 0))
                    notional = abs(szi * current_px)
                    all_positions.append((coin, notional, abs(szi)))
            except Exception:
                pass

        # Lighter - 本地查询
        elif exchange_base == "lighter":
            try:
                import asyncio
                from lighter_ops import get_lighter_config, _get_account_info
                wallet_address, _, _ = get_lighter_config(ec2_exchange)
                account_info = asyncio.run(_get_account_info(wallet_address))
                if account_info and account_info.accounts:
                    for acc in account_info.accounts:
                        if acc.account_type == 0 and acc.positions:
                            for pos in acc.positions:
                                size = float(pos.position) if hasattr(pos, 'position') and pos.position else 0
                                if size == 0:
                                    continue
                                symbol = pos.symbol if hasattr(pos, 'symbol') else "?"
                                # 去掉 _USDT 后缀
                                symbol = symbol.replace("_USDT", "").replace("USDT", "")
                                pv = float(pos.position_value) if hasattr(pos, 'position_value') and pos.position_value else 0
                                all_positions.append((symbol, abs(pv), abs(size)))
                            break
            except Exception:
                pass

        # Aster - 从 balance 输出解析持仓
        elif exchange_base == "aster":
            try:
                output = run_on_ec2(f"balance {ec2_exchange}")
                for line in output.split('\n'):
                    parts = line.split()
                    # 格式: "ASTERUSDT  SHORT  数量:191176.0000  杠杆:3x"
                    if len(parts) >= 3 and parts[1] in ("LONG", "SHORT") and parts[2].startswith("数量:"):
                        symbol = parts[0].replace("USDT", "")
                        amt = abs(float(parts[2].split(":")[1]))
                        # 下一行有标记价: "开仓:0.5946  标记:0.6965 ..."
                        # 从同一输出中查找
                        lines = output.split('\n')
                        idx = lines.index(line)
                        if idx + 1 < len(lines):
                            next_line = lines[idx + 1]
                            for part in next_line.split():
                                if part.startswith("标记:"):
                                    mark = float(part.split(":")[1])
                                    notional = amt * mark
                                    all_positions.append((symbol, notional, amt))
                                    break
            except (SSHError, ValueError):
                pass

        # Bybit - 通过 EC2 出口 IP 调用 V5 API 查询持仓
        elif exchange_base == "bybit":
            try:
                from funding import _BYBIT_SIGNED_GET_SCRIPT
                script = _BYBIT_SIGNED_GET_SCRIPT + r"""
positions = []
cursor = ""
for _ in range(10):
    params = {"category": "linear", "limit": "200", "settleCoin": "USDT"}
    if cursor:
        params["cursor"] = cursor
    data = signed_get("/v5/position/list", params)
    if data.get("retCode") != 0:
        break
    result = data.get("result", {})
    rows = result.get("list", [])
    for row in rows:
        size = float(row.get("size", 0))
        if size == 0:
            continue
        symbol = row.get("symbol", "").replace("USDT", "")
        mark_price = float(row.get("markPrice", 0))
        notional = size * mark_price
        positions.append({"symbol": symbol, "notional": notional, "qty": size})
    cursor = result.get("nextPageCursor", "")
    if not cursor:
        break
print(json.dumps(positions))
"""
                output = run_bybit_api_script(ec2_exchange, script)
                if output:
                    bybit_positions = json.loads(output)
                    for p in bybit_positions:
                        all_positions.append((p["symbol"], p["notional"], p.get("qty", 0)))
            except Exception:
                pass

    if not all_positions:
        print("\n没有合约持仓")
        return

    # 合并同一币种的持仓 (notional, quantity)
    merged = {}
    for symbol, notional, qty in all_positions:
        prev_n, prev_q = merged.get(symbol, (0, 0))
        merged[symbol] = (prev_n + notional, prev_q + qty)

    # 按市值排序
    sorted_positions = sorted(merged.items(), key=lambda x: x[1][0], reverse=True)
    total_notional = sum(v[0] for _, v in sorted_positions)

    print(f"\n{'=' * 75}")
    print(f"  {user_name} 合约持仓分布")
    print(f"  总开仓市值: ${total_notional:,.2f} USDT")
    print(f"{'=' * 75}")

    # 柱状图展示
    BAR_MAX_LEN = 20
    max_notional = sorted_positions[0][1][0] if sorted_positions else 1

    for symbol, (notional, qty) in sorted_positions:
        pct = (notional / total_notional * 100) if total_notional > 0 else 0
        bar_len = int(notional / max_notional * BAR_MAX_LEN)
        bar = "█" * bar_len
        # 格式化数量
        if qty == int(qty):
            qty_str = f"{int(qty):,}"
        elif qty >= 1:
            qty_str = f"{qty:,.1f}"
        else:
            qty_str = f"{qty:.4f}"
        print(f"  {symbol:>10} {bar:<{BAR_MAX_LEN}}  $ {notional:>12,.2f} ({pct:>5.1f}%)  x{qty_str}")

    print(f"{'=' * 75}")
