#!/usr/bin/env python3
"""Lighter 交易所专用功能 - 本地直接运行"""

import asyncio
from lighter import ApiClient, AccountApi, InfoApi
from lighter.configuration import Configuration
from utils import load_config, get_exchange_display_name, input_amount, select_option

LIGHTER_MAINNET_URL = "https://mainnet.zklighter.elliot.ai"


def get_lighter_config(user_id: str = "eb65"):
    """获取 Lighter 配置"""
    config = load_config()
    user = config.get("users", {}).get(user_id, {})
    lighter_config = user.get("accounts", {}).get("lighter", {})

    wallet_address = lighter_config.get("wallet_address", "")
    api_key = lighter_config.get("api_key", "")
    key_index = lighter_config.get("key_index", 0)

    if not wallet_address or not api_key:
        raise ValueError("Lighter 配置缺失，请检查 config.json")

    return wallet_address, api_key, key_index


async def _get_account_info(wallet_address: str):
    """异步获取账户信息"""
    config = Configuration(host=LIGHTER_MAINNET_URL)
    async with ApiClient(config) as api_client:
        account_api = AccountApi(api_client)
        # 使用地址查询账户 (参数是 l1_address 不是 l1Address)
        result = await account_api.account(by="l1_address", value=wallet_address)
        return result


async def _get_market_prices():
    """异步获取所有市场当前价格"""
    from lighter import OrderApi
    config = Configuration(host=LIGHTER_MAINNET_URL)
    async with ApiClient(config) as api_client:
        order_api = OrderApi(api_client)
        result = await order_api.order_book_details()
        # 返回 symbol -> price 的映射
        prices = {}
        if result and result.order_book_details:
            for book in result.order_book_details:
                if hasattr(book, 'symbol') and hasattr(book, 'last_trade_price'):
                    prices[book.symbol] = float(book.last_trade_price) if book.last_trade_price else 0
        return prices


