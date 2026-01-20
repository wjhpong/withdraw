#!/usr/bin/env python3
"""
交易所提现脚本 - 主入口
本地控制 → EC2执行
"""

from utils import select_option
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
        action_idx = select_option("请选择操作:", [
            "查询余额",
            "提现",
            "账户划转",
            "币安理财",
            "稳定币交易",
            "BNB工具",
            "统一保证金率",
            "管理地址簿",
            "退出"
        ])

        actions = [
            show_balance,
            do_withdraw,
            do_transfer,
            manage_earn,
            do_stablecoin_trade,
            manage_bnb_tools,
            show_pm_ratio,
            manage_addresses,
        ]

        if action_idx < len(actions):
            actions[action_idx]()
            input("\n按回车继续...")
        else:
            print("\n再见!")
            break


if __name__ == "__main__":
    main()
