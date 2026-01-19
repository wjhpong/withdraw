#!/usr/bin/env python3
"""余额查询"""

from utils import run_on_ec2, select_option


def show_balance():
    """查询余额"""
    ex_idx = select_option("请选择交易所:", ["BINANCE", "BYBIT"], allow_back=True)
    if ex_idx == -1:
        return
    
    exchanges = ["binance", "bybit"]
    print(f"\n正在查询 {exchanges[ex_idx].upper()} 余额...")
    output = run_on_ec2(f"balance {exchanges[ex_idx]}")
    print(output)


def get_coin_balance(exchange: str, coin: str) -> str:
    """查询指定币种余额"""
    output = run_on_ec2(f"balance {exchange}")
    coin_upper = coin.upper()
    for line in output.split('\n'):
        line_upper = line.upper()
        if line_upper.startswith(coin_upper + '\t') or line_upper.startswith(coin_upper + ' '):
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
    return "0"
