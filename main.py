#!/usr/bin/env python3
"""
交易所提现脚本 - 主入口
本地控制 → EC2执行
"""

from utils import select_option, select_exchange, get_exchange_base, get_exchange_display_name
from balance import show_balance, show_pm_ratio
from withdraw_ops import do_withdraw
from transfer import do_transfer
from earn import manage_earn
from trade import do_stablecoin_trade
from addresses import manage_addresses
from bnb_tools import manage_bnb_tools


def main():
    print("=" * 50)
    print("    交易所提现脚本 (本地控制 → EC2执行)")
    print("=" * 50)

    while True:
        # 先选择交易所
        exchange = select_exchange(allow_back=False)
        if not exchange:
            print("\n再见!")
            break
        
        exchange_base = get_exchange_base(exchange)
        display_name = get_exchange_display_name(exchange)
        
        # 根据交易所显示对应功能菜单
        while True:
            print(f"\n{'=' * 50}")
            print(f"    当前交易所: {display_name}")
            print("=" * 50)
            
            # 根据交易所类型构建菜单
            if exchange_base == "binance":
                options = [
                    ("查询余额", lambda: show_balance(exchange)),
                    ("提现", lambda: do_withdraw(exchange)),
                    ("账户划转", lambda: do_transfer(exchange)),
                    ("理财管理", lambda: manage_earn(exchange)),
                    ("稳定币交易", lambda: do_stablecoin_trade(exchange)),
                    ("BNB工具", lambda: manage_bnb_tools(exchange)),
                    ("统一保证金率", lambda: show_pm_ratio(exchange)),
                    ("管理地址簿", manage_addresses),
                    ("切换交易所", None),
                    ("退出", "exit"),
                ]
            elif exchange_base == "gate":
                options = [
                    ("查询余额", lambda: show_balance(exchange)),
                    ("提现", lambda: do_withdraw(exchange)),
                    ("账户划转", lambda: do_transfer(exchange)),
                    ("管理地址簿", manage_addresses),
                    ("切换交易所", None),
                    ("退出", "exit"),
                ]
            elif exchange_base == "bybit":
                options = [
                    ("查询余额", lambda: show_balance(exchange)),
                    ("提现", lambda: do_withdraw(exchange)),
                    ("账户划转", lambda: do_transfer(exchange)),
                    ("管理地址簿", manage_addresses),
                    ("切换交易所", None),
                    ("退出", "exit"),
                ]
            else:
                options = [
                    ("查询余额", lambda: show_balance(exchange)),
                    ("提现", lambda: do_withdraw(exchange)),
                    ("管理地址簿", manage_addresses),
                    ("切换交易所", None),
                    ("退出", "exit"),
                ]
            
            option_names = [opt[0] for opt in options]
            action_idx = select_option("请选择操作:", option_names)
            
            action = options[action_idx][1]
            
            if action == "exit":
                print("\n再见!")
                return
            elif action is None:
                # 切换交易所
                break
            else:
                action()
                input("\n按回车继续...")


if __name__ == "__main__":
    main()
