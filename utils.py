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

# 网络列表
EVM_NETWORKS = ["ERC20", "BSC", "ARBITRUM", "OPTIMISM", "MATIC", "LINEA", "AVAXC", "MANTLE", "CELO", "PLASMA", "TON"]
TRC_NETWORKS = ["TRC20"]
SOL_NETWORKS = ["SOL"]
SUI_NETWORKS = ["SUI"]
APT_NETWORKS = ["APT"]


class SSHError(Exception):
    """SSH 连接或执行错误"""
    pass


class ConfigError(Exception):
    """配置文件错误"""
    pass


# ===================== 配置管理 =====================

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "ssh": {}, "_legacy": {}}


def save_config(config: dict):
    """保存配置文件"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_users():
    """获取所有用户列表 [(user_id, name), ...]"""
    config = load_config()
    users = config.get("users", {})
    return [(uid, info.get("name", uid)) for uid, info in users.items()]


def get_user_accounts(user_id: str):
    """获取用户的所有交易所账号 [(account_id, exchange_name), ...]"""
    config = load_config()
    user = config.get("users", {}).get(user_id, {})
    accounts = user.get("accounts", {})
    return [(acc_id, acc.get("exchange", acc_id).upper()) for acc_id, acc in accounts.items()]


def get_ec2_exchange_key(user_id: str, account_id: str) -> str:
    """获取 EC2 使用的交易所 key (如 binance, binance2, binance3)

    EC2 上的脚本使用 binance, binance2 等 key 区分不同账号
    这里通过 _legacy 映射找到对应的 key
    """
    config = load_config()
    legacy = config.get("_legacy", {})

    # 反向查找：找到映射到该用户的所有 legacy key
    user_legacy_keys = [k for k, v in legacy.items() if v == user_id]

    # 获取账户的交易所类型
    user_accounts = config.get("users", {}).get(user_id, {}).get("accounts", {})
    account = user_accounts.get(account_id, {})
    exchange_type = account.get("exchange", account_id)

    # 找到匹配交易所类型的 legacy key
    for key in user_legacy_keys:
        # 匹配: key == exchange_type, key 以 exchange_type 开头, 或 key 包含 _exchange_type
        if key == exchange_type or key.startswith(exchange_type) or f"_{exchange_type}" in key:
            return key

    # 如果没找到，返回交易所类型作为默认值
    return exchange_type


# ===================== SSH 执行 =====================

def get_ssh_config():
    """从配置文件读取SSH连接信息"""
    ssh_host = DEFAULT_EC2_HOST
    ssh_user = None
    ssh_hostname = None
    ssh_port = None
    ssh_key = None

    config = load_config()
    ssh_config = config.get("ssh", {})
    ssh_host = ssh_config.get("host", DEFAULT_EC2_HOST)
    ssh_user = ssh_config.get("user")
    ssh_hostname = ssh_config.get("hostname")
    ssh_port = ssh_config.get("port")
    ssh_key = ssh_config.get("key")

    return ssh_host, ssh_user, ssh_hostname, ssh_port, ssh_key


def get_control_socket_path():
    """获取 SSH ControlMaster socket 路径"""
    import os
    # 使用 /tmp 目录，路径尽量短以避免 Unix socket 路径过长问题
    return "/tmp/ec2_ctl"


def ensure_ssh_connection():
    """确保 SSH ControlMaster 连接已建立"""
    import os

    ssh_host, ssh_user, ssh_hostname, ssh_port, ssh_key = get_ssh_config()
    socket_path = get_control_socket_path()

    # 构建 SSH 目标
    if ssh_hostname:
        if ssh_user:
            ssh_target = f"{ssh_user}@{ssh_hostname}"
        else:
            ssh_target = ssh_hostname
    else:
        ssh_target = ssh_host

    # 检查连接是否存在
    check_cmd = ["ssh", "-O", "check", "-o", f"ControlPath={socket_path}", ssh_target]
    result = subprocess.run(check_cmd, capture_output=True, text=True)

    if result.returncode == 0:
        # 连接已存在
        return True

    # 建立新的 ControlMaster 连接
    print("正在建立 EC2 连接...")
    ssh_cmd = ["ssh", "-fNM",  # -f 后台, -N 不执行命令, -M 主连接
               "-o", f"ControlPath={socket_path}",
               "-o", "ControlPersist=600",  # 保持 10 分钟
               "-o", "ServerAliveInterval=30"]

    if ssh_hostname:
        if ssh_port:
            ssh_cmd.extend(["-p", str(ssh_port)])
        if ssh_key:
            ssh_cmd.extend(["-i", ssh_key])
        ssh_cmd.append(ssh_target)
    else:
        ssh_cmd.append(ssh_target)

    result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"建立连接失败: {result.stderr}")
        return False

    print("EC2 连接已建立 ✓")
    return True


def run_on_ec2(cmd: str) -> str:
    """在 EC2 上执行命令并返回结果（使用连接复用）"""
    ssh_host, ssh_user, ssh_hostname, ssh_port, ssh_key = get_ssh_config()
    socket_path = get_control_socket_path()

    # 确保连接存在
    ensure_ssh_connection()

    # 构建SSH命令（使用 ControlPath 复用连接）
    ssh_cmd_parts = ["ssh", "-o", f"ControlPath={socket_path}"]

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
    cmd_parts = cmd.split()
    remote_cmd_parts = ["./run.sh"] + cmd_parts
    remote_cmd = "bash -c " + shlex.quote(" ".join(remote_cmd_parts))
    ssh_cmd_parts.append(remote_cmd)

    try:
        result = subprocess.run(ssh_cmd_parts, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 and "Permission denied" in result.stderr:
            raise SSHError(f"SSH 连接被拒绝，请检查密钥配置")
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        raise SSHError("SSH 命令执行超时 (120秒)")
    except FileNotFoundError:
        raise SSHError("找不到 ssh 命令，请确保已安装 OpenSSH")


# ===================== 用户交互 =====================

def select_option(prompt: str, options: list, allow_back: bool = False) -> int:
    """显示选项并让用户选择，返回 -1 表示返回"""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    if allow_back:
        print(f"  0. <- 返回")

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


def select_user(allow_back: bool = True):
    """选择用户，返回 user_id 或 None"""
    users = get_users()
    if not users:
        print("\n没有配置任何用户")
        return None

    user_names = [name for _, name in users]
    idx = select_option("请选择用户:", user_names, allow_back=allow_back)
    if idx == -1:
        return None
    return users[idx][0]


def select_account(user_id: str, allow_back: bool = True, show_combined: bool = True):
    """选择用户的交易所账号，返回 account_id 或 None

    返回值:
        account_id: 正常选择的账号ID
        None: 返回上一级
        "__combined__": 选择了综合收益选项
    """
    accounts = get_user_accounts(user_id)
    if not accounts:
        print(f"\n该用户没有配置任何交易所账号")
        return None

    if len(accounts) == 1 and not show_combined:
        # 只有一个账号且不显示综合选项，直接返回
        return accounts[0][0]

    account_names = [name for _, name in accounts]

    # 如果有多个账号，添加综合收益选项
    if show_combined and len(accounts) > 1:
        account_names.append("== 综合收益 ==")

    idx = select_option("请选择交易所:", account_names, allow_back=allow_back)
    if idx == -1:
        return None

    # 检查是否选择了综合收益
    if show_combined and len(accounts) > 1 and idx == len(accounts):
        return "__combined__"

    return accounts[idx][0]


def select_user_and_account(allow_back: bool = True):
    """选择用户和账户，返回 (user_id, account_id, ec2_exchange) 或 (None, None, None)"""
    user_id = select_user(allow_back=allow_back)
    if not user_id:
        return None, None, None

    account_id = select_account(user_id, allow_back=allow_back)
    if not account_id:
        return None, None, None

    ec2_exchange = get_ec2_exchange_key(user_id, account_id)
    return user_id, account_id, ec2_exchange


# ===================== 工具函数 =====================

def get_exchange_base(exchange: str) -> str:
    """获取交易所基础类型 (binance/binance2 都返回 binance)"""
    if exchange.startswith("binance") or "_binance" in exchange:
        return "binance"
    if exchange.startswith("gate") or "_gate" in exchange:
        return "gate"
    if exchange.startswith("bitget") or "_bitget" in exchange:
        return "bitget"
    if exchange.startswith("hyperliquid") or "_hyperliquid" in exchange:
        return "hyperliquid"
    if exchange.startswith("lighter") or "_lighter" in exchange:
        return "lighter"
    if exchange.startswith("aster") or "_aster" in exchange:
        return "aster"
    if exchange.startswith("bybit") or "_bybit" in exchange:
        return "bybit"
    return exchange


def get_exchange_display_name(exchange: str, user_name: str = None) -> str:
    """获取交易所的显示名称"""
    base = get_exchange_base(exchange).upper()
    if user_name:
        return f"{base} - {user_name}"
    return base


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


# ===================== 兼容旧接口 (保留给其他模块使用) =====================

# 旧的交易所列表 (为了兼容)
EXCHANGES = [
    ("binance", "BINANCE - Dennis"),
    ("binance2", "BINANCE - Vanie"),
    ("binance3", "BINANCE - 柏青"),
    ("bybit", "BYBIT"),
    ("gate", "GATE.IO"),
    ("bitget", "BITGET"),
    ("hyperliquid", "HYPERLIQUID"),
]


def select_exchange(allow_back: bool = True, binance_only: bool = False, bybit_only: bool = False):
    """选择交易所 (旧接口，兼容用)"""
    if binance_only:
        options = [(k, n) for k, n in EXCHANGES if k.startswith("binance")]
    elif bybit_only:
        options = [(k, n) for k, n in EXCHANGES if k.startswith("bybit")]
    else:
        options = EXCHANGES

    if len(options) == 1:
        return options[0][0]

    display_names = [n for _, n in options]
    idx = select_option("请选择交易所:", display_names, allow_back=allow_back)
    if idx == -1:
        return None
    return options[idx][0]
