#!/usr/bin/env python3
"""同步 config.json 到 EC2"""

import json
import os
import sys
import subprocess
import shlex

from utils import load_config, get_ec2_exchange_key, get_ssh_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def _get_remote_config_path() -> str:
    """从 config 读取 EC2 上的 config 路径，run.sh 需从此路径读取"""
    config = load_config()
    path = config.get("ssh", {}).get("remote_config_path")
    return path or "~/config.json"


def build_ec2_config(config: dict) -> dict:
    """从 users/accounts 构建 EC2 用的扁平化 config"""
    flat = {}
    users = config.get("users", {})
    legacy = config.get("_legacy", {})

    for user_id, user_data in users.items():
        accounts = user_data.get("accounts", {})
        for account_id, acc in accounts.items():
            ec2_key = get_ec2_exchange_key(user_id, account_id)
            if ec2_key in flat:
                continue  # 已有则跳过（legacy 可能多对一）
            cred = {}
            if "api_key" in acc:
                cred["api_key"] = acc["api_key"]
            if "api_secret" in acc:
                cred["api_secret"] = acc["api_secret"]
            if "passphrase" in acc:
                cred["passphrase"] = acc["passphrase"]
            if "wallet_address" in acc:
                cred["wallet_address"] = acc["wallet_address"]
            if "private_key" in acc:
                cred["private_key"] = acc["private_key"]
            if "key_index" in acc:
                cred["key_index"] = acc["key_index"]
            if cred:
                flat[ec2_key] = cred

    return flat


def _get_ssh_target_and_opts():
    """获取 scp/ssh 的目标和参数"""
    ssh_host, ssh_user, ssh_hostname, ssh_port, ssh_key = get_ssh_config()
    opts = []
    if ssh_key:
        opts.extend(["-i", ssh_key])
    if ssh_hostname:
        target = f"{ssh_user}@{ssh_hostname}" if ssh_user else ssh_hostname
    else:
        target = ssh_host
    return target, opts, ssh_port, ssh_hostname


def _run_scp(local_path: str, remote_path: str):
    """执行 scp 上传"""
    target, opts, ssh_port, ssh_hostname = _get_ssh_target_and_opts()
    cmd = ["scp"] + opts
    if ssh_port and ssh_hostname:
        cmd.extend(["-P", str(ssh_port)])
    cmd.extend([local_path, f"{target}:{remote_path}"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)


def _run_ssh(cmd: str) -> str:
    """在 EC2 上执行命令"""
    target, opts, ssh_port, ssh_hostname = _get_ssh_target_and_opts()
    full_cmd = ["ssh"] + opts
    if ssh_port and ssh_hostname:
        full_cmd.extend(["-p", str(ssh_port)])
    full_cmd.extend([target, cmd])
    result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout + result.stderr


def sync_config_to_ec2(aster_only: bool = False):
    """将 config 同步到 EC2"""
    if not os.path.exists(CONFIG_FILE):
        print("❌ config.json 不存在")
        sys.exit(1)

    config = load_config()
    ec2_config = build_ec2_config(config)

    if aster_only:
        aster_entries = {k: v for k, v in ec2_config.items() if "aster" in k.lower()}
        if not aster_entries:
            print("❌ 没有找到 Aster 相关配置")
            sys.exit(1)
        # 合并：先拉取 EC2 现有 config，更新 aster 条目，再推送
        remote_path = _get_remote_config_path()
        try:
            remote_content = _run_ssh(f"cat {remote_path} 2>/dev/null || echo '{{}}'")
            remote_config = json.loads(remote_content.strip() or "{}")
        except (json.JSONDecodeError, RuntimeError):
            remote_config = {}
        remote_config.update(aster_entries)
        ec2_config = remote_config
        print(f"📤 同步 Aster 配置到 EC2: {list(aster_entries.keys())}")
    else:
        print(f"📤 同步全部配置到 EC2: {len(ec2_config)} 个交易所账号")

    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(ec2_config, f, indent=2, ensure_ascii=False)
        tmp_path = f.name

    remote_path = _get_remote_config_path()
    try:
        _run_scp(tmp_path, remote_path)
        print(f"✅ 同步完成 -> {remote_path}")
    except RuntimeError as e:
        print(f"❌ 同步失败: {e}")
        sys.exit(1)
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    aster_only = "--aster-only" in sys.argv or "-a" in sys.argv
    sync_config_to_ec2(aster_only=aster_only)
