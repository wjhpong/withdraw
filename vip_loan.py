#!/usr/bin/env python3
"""
Binance VIP 借贷功能
仅支持 dennis 和 柏青
"""

import json
from utils import run_on_ec2, select_option, load_config

# 用户配置
VIP_LOAN_CONFIG = {
    "dennis": {
        "account_id": "35693211",
        "collateral_coins": ["BTC"],  # 固定 BTC
        "ec2_key": "dennis_binance"
    },
    "baiqing": {
        "account_id": "396833626",
        "collateral_coins": ["BTC", "ETH"],  # 固定 BTC,ETH
        "ec2_key": "baiqing_binance"
    }
}

# 常用借贷币种
LOAN_COINS = ["USDT", "USDC", "BTC", "ETH"]


def get_vip_loan_config(user_id: str) -> dict:
    """获取用户 VIP 借贷配置"""
    return VIP_LOAN_CONFIG.get(user_id)


def show_vip_loan_orders(user_id: str, ec2_exchange: str):
    """查询 VIP 借贷订单"""
    config = get_vip_loan_config(user_id)
    if not config:
        print(f"\n用户 {user_id} 不支持 VIP 借贷功能")
        return

    print(f"\n正在查询 VIP 借贷订单...")

    try:
        output = run_on_ec2(f"vip_loan_orders {ec2_exchange}")
        result = json.loads(output.strip())

        if isinstance(result, dict) and "error" in result:
            print(f"查询失败: {result['error']}")
            return

        rows = result.get("rows", [])
        if not rows:
            print("\n当前没有进行中的借贷订单")
            return

        # 查询各币种的实时利率
        loan_coins = list(set(order.get("loanCoin", "") for order in rows))
        rate_map = {}  # coin -> yearly rate
        try:
            coins_str = ",".join(loan_coins)
            rate_output = run_on_ec2(f"vip_loan_rates {ec2_exchange} {coins_str}")
            rate_data = json.loads(rate_output.strip())
            if isinstance(rate_data, list):
                for item in rate_data:
                    coin = item.get("asset", "")
                    yearly = float(item.get("flexibleYearlyInterestRate", 0))
                    rate_map[coin] = yearly
        except:
            pass  # 利率查询失败不影响订单显示

        print("\n" + "=" * 100)
        print(f"{'订单ID':<15} {'借贷币种':<10} {'总负债':<18} {'年利率':<14} {'LTV':<10} {'到期时间'}")
        print("-" * 100)

        for order in rows:
            order_id = order.get("orderId", "")
            loan_coin = order.get("loanCoin", "")
            total_debt = float(order.get("totalDebt", 0))

            # 优先使用实时查询的利率，否则用订单中的利率
            if loan_coin in rate_map:
                loan_rate_str = f"{rate_map[loan_coin] * 100:.2f}%"
            else:
                loan_rate_raw = order.get("loanRate", 0)
                try:
                    loan_rate = float(loan_rate_raw) * 100
                    loan_rate_str = f"{loan_rate:.2f}%"
                except (ValueError, TypeError):
                    loan_rate_str = str(loan_rate_raw)

            current_ltv = float(order.get("currentLTV", 0)) * 100
            expiration = order.get("expirationTime", "")

            # 格式化到期时间
            if expiration and expiration != "0":
                from datetime import datetime
                try:
                    exp_ts = int(expiration) / 1000
                    exp_str = datetime.fromtimestamp(exp_ts).strftime("%Y-%m-%d")
                except:
                    exp_str = str(expiration)
            else:
                exp_str = "浮动"

            print(f"{order_id:<15} {loan_coin:<10} {total_debt:>15,.4f} {loan_rate_str:>12} {current_ltv:>8.2f}% {exp_str}")

            # 显示抵押品信息
            collateral_coins = order.get("collateralCoin", "").split(",")
            print(f"  抵押品: {', '.join(collateral_coins)}")
            print(f"  剩余利息: {float(order.get('residualInterest', 0)):,.6f} {loan_coin}")
            print()

        print("=" * 100)

    except Exception as e:
        print(f"查询失败: {e}")


