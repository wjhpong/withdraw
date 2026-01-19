#!/usr/bin/env python3
"""通用工具函数和配置"""

import subprocess
import json
import os

# 配置
EC2_HOST = "tixian"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDRESSES_FILE = os.path.join(BASE_DIR, "addresses.json")

# 网络列表
EVM_NETWORKS = ["ERC20", "BSC", "ARBITRUM", "OPTIMISM", "MATIC", "BASE", "LINEA", "ZKSYNCERA", "SCROLL", "AVAXC", "FTM", "MANTLE", "BLAST", "MANTA", "CELO"]
TRC_NETWORKS = ["TRC20"]
SOL_NETWORKS = ["SOL"]
SUI_NETWORKS = ["SUI"]
APT_NETWORKS = ["APT"]


def run_on_ec2(cmd: str) -> str:
    """在 EC2 上执行命令并返回结果"""
    full_cmd = f'ssh {EC2_HOST} "./run.sh {cmd}"'
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def select_option(prompt: str, options: list, allow_back: bool = False) -> int:
    """显示选项并让用户选择，返回 -1 表示返回"""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    if allow_back:
        print(f"  0. ← 返回")

    while True:
        try:
            choice = input("\n请输入数字选择: ").strip()
            idx = int(choice)
            if allow_back and idx == 0:
                return -1
            idx -= 1
            if 0 <= idx < len(options):
                return idx
            if allow_back:
                print(f"请输入 0-{len(options)} 之间的数字")
            else:
                print(f"请输入 1-{len(options)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")


def input_amount(prompt: str = "请输入数量: "):
    """输入数量的通用函数，输入 0 或空返回 None 表示取消"""
    while True:
        try:
            amount_str = input(f"\n{prompt} (输入 0 返回): ").strip()
            if not amount_str or amount_str == "0":
                return None
            amount = float(amount_str)
            if amount <= 0:
                print("数量必须大于0")
                continue
            return amount
        except ValueError:
            print("请输入有效的数字")


def get_networks_for_type(addr_type: str) -> list:
    """根据地址类型返回可用网络列表"""
    networks_map = {
        "evm": EVM_NETWORKS,
        "trc": TRC_NETWORKS,
        "sol": SOL_NETWORKS,
        "sui": SUI_NETWORKS,
        "apt": APT_NETWORKS,
    }
    return networks_map.get(addr_type, EVM_NETWORKS + TRC_NETWORKS + SOL_NETWORKS + SUI_NETWORKS + APT_NETWORKS + ["其他"])


def detect_address_type(address: str) -> str:
    """自动检测地址类型"""
    if address.startswith("0x"):
        addr_len = len(address) - 2
        if addr_len == 40:
            return "evm"
        elif addr_len == 64:
            return "sui_apt"
    elif address.startswith("T") and len(address) == 34:
        return "trc"
    elif 32 <= len(address) <= 44:
        return "sol"
    return "other"
