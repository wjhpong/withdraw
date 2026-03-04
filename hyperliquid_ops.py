#!/usr/bin/env python3
"""Hyperliquid 交易所专用功能 - 本地直接运行"""

from eth_account import Account
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from utils import load_config, get_exchange_display_name, input_amount, select_option


def get_hyperliquid_config(exchange: str = "hyperliquid"):
    """获取 Hyperliquid 配置，根据 exchange 参数查找对应用户"""
    config = load_config()

    # 从 _legacy 映射获取用户 ID
    legacy = config.get("_legacy", {})
    user_id = legacy.get(exchange)

    # 如果没有映射，尝试直接用 exchange 作为 user_id
    if not user_id:
        # 尝试解析 exchange 格式，例如 "eb65_hyperliquid" -> "eb65"
        if "_hyperliquid" in exchange:
            user_id = exchange.replace("_hyperliquid", "")
        else:
            user_id = "eb65"  # 默认用户

    user = config.get("users", {}).get(user_id, {})
    hl_config = user.get("accounts", {}).get("hyperliquid", {})

    wallet_address = hl_config.get("wallet_address", "")
    private_key = hl_config.get("private_key", "")

    if not wallet_address or not private_key:
        raise ValueError("Hyperliquid 配置缺失，请检查 config.json")

    return wallet_address, private_key


def show_hyperliquid_balance(exchange: str = "hyperliquid"):
    """查询 Hyperliquid 账户余额和保证金率"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 余额...")

    try:
        wallet_address, _ = get_hyperliquid_config(exchange)
        info = Info(constants.MAINNET_API_URL, skip_ws=True)

        # 获取用户状态
        user_state = info.user_state(wallet_address)

        print("\n" + "=" * 50)
        print("📊 Hyperliquid 账户概览:")
        print("=" * 50)

        # 显示保证金信息
        margin_summary = user_state.get("marginSummary", {})
        account_value = float(margin_summary.get("accountValue", 0))
        total_margin_used = float(margin_summary.get("totalMarginUsed", 0))
        total_ntl_pos = float(margin_summary.get("totalNtlPos", 0))
        withdrawable = float(user_state.get("withdrawable", 0))

        print(f"账户价值:     ${account_value:,.2f}")
        print(f"可用余额:     ${withdrawable:,.2f}")
        print(f"已用保证金:   ${total_margin_used:,.2f}")
        print(f"持仓名义价值: ${total_ntl_pos:,.2f}")

        # 保证金率和风险等级
        if total_margin_used > 0 and account_value > 0:
            margin_ratio = (total_margin_used / account_value) * 100
            print(f"保证金使用率: {margin_ratio:.2f}%", end="  ")
            if margin_ratio < 30:
                print("🟢 安全")
            elif margin_ratio < 60:
                print("🟡 中等")
            elif margin_ratio < 80:
                print("🟠 较高")
            else:
                print("🔴 危险")

        # 显示持仓（带平仓价信息）
        positions = user_state.get("assetPositions", [])
        has_position = False
        for pos in positions:
            position = pos.get("position", {})
            szi = float(position.get("szi", 0))
            if szi != 0:
                if not has_position:
                    print("\n" + "-" * 50)
                    print("📈 当前持仓:")
                    print("-" * 50)
                    all_mids = info.all_mids()
                    has_position = True

                coin = position.get("coin", "")
                entry_px = float(position.get("entryPx", 0))
                liquidation_px = float(position.get("liquidationPx", 0)) if position.get("liquidationPx") else None
                unrealized_pnl = float(position.get("unrealizedPnl", 0))
                leverage = position.get("leverage", {})
                lev_value = leverage.get("value", 0)
                current_px = float(all_mids.get(coin, 0))

                direction = "多" if szi > 0 else "空"
                print(f"\n{coin} {direction} {abs(szi):.4f} | {lev_value}x")
                print(f"  开仓: ${entry_px:,.4f}  当前: ${current_px:,.4f}  盈亏: ${unrealized_pnl:,.2f}")

                if liquidation_px and liquidation_px > 0:
                    if szi > 0:  # 多仓
                        distance_pct = ((current_px - liquidation_px) / current_px) * 100
                    else:  # 空仓
                        distance_pct = ((liquidation_px - current_px) / current_px) * 100

                    warning = ""
                    if distance_pct < 5:
                        warning = " ⚠️ 危险!"
                    elif distance_pct < 10:
                        warning = " ⚠️ 注意"
                    print(f"  平仓价: ${liquidation_px:,.4f}  距平仓线: {distance_pct:.2f}%{warning}")

        # 查询现货余额
        spot_state = info.spot_user_state(wallet_address)
        balances = spot_state.get("balances", [])
        has_spot = False
        for bal in balances:
            total = float(bal.get("total", 0))
            if total > 0:
                if not has_spot:
                    print("\n" + "-" * 50)
                    print("💰 现货余额:")
                    print("-" * 50)
                    has_spot = True
                coin = bal.get("coin", "")
                hold = float(bal.get("hold", 0))
                print(f"{coin}: {total:.6f}" + (f" (锁定: {hold:.6f})" if hold > 0 else ""))

    except ValueError as e:
        print(f"❌ 配置错误: {e}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")


def show_hyperliquid_margin_ratio(exchange: str = "hyperliquid"):
    """查询 Hyperliquid 合约账户保证金率和持仓信息"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 保证金率...")

    try:
        wallet_address, _ = get_hyperliquid_config(exchange)
        info = Info(constants.MAINNET_API_URL, skip_ws=True)

        user_state = info.user_state(wallet_address)
        margin_summary = user_state.get("marginSummary", {})

        account_value = float(margin_summary.get("accountValue", 0))
        total_margin_used = float(margin_summary.get("totalMarginUsed", 0))

        print("\n" + "=" * 50)
        print("📊 Hyperliquid 保证金状态:")
        print("=" * 50)

        if total_margin_used > 0:
            margin_ratio = (total_margin_used / account_value) * 100 if account_value > 0 else 0
            print(f"账户价值:   ${account_value:,.2f}")
            print(f"已用保证金: ${total_margin_used:,.2f}")
            print(f"保证金使用率: {margin_ratio:.2f}%")

            # 风险等级
            if margin_ratio < 30:
                print("风险等级: 🟢 安全")
            elif margin_ratio < 60:
                print("风险等级: 🟡 中等")
            elif margin_ratio < 80:
                print("风险等级: 🟠 较高")
            else:
                print("风险等级: 🔴 危险")

            # 显示持仓和距离平仓线
            positions = user_state.get("assetPositions", [])
            if positions:
                print("\n" + "-" * 50)
                print("📈 持仓详情:")
                print("-" * 50)

                # 获取所有币种的当前价格
                all_mids = info.all_mids()

                for pos in positions:
                    position = pos.get("position", {})
                    coin = position.get("coin", "")
                    szi = float(position.get("szi", 0))
                    if szi != 0:
                        entry_px = float(position.get("entryPx", 0))
                        liquidation_px = float(position.get("liquidationPx", 0)) if position.get("liquidationPx") else None
                        unrealized_pnl = float(position.get("unrealizedPnl", 0))
                        leverage = position.get("leverage", {})
                        lev_value = leverage.get("value", 0)

                        # 获取当前价格
                        current_px = float(all_mids.get(coin, 0))

                        direction = "多" if szi > 0 else "空"
                        print(f"\n{coin} {direction} {abs(szi):.4f}")
                        print(f"  开仓价: ${entry_px:,.4f}")
                        print(f"  当前价: ${current_px:,.4f}")
                        print(f"  杠杆: {lev_value}x")
                        print(f"  未实现盈亏: ${unrealized_pnl:,.2f}")

                        if liquidation_px and liquidation_px > 0:
                            # 计算距离平仓线百分比
                            if szi > 0:  # 多仓
                                distance_pct = ((current_px - liquidation_px) / current_px) * 100
                            else:  # 空仓
                                distance_pct = ((liquidation_px - current_px) / current_px) * 100

                            print(f"  平仓价: ${liquidation_px:,.4f}")
                            print(f"  距平仓线: {distance_pct:.2f}%")

                            if distance_pct < 5:
                                print(f"  ⚠️  警告: 距平仓线不足5%!")
                            elif distance_pct < 10:
                                print(f"  ⚠️  注意: 距平仓线不足10%")
        else:
            print(f"账户价值: ${account_value:,.2f}")
            print("无持仓")

    except ValueError as e:
        print(f"❌ 配置错误: {e}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")