def show_lighter_balance(exchange: str = "lighter"):
    """查询 Lighter 账户余额"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 余额...")

    try:
        wallet_address, _, _ = get_lighter_config()

        # 运行异步查询
        account_info = asyncio.run(_get_account_info(wallet_address))

        if not account_info or not account_info.accounts:
            print("❌ 未找到账户信息")
            return

        # 只显示主账户 (account_type == 0)
        main_account = None
        for acc in account_info.accounts:
            if acc.account_type == 0:
                main_account = acc
                break

        if not main_account:
            main_account = account_info.accounts[0]

        print("\n" + "=" * 50)
        print("📊 Lighter 账户余额:")
        print("=" * 50)

        # 显示保证金/抵押品
        collateral = float(main_account.collateral) if main_account.collateral else 0
        available_balance = float(main_account.available_balance) if main_account.available_balance else 0
        total_asset_value = float(main_account.total_asset_value) if main_account.total_asset_value else 0

        print(f"总资产价值:  ${total_asset_value:,.2f}")
        print(f"抵押品:       ${collateral:,.2f}")
        print(f"可用余额:     ${available_balance:,.2f}")

        # 显示资产
        if main_account.assets:
            print("\n" + "-" * 50)
            print("💰 资产:")
            print("-" * 50)
            for asset in main_account.assets:
                symbol = asset.symbol if hasattr(asset, 'symbol') else "?"
                balance = float(asset.balance) if hasattr(asset, 'balance') and asset.balance else 0
                locked = float(asset.locked_balance) if hasattr(asset, 'locked_balance') and asset.locked_balance else 0
                if balance > 0:
                    print(f"{symbol}: {balance:,.6f} (锁定: {locked:,.6f})")

        # 显示持仓
        if main_account.positions:
            has_position = False
            for pos in main_account.positions:
                position_size = float(pos.position) if hasattr(pos, 'position') and pos.position else 0
                if position_size != 0:
                    if not has_position:
                        print("\n" + "-" * 50)
                        print("📈 当前持仓:")
                        print("-" * 50)
                        has_position = True

                    symbol = pos.symbol if hasattr(pos, 'symbol') else "?"
                    sign = pos.sign if hasattr(pos, 'sign') else 1
                    direction = "多" if sign > 0 else "空"
                    avg_entry = float(pos.avg_entry_price) if hasattr(pos, 'avg_entry_price') and pos.avg_entry_price else 0
                    position_value = float(pos.position_value) if hasattr(pos, 'position_value') and pos.position_value else 0
                    unrealized_pnl = float(pos.unrealized_pnl) if hasattr(pos, 'unrealized_pnl') and pos.unrealized_pnl else 0

                    print(f"\n{symbol}: {direction} {abs(position_size):,.4f}")
                    print(f"  开仓均价: ${avg_entry:,.4f}")
                    print(f"  持仓价值: ${abs(position_value):,.2f}")
                    print(f"  未实现盈亏: ${unrealized_pnl:,.2f}")

    except ValueError as e:
        print(f"❌ 配置错误: {e}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")


def show_lighter_margin_ratio(exchange: str = "lighter"):
    """查询 Lighter 合约账户保证金率和持仓信息"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n正在查询 {display_name} 保证金率...")

    try:
        wallet_address, _, _ = get_lighter_config()

        # 运行异步查询 - 同时获取账户信息和市场价格
        async def fetch_all():
            account_task = _get_account_info(wallet_address)
            prices_task = _get_market_prices()
            return await asyncio.gather(account_task, prices_task)

        account_info, market_prices = asyncio.run(fetch_all())

        if not account_info or not account_info.accounts:
            print("❌ 未找到账户信息")
            return

        # 只显示主账户 (account_type == 0)
        main_account = None
        for acc in account_info.accounts:
            if acc.account_type == 0:
                main_account = acc
                break

        if not main_account:
            main_account = account_info.accounts[0]

        print("\n" + "=" * 50)
        print("📊 Lighter 保证金状态:")
        print("=" * 50)

        # 获取保证金信息
        collateral = float(main_account.collateral) if main_account.collateral else 0
        available_balance = float(main_account.available_balance) if main_account.available_balance else 0
        total_asset_value = float(main_account.total_asset_value) if main_account.total_asset_value else 0

        print(f"总资产价值:  ${total_asset_value:,.2f}")
        print(f"抵押品:       ${collateral:,.2f}")
        print(f"可用余额:     ${available_balance:,.2f}")

        # 计算持仓相关
        total_position_value = 0
        total_unrealized_pnl = 0

        # 显示持仓详情和距离平仓线
        if main_account.positions:
            has_position = False
            for pos in main_account.positions:
                position_size = float(pos.position) if hasattr(pos, 'position') and pos.position else 0
                if position_size != 0:
                    if not has_position:
                        print("\n" + "-" * 50)
                        print("📈 持仓详情:")
                        print("-" * 50)
                        has_position = True

                    symbol = pos.symbol if hasattr(pos, 'symbol') else "?"
                    sign = pos.sign if hasattr(pos, 'sign') else 1
                    direction = "多" if sign > 0 else "空"
                    avg_entry = float(pos.avg_entry_price) if hasattr(pos, 'avg_entry_price') and pos.avg_entry_price else 0
                    position_value = float(pos.position_value) if hasattr(pos, 'position_value') and pos.position_value else 0
                    unrealized_pnl = float(pos.unrealized_pnl) if hasattr(pos, 'unrealized_pnl') and pos.unrealized_pnl else 0
                    liquidation_price = float(pos.liquidation_price) if hasattr(pos, 'liquidation_price') and pos.liquidation_price else 0

                    total_position_value += abs(position_value)
                    total_unrealized_pnl += unrealized_pnl

                    # 获取当前价格
                    current_price = market_prices.get(symbol, 0)

                    print(f"\n{symbol}: {direction} {abs(position_size):,.4f}")
                    print(f"  开仓均价: ${avg_entry:,.4f}")
                    print(f"  当前价格: ${current_price:,.4f}")
                    print(f"  持仓价值: ${abs(position_value):,.2f}")
                    print(f"  未实现盈亏: ${unrealized_pnl:,.2f}")

                    if liquidation_price > 0:
                        print(f"  平仓价: ${liquidation_price:,.4f}")

                        # 计算距离平仓线 - 使用当前价格
                        if current_price > 0:
                            if sign > 0:  # 多仓
                                distance_pct = ((current_price - liquidation_price) / current_price) * 100
                            else:  # 空仓
                                distance_pct = ((liquidation_price - current_price) / current_price) * 100

                            print(f"  距平仓线: {distance_pct:.2f}%")

                            if distance_pct < 5:
                                print(f"  ⚠️  警告: 距平仓线不足5%!")
                            elif distance_pct < 10:
                                print(f"  ⚠️  注意: 距平仓线不足10%")

            if has_position:
                print("\n" + "-" * 50)
                print(f"总持仓价值:   ${total_position_value:,.2f}")
                print(f"总未实现盈亏: ${total_unrealized_pnl:,.2f}")
        else:
            print("\n无持仓")

    except ValueError as e:
        print(f"❌ 配置错误: {e}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")


def do_lighter_transfer(exchange: str):
    """Lighter 账户划转"""
    display_name = get_exchange_display_name(exchange)
    print(f"\n{display_name} 暂不支持划转功能")
