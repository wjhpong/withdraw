# 环境变量迁移指南

## 概述

为了提高安全性，现在支持将敏感信息（私钥、API Key 等）存储在环境变量中，而不是明文保存在 `config.json` 文件中。

## 环境变量命名规则

```
{USER_ID}_{ACCOUNT_ID}_{KEY}
```

例如：
- `EB65_HYPERLIQUID_PRIVATE_KEY`
- `EB65_LIGHTER_API_KEY`
- `DENNIS_BINANCE_API_KEY`

或者使用简化的格式：
- `HYPERLIQUID_PRIVATE_KEY`
- `LIGHTER_API_KEY`

## 快速开始

### 1. 检查当前配置

```bash
python3 check_env.py
```

### 2. 设置环境变量

编辑你的 shell 配置文件：

```bash
# macOS (zsh)
nano ~/.zshrc

# Linux (bash)
nano ~/.bashrc
```

添加以下内容：

```bash
# Hyperliquid 私钥
export EB65_HYPERLIQUID_PRIVATE_KEY=0x...

# Lighter API Key
export EB65_LIGHTER_API_KEY=...

# 其他交易所 API Key（如果需要）
export DENNIS_BINANCE_API_KEY=...
export DENNIS_BINANCE_API_SECRET=...
```

### 3. 加载配置

```bash
source ~/.zshrc  # 或 source ~/.bashrc
```

### 4. 验证

```bash
python3 check_env.py
```

## 从 config.json 移除敏感信息

设置好环境变量后，可以从 `config.json` 中移除敏感字段：

```json
{
  "users": {
    "eb65": {
      "accounts": {
        "hyperliquid": {
          "exchange": "hyperliquid",
          "wallet_address": "0x...",
          "// private_key": "已迁移到环境变量 EB65_HYPERLIQUID_PRIVATE_KEY"
        }
      }
    }
  }
}
```

## 优先级说明

读取敏感信息的优先级：

1. **环境变量** (最高优先级)
   - `EB65_HYPERLIQUID_PRIVATE_KEY`
   - `HYPERLIQUID_PRIVATE_KEY`

2. **配置文件** (后备)
   - `config.json` 中的值

## 同步到 EC2

使用 `sync_config.py` 同步配置时，环境变量中的值会自动包含：

```bash
python3 sync_config.py
```

输出示例：
```
🔐 以下凭证来自环境变量:
   - eb65.hyperliquid.private_key
   (已包含在同步配置中)

📤 同步全部配置到 EC2: 5 个交易所账号
✅ 同步完成 -> ~/config.json
```

## 安全建议

1. **不要将 `.zshrc` 或 `.bashrc` 提交到 Git**
   ```bash
   echo ".zshrc" >> .gitignore
   echo ".bashrc" >> .gitignore
   ```

2. **使用 `.env` 文件（可选）**
   创建 `.env` 文件：
   ```bash
   EB65_HYPERLIQUID_PRIVATE_KEY=0x...
   EB65_LIGHTER_API_KEY=...
   ```
   
   加载：
   ```bash
   export $(cat .env | xargs)
   ```
   
   记得将 `.env` 加入 `.gitignore`

3. **文件权限**
   ```bash
   chmod 600 ~/.zshrc
   chmod 600 .env
   ```

## 故障排查

### 检查环境变量是否生效

```bash
echo $EB65_HYPERLIQUID_PRIVATE_KEY
```

### 检查配置读取

```bash
python3 -c "from utils import get_sensitive_value; print(get_sensitive_value('eb65', 'hyperliquid', 'private_key'))"
```

### 常见问题

**Q: 环境变量设置了但读取不到？**
- 确保已执行 `source ~/.zshrc` 或重启终端
- 检查变量名是否正确（区分大小写）

**Q: 同步到 EC2 后环境变量值丢失？**
- EC2 上也需要设置相同的环境变量
- 或者继续使用 `config.json` 作为后备