def do_hyperliquid_transfer(exchange: str):
    """Hyperliquid 账户划转 - Spot <-> Perp"""
    display_name = get_exchange_display_name(exchange)

    try:
        wallet_address, private_key = get_hyperliquid_config(exchange)
        info = Info(constants.MAINNET_API_URL, skip_ws=True)

        # 获取当前余额
        user_state = info.user_state(wallet_address)
        perp_balance = float(user_state.get("withdrawable", 0))

        spot_state = info.spot_user_state(wallet_address)
        spot_usdc = 0
        for bal in spot_state.get("balances", []):
            if bal.get("coin") == "USDC":
                spot_usdc = float(bal.get("total", 0)) - float(bal.get("hold", 0))
                break

        print(f"\n当前余额:")
        print(f"  合约账户 (可用): ${perp_balance:,.2f}")
        print(f"  现货账户 USDC:   ${spot_usdc:,.2f}")

        # 选择方向
        options = [
            f"现货 -> 合约 (可用: ${spot_usdc:,.2f})",
            f"合约 -> 现货 (可用: ${perp_balance:,.2f})"
        ]
        idx = select_option("请选择划转方向:", options, allow_back=True)
        if idx == -1:
            return

        is_spot_to_perp = (idx == 0)
        max_amount = spot_usdc if is_spot_to_perp else perp_balance

        if max_amount <= 0:
            print("❌ 可用余额不足")
            return

        # 输入金额
        amount = input_amount(f"请输入划转金额 (最大 {max_amount:,.2f}): ")
        if not amount:
            return

        if amount > max_amount:
            print(f"❌ 超过可用余额 {max_amount:,.2f}")
            return

        # 确认
        direction = "现货 -> 合约" if is_spot_to_perp else "合约 -> 现货"
        confirm = input(f"\n确认划转 {amount} USDC ({direction})? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

        # 执行划转 (使用 API Wallet 模式，wallet_address 是主账户，私钥是 API Wallet 的)
        wallet = Account.from_key(private_key)
        exchange_client = Exchange(wallet, constants.MAINNET_API_URL, account_address=wallet_address)

        # usd_class_transfer: to_perp=True 划转到合约, to_perp=False 划转到现货
        result = exchange_client.usd_class_transfer(amount, is_spot_to_perp)

        if result.get("status") == "ok":
            print(f"✅ 划转成功: {amount} USDC ({direction})")
        else:
            print(f"❌ 划转失败: {result}")

    except ValueError as e:
        print(f"❌ 配置错误: {e}")
    except Exception as e:
        print(f"❌ 划转失败: {e}")
