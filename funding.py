#!/usr/bin/env python3
"""资金费率查询"""

from utils import run_on_ec2, select_option, SSHError


def show_funding_rate(exchange: str = None):
    """查询资金费率"""
    if not exchange:
        # 选择交易所
        exchanges = [
            ("bybit", "Bybit"),
            ("hyperliquid", "Hyperliquid"),
        ]
        display_names = [n for _, n in exchanges]
        idx = select_option("选择交易所:", display_names, allow_back=True)
        if idx == -1:
            return
        exchange = exchanges[idx][0]

    # 输入交易对
    symbol = input("\n请输入交易对 (如 BTC, ETH, 直接回车查询全部热门): ").strip().upper()

    print(f"\n正在查询 {exchange.upper()} 资金费率...")

    try:
        if symbol:
            output = run_on_ec2(f"funding_rate {exchange} {symbol}")
        else:
            output = run_on_ec2(f"funding_rate {exchange}")
        print(output)
    except SSHError as e:
        print(f"❌ 查询资金费率失败: {e}")


def show_funding_rate_menu():
    """资金费率查询菜单"""
    while True:
        action = select_option("资金费率查询:", [
            "Bybit 资金费率",
            "Hyperliquid 资金费率",
            "返回"
        ])

        if action == 0:
            show_funding_rate("bybit")
        elif action == 1:
            show_funding_rate("hyperliquid")
        else:
            break

        input("\n按回车继续...")