def do_vip_loan_borrow(user_id: str, ec2_exchange: str):
    """VIP 借贷 - 借款（支持多币种）"""
    config = get_vip_loan_config(user_id)
    if not config:
        print(f"\n用户 {user_id} 不支持 VIP 借贷功能")
        return

    account_id = config["account_id"]
    collateral_options = config["collateral_coins"]

    print(f"\n===== VIP 借贷 - 借款 =====")
    print(f"账户 ID: {account_id}")

    # 收集借贷请求
    borrow_requests = []

    print("\n请输入借贷信息，格式: 币种 金额")
    print("例如: USDT 20000")
    print("可以输入多行，每行一个币种，输入空行结束\n")

    while True:
        line = input("借贷 (币种 金额): ").strip()
        if not line:
            break

        # 解析输入：支持空格、逗号、冒号分隔
        import re
        parts = re.split(r'[\s,，:：]+', line)
        if len(parts) < 2:
            print("  格式错误，请输入: 币种 金额")
            continue

        coin = parts[0].upper()
        try:
            amount = float(parts[1])
            if amount <= 0:
                print("  金额必须大于 0")
                continue
            borrow_requests.append({"coin": coin, "amount": amount})
            print(f"  已添加: {coin} {amount:,.4f}")
        except ValueError:
            print("  无效的金额")
            continue

    if not borrow_requests:
        print("没有添加任何借款")
        return

    # 抵押币种（固定，不用选择）
    collateral_coin = ",".join(collateral_options)

    # 确认所有借款
    print(f"\n===== 确认借款信息 =====")
    print(f"账户 ID: {account_id}")
    print(f"抵押币种: {collateral_coin}")
    print(f"利率类型: 浮动")
    print(f"\n借款明细:")
    for req in borrow_requests:
        print(f"  - {req['coin']}: {req['amount']:,.4f}")

    confirm = input("\n确认借款? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    # 逐个执行借款
    print("\n正在提交借款请求...")
    success_count = 0
    for req in borrow_requests:
        loan_coin = req["coin"]
        loan_amount = req["amount"]

        try:
            cmd = f"vip_loan_borrow {ec2_exchange} {account_id} {loan_coin} {loan_amount} {collateral_coin} true"
            output = run_on_ec2(cmd)
            result = json.loads(output.strip())

            if isinstance(result, dict) and "error" in result:
                print(f"  {loan_coin} 借款失败: {result['error']}")
            elif isinstance(result, dict) and result.get("code"):
                print(f"  {loan_coin} 借款失败: {result.get('msg', '未知错误')}")
            else:
                print(f"  {loan_coin} 借款成功! 订单 ID: {result.get('orderId', 'N/A')}, 金额: {result.get('loanAmount', loan_amount)}")
                success_count += 1

        except Exception as e:
            print(f"  {loan_coin} 借款失败: {e}")

    print(f"\n借款完成: {success_count}/{len(borrow_requests)} 笔成功")


def do_vip_loan_repay(user_id: str, ec2_exchange: str):
    """VIP 借贷 - 还款"""
    config = get_vip_loan_config(user_id)
    if not config:
        print(f"\n用户 {user_id} 不支持 VIP 借贷功能")
        return

    print(f"\n正在查询进行中的借贷订单...")

    try:
        output = run_on_ec2(f"vip_loan_orders {ec2_exchange}")
        result = json.loads(output.strip())

        if isinstance(result, dict) and "error" in result:
            print(f"查询失败: {result['error']}")
            return

        rows = result.get("rows", [])
        if not rows:
            print("\n当前没有需要还款的订单")
            return

        # 显示订单列表供选择
        print("\n===== 选择要还款的订单 =====")
        order_options = []
        for order in rows:
            order_id = order.get("orderId", "")
            loan_coin = order.get("loanCoin", "")
            total_debt = float(order.get("totalDebt", 0))
            option_text = f"订单 {order_id}: {total_debt:,.4f} {loan_coin}"
            order_options.append((option_text, order))

        order_idx = select_option("选择订单:", [opt[0] for opt in order_options] + ["返回"])
        if order_idx == len(order_options):
            return

        selected_order = order_options[order_idx][1]
        order_id = selected_order.get("orderId")
        loan_coin = selected_order.get("loanCoin")
        total_debt = float(selected_order.get("totalDebt", 0))
        residual_interest = float(selected_order.get("residualInterest", 0))

        # 查询可用余额（从文本输出解析）
        available_balance = 0.0
        try:
            balance_output = run_on_ec2(f"balance {ec2_exchange}")
            # 解析文本格式的余额输出
            # 格式: "USDT		31614.98173536"
            import re
            for line in balance_output.split('\n'):
                # 匹配 "币种\t\t数量" 格式
                match = re.match(rf'^{loan_coin}\s+(\d+\.?\d*)', line)
                if match:
                    available_balance = float(match.group(1))
                    break
        except:
            pass  # 查询失败不影响还款流程

        print(f"\n===== 订单详情 =====")
        print(f"订单 ID: {order_id}")
        print(f"借贷币种: {loan_coin}")
        print(f"总负债: {total_debt:,.6f} {loan_coin}")
        print(f"剩余利息: {residual_interest:,.6f} {loan_coin}")
        print(f"可用余额: {available_balance:,.6f} {loan_coin}")

        # 选择还款方式
        repay_type_idx = select_option("选择还款方式:", [
            f"全部还款 ({total_debt:,.4f} {loan_coin})",
            "自定义金额",
            "返回"
        ])

        if repay_type_idx == 2:  # 返回
            return
        elif repay_type_idx == 0:
            repay_amount = total_debt
        else:
            amount_str = input(f"\n请输入还款金额 ({loan_coin}, 可用 {available_balance:,.4f}): ").strip()
            try:
                repay_amount = float(amount_str)
                if repay_amount <= 0:
                    print("金额必须大于 0")
                    return
            except ValueError:
                print("无效的金额")
                return

        # 确认
        print(f"\n===== 确认还款信息 =====")
        print(f"订单 ID: {order_id}")
        print(f"还款金额: {repay_amount:,.6f} {loan_coin}")

        confirm = input("\n确认还款? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

        # 执行还款
        print("\n正在提交还款请求...")
        cmd = f"vip_loan_repay {ec2_exchange} {order_id} {repay_amount}"
        output = run_on_ec2(cmd)
        result = json.loads(output.strip())

        if isinstance(result, dict) and "error" in result:
            print(f"还款失败: {result['error']}")
        elif isinstance(result, dict) and result.get("code"):
            print(f"还款失败: {result.get('msg', '未知错误')}")
        else:
            print(f"\n还款成功!")
            print(f"还款金额: {result.get('repayAmount', repay_amount)} {loan_coin}")
            print(f"剩余本金: {result.get('remainingPrincipal', 'N/A')}")
            print(f"剩余利息: {result.get('remainingInterest', 'N/A')}")
            print(f"当前 LTV: {result.get('currentLTV', 'N/A')}")
            print(f"还款状态: {result.get('repayStatus', 'N/A')}")

    except Exception as e:
        print(f"还款失败: {e}")


def manage_vip_loan(user_id: str, ec2_exchange: str):
    """VIP 借贷管理菜单"""
    config = get_vip_loan_config(user_id)
    if not config:
        print(f"\n用户 {user_id} 不支持 VIP 借贷功能")
        return

    while True:
        print(f"\n===== VIP 借贷管理 =====")

        options = [
            ("查询借贷订单", lambda: show_vip_loan_orders(user_id, ec2_exchange)),
            ("借款", lambda: do_vip_loan_borrow(user_id, ec2_exchange)),
            ("还款", lambda: do_vip_loan_repay(user_id, ec2_exchange)),
            ("返回", None)
        ]

        option_names = [opt[0] for opt in options]
        action_idx = select_option("请选择操作:", option_names)

        action = options[action_idx][1]

        if action is None:
            break
        else:
            action()
            input("\n按回车继续...")
