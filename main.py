#!/usr/bin/env python3
"""
交易所工具脚本 - 主入口
本地控制 -> EC2执行
"""

from utils import (
    select_option, select_user, select_account, get_ec2_exchange_key,
    get_exchange_base, get_user_accounts, load_config
)
from balance import show_balance, show_pm_ratio, show_gate_subaccounts
from aster import show_aster_margin_ratio
from hyperliquid_ops import show_hyperliquid_balance, show_hyperliquid_margin_ratio, do_hyperliquid_transfer
from lighter_ops import show_lighter_balance, show_lighter_margin_ratio
from withdraw_ops import do_withdraw
from transfer import do_transfer
from earn import manage_earn
from trade import do_stablecoin_trade, cancel_orders_menu, market_sell_menu, futures_close_menu
from addresses import manage_addresses
from bnb_tools import manage_bnb_tools
from funding import show_funding_rate, show_binance_funding_history, show_aster_funding_history, show_hyperliquid_funding_history, show_lighter_funding_history


def main():
    print("=" * 50)
    print("    交易所工具脚本 (本地控制 -> EC2执行)")
    print("=" * 50)

    while True:
        # 1. 先选择用户
        user_id = select_user(allow_back=False)
        if not user_id:
            print("\n再见!")
            break

        config = load_config()
        user_name = config.get("users", {}).get(user_id, {}).get("name", user_id)

        # 2. 再选择交易所账号
        account_id = select_account(user_id, allow_back=True)
        if not account_id:
            continue  # 返回重新选用户

        # 获取 EC2 使用的交易所 key
        ec2_exchange = get_ec2_exchange_key(user_id, account_id)
        exchange_base = get_exchange_base(ec2_exchange)

        # 获取显示名称
        accounts = get_user_accounts(user_id)
        exchange_name = next((name for aid, name in accounts if aid == account_id), account_id.upper())

        # 3. 显示功能菜单
        while True:
            print(f"\n{'=' * 50}")
            print(f"    {user_name} - {exchange_name}")
            print("=" * 50)

            # 根据交易所类型构建菜单
            options = []

            # Hyperliquid 和 Lighter 使用本地函数，其他交易所通过 EC2
            if exchange_base == "hyperliquid":
                options.append(("查询余额", lambda: show_hyperliquid_balance()))
                options.append(("账户划转", lambda: do_hyperliquid_transfer("hyperliquid")))
                options.append(("保证金率", lambda: show_hyperliquid_margin_ratio()))
                options.append(("历史费率", lambda u=user_id: show_hyperliquid_funding_history(u)))
            elif exchange_base == "lighter":
                options.append(("查询余额", lambda: show_lighter_balance()))
                options.append(("保证金率", lambda: show_lighter_margin_ratio()))
                options.append(("历史费率", lambda u=user_id: show_lighter_funding_history(u)))
            else:
                # 所有其他交易所都支持查询余额
                options.append(("查询余额", lambda ex=ec2_exchange: show_balance(ex)))

                # Aster 和 Gate 不支持提现，Frances/Vanie/李天一 禁用提现
                if exchange_base not in ("aster", "gate") and user_id not in ("frances", "vanie", "litianyi"):
                    options.append(("提现", lambda ex=ec2_exchange: do_withdraw(ex)))

                # 账户划转 (Gate 不支持)
                if exchange_base != "gate":
                    options.append(("账户划转", lambda ex=ec2_exchange: do_transfer(ex)))

                # 交易功能 (撤单、市价卖出)
                options.append(("撤单", lambda ex=ec2_exchange: cancel_orders_menu(ex)))
                options.append(("市价卖出", lambda ex=ec2_exchange: market_sell_menu(ex)))

                # Binance 特有功能
                if exchange_base == "binance":
                    options.append(("永续平仓", lambda ex=ec2_exchange: futures_close_menu(ex)))
                    options.append(("理财管理", lambda ex=ec2_exchange: manage_earn(ex)))
                    options.append(("稳定币交易", lambda ex=ec2_exchange: do_stablecoin_trade(ex)))
                    options.append(("BNB工具", lambda ex=ec2_exchange: manage_bnb_tools(ex)))
                    options.append(("统一保证金率", lambda ex=ec2_exchange: show_pm_ratio(ex)))
                    options.append(("历史费率", lambda ex=ec2_exchange: show_binance_funding_history(ex)))

                # Gate 特有功能
                if exchange_base == "gate":
                    options.append(("子账户资产", lambda: show_gate_subaccounts()))

                # Bybit 特有功能
                if exchange_base == "bybit":
                    options.append(("资金费率", lambda: show_funding_rate("bybit")))

                # Aster 特有功能
                if exchange_base == "aster":
                    options.append(("统一保证金率", lambda ex=ec2_exchange: show_aster_margin_ratio(ex)))
                    options.append(("历史费率", lambda ex=ec2_exchange: show_aster_funding_history(ex)))

                # 地址管理 (Aster 不需要，Frances/Vanie/李天一 禁用)
                if exchange_base != "aster" and user_id not in ("frances", "vanie", "litianyi"):
                    options.append(("管理地址簿", lambda ex=ec2_exchange: manage_addresses(ex)))

            # 导航选项
            options.append(("切换用户/交易所", None))
            options.append(("退出", "exit"))

            option_names = [opt[0] for opt in options]
            action_idx = select_option("请选择操作:", option_names)

            action = options[action_idx][1]

            if action == "exit":
                print("\n再见!")
                return
            elif action is None:
                # 切换用户/交易所
                break
            else:
                action()
                input("\n按回车继续...")


if __name__ == "__main__":
    main()
