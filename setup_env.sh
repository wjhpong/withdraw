#!/bin/bash
# 设置交易所敏感信息环境变量
# 使用方式: source setup_env.sh

echo "🔐 设置交易所敏感信息环境变量"
echo "=============================="
echo ""

# 检查是否已经设置
if [ -n "$EB65_HYPERLIQUID_PRIVATE_KEY" ]; then
    echo "✅ EB65_HYPERLIQUID_PRIVATE_KEY 已设置"
else
    echo "⚠️  EB65_HYPERLIQUID_PRIVATE_KEY 未设置"
    echo "   请运行: export EB65_HYPERLIQUID_PRIVATE_KEY=0x..."
fi

if [ -n "$EB65_LIGHTER_API_KEY" ]; then
    echo "✅ EB65_LIGHTER_API_KEY 已设置"
else
    echo "⚠️  EB65_LIGHTER_API_KEY 未设置"
    echo "   请运行: export EB65_LIGHTER_API_KEY=..."
fi

echo ""
echo "📋 环境变量命名规则:"
echo "   {USER_ID}_{ACCOUNT_ID}_{KEY}"
echo ""
echo "示例:"
echo "   export EB65_HYPERLIQUID_PRIVATE_KEY=0x..."
echo "   export EB65_LIGHTER_API_KEY=..."
echo "   export DENNIS_BINANCE_API_KEY=..."
echo ""
echo "💡 提示: 可将上述 export 命令添加到 ~/.zshrc 或 ~/.bashrc"
