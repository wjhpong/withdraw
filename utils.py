#!/usr/bin/env python3
"""通用工具函数和配置"""

import subprocess
import json
import os
import shlex

# 配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDRESSES_FILE = os.path.join(BASE_DIR, "addresses.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# 默认SSH配置
DEFAULT_EC2_HOST = "tixian"

# 交易所列表 (支持多账号)
EXCHANGES = [
    ("binance", "BINANCE - Dennis"),
    ("binance2", "BINANCE - Vanie"),
    ("bybit", "BYBIT"),
]

# 网络列表
EVM_NETWORKS = ["ERC20", "BSC", "ARBITRUM", "OPTIMISM", "MATIC", "BASE", "LINEA", "ZKSYNCERA", "SCROLL", "AVAXC", "FTM", "MANTLE", "BLAST", "MANTA", "CELO"]
TRC_NETWORKS = ["TRC20"]
SOL_NETWORKS = ["SOL"]
SUI_NETWORKS = ["SUI"]
APT_NETWORKS = ["APT"]


def get_ssh_config():
    """从配置文件读取SSH连接信息"""
    ssh_host = DEFAULT_EC2_HOST
    ssh_user = None
    ssh_hostname = None
    ssh_port = None
    ssh_key = None
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                ssh_config = config.get("ssh", {})
                ssh_host = ssh_config.get("host", DEFAULT_EC2_HOST)
                ssh_user = ssh_config.get("user")
                ssh_hostname = ssh_config.get("hostname")
                ssh_port = ssh_config.get("port")
                ssh_key = ssh_config.get("key")
        except (json.JSONDecodeError, KeyError):
            pass
    
    return ssh_host, ssh_user, ssh_hostname, ssh_port, ssh_key


def run_on_ec2(cmd: str) -> str:
    """在 EC2 上执行命令并返回结果"""
    ssh_host, ssh_user, ssh_hostname, ssh_port, ssh_key = get_ssh_config()
    
    # 构建SSH命令
    ssh_cmd_parts = ["ssh"]
    
    # 如果配置了详细的SSH信息，使用完整SSH命令
    if ssh_hostname:
        if ssh_user:
            ssh_target = f"{ssh_user}@{ssh_hostname}"
        else:
            ssh_target = ssh_hostname
        
        if ssh_port:
            ssh_cmd_parts.extend(["-p", str(ssh_port)])
        
        if ssh_key:
            ssh_cmd_parts.extend(["-i", ssh_key])
        
        ssh_cmd_parts.append(ssh_target)
    else:
        # 使用SSH config中的别名
        ssh_cmd_parts.append(ssh_host)
    
    # 执行远程命令
    # 将命令拆分成多个参数，run.sh需要接收多个独立参数
    cmd_parts = cmd.split()
    remote_cmd_parts = ["./run.sh"] + cmd_parts
    # 使用bash -c来执行，确保参数正确传递
    remote_cmd = "bash -c " + shlex.quote(" ".join(remote_cmd_parts))
    ssh_cmd_parts.append(remote_cmd)
    
    # 使用列表形式执行，避免shell转义问题
    result = subprocess.run(ssh_cmd_parts, capture_output=True, text=True)
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


def get_networks_for_coin(coin: str, addr_type: str) -> list:
    """根据币种和地址类型返回可用网络列表"""
    # 使用默认网络列表
    return get_networks_for_type(addr_type)


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


def select_exchange(allow_back: bool = True, binance_only: bool = False, bybit_only: bool = False):
    """选择交易所，返回 exchange_key 或 None"""
    if binance_only:
        options = [(k, n) for k, n in EXCHANGES if k.startswith("binance")]
    elif bybit_only:
        options = [(k, n) for k, n in EXCHANGES if k == "bybit"]
    else:
        options = EXCHANGES
    
    if len(options) == 1:
        return options[0][0]
    
    display_names = [n for _, n in options]
    idx = select_option("请选择交易所:", display_names, allow_back=allow_back)
    if idx == -1:
        return None
    return options[idx][0]


def get_exchange_base(exchange: str) -> str:
    """获取交易所基础类型 (binance/binance2 都返回 binance)"""
    if exchange.startswith("binance"):
        return "binance"
    return exchange


def get_exchange_display_name(exchange: str) -> str:
    """获取交易所的显示名称"""
    for key, name in EXCHANGES:
        if key == exchange:
            return name
    return exchange.upper()
