#!/usr/bin/env python3
"""检查环境变量配置"""

import os
from utils import load_config, has_sensitive_in_env, get_sensitive_value


def check_env_config():
    """检查环境变量配置状态"""
    print("🔐 交易所敏感信息环境变量检查")
    print("=" * 60)
    
    config = load_config()
    users = config.get("users", {})
    
    found_any = False
    
    for user_id, user_data in users.items():
        accounts = user_data.get("accounts", {})
        for account_id, acc in accounts.items():
            # 检查私钥
            if "private_key" in acc or has_sensitive_in_env(user_id, account_id, "private_key"):
                found_any = True
                env_key = f"{user_id.upper()}_{account_id.upper()}_PRIVATE_KEY"
                simple_key = f"{account_id.upper()}_PRIVATE_KEY"
                
                env_value = os.getenv(env_key) or os.getenv(simple_key)
                config_value = acc.get("private_key", "")
                
                print(f"\n📍 {user_id}.{account_id}.private_key:")
                if env_value:
                    print(f"   ✅ 环境变量 {env_key} 已设置")
                    print(f"   🔒 值: {env_value[:10]}...{env_value[-6:]}")
                elif config_value:
                    print(f"   ⚠️  使用配置文件中的值 (建议迁移到环境变量)")
                    print(f"      设置: export {env_key}=0x...")
                else:
                    print(f"   ❌ 未设置")
                    print(f"      设置: export {env_key}=0x...")
            
            # 检查 API Key (Lighter)
            if account_id == "lighter" and ("api_key" in acc or has_sensitive_in_env(user_id, account_id, "api_key")):
                found_any = True
                env_key = f"{user_id.upper()}_{account_id.upper()}_API_KEY"
                simple_key = f"{account_id.upper()}_API_KEY"
                
                env_value = os.getenv(env_key) or os.getenv(simple_key)
                config_value = acc.get("api_key", "")
                
                print(f"\n📍 {user_id}.{account_id}.api_key:")
                if env_value:
                    print(f"   ✅ 环境变量 {env_key} 已设置")
                    print(f"   🔒 值: {env_value[:15]}...")
                elif config_value:
                    print(f"   ⚠️  使用配置文件中的值 (建议迁移到环境变量)")
                    print(f"      设置: export {env_key}=...")
                else:
                    print(f"   ❌ 未设置")
                    print(f"      设置: export {env_key}=...")
    
    if not found_any:
        print("\nℹ️  没有找到需要环境变量的配置")
    
    print("\n" + "=" * 60)
    print("💡 提示: 可将 export 命令添加到 ~/.zshrc 或 ~/.bashrc")


if __name__ == "__main__":
    check_env_config()
