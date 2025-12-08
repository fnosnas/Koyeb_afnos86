import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def validate_env_variables():
    """
    从环境变量中读取 KOYEB_ACCOUNTS，并解析为 Python 对象
    现在格式是：
    [
      {"name": "afnos86", "token": "koyeb_xxx"},
      ...
    ]
    """
    koyeb_accounts_env = os.getenv("KOYEB_ACCOUNTS")
    if not koyeb_accounts_env:
        raise ValueError("❌ KOYEB_ACCOUNTS 环境变量未设置或格式错误")

    try:
        return json.loads(koyeb_accounts_env)
    except json.JSONDecodeError:
        raise ValueError("❌ KOYEB_ACCOUNTS JSON 格式无效")


def send_tg_message(message: str):
    """
    发送 Telegram 消息
    """
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    if not bot_token or not chat_id:
        logging.warning("⚠️ TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过 Telegram 通知")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        logging.info("✅ Telegram 消息发送成功")
    except requests.RequestException as e:
        logging.error(f"❌ 发送 Telegram 消息失败: {e}")


def check_koyeb_with_token(name: str, token: str):
    """
    用 Koyeb API Token 访问一个简单的接口，判断 Token 是否有效
    这里选 /v1/apps（列出应用），只要返回 200 就表示 Token 可以用
    """
    if not token:
        return False, "Token 为空"

    url = "https://app.koyeb.com/v1/apps"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "KoyebKeepAliveScript/1.0",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return True, "Token 校验成功"
    except requests.Timeout:
        return False, "请求超时"
    except requests.RequestException as e:
        # 这里会把 401/403/其它错误都原样带出来，方便你在 TG 里看到
        return False, str(e)


def main():
    """
    主流程：
    1. 读取 KOYEB_ACCOUNTS
    2. 遍历每个账号，用 Token 调用 Koyeb API
    3. 汇总结果发到 Telegram
    """
    try:
        koyeb_accounts = validate_env_variables()
        if not koyeb_accounts:
            raise ValueError("❌ 没有找到有效的 Koyeb 账户信息")

        # 北京时间（UTC+8）
        current_time = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
        messages = []

        for account in koyeb_accounts:
            name = account.get("name") or account.get("email") or "未命名账号"
            token = account.get("token", "").strip()

            if not token:
                logging.warning(f"⚠️ 账户 {name} 没有配置 token，跳过")
                messages.append(f"⚠️ 账户: {name}\nToken 未配置，跳过")
                continue

            logging.info(f"🔍 正在检查账户: {name}")
            success, message = check_koyeb_with_token(name, token)

            if success:
                result = f"✅ 账户: {name} Token 校验成功"
            else:
                result = f"❌ 账户: {name} Token 校验失败 | 原因: {message}"

            messages.append(result)

            # 每个账号之间稍微等一下，避免请求过于频繁
            time.sleep(5)

        summary = f"⏰ 北京时间: {current_time}\n\n" + "\n".join(messages) + "\n\n✅ 任务执行完成"
        logging.info("📝 任务完成，发送 Telegram 通知")
        send_tg_message(summary)

    except Exception as e:
        error_message = f"❌ 脚本执行出错: {e}"
        logging.error(error_message)
        send_tg_message(error_message)


if __name__ == "__main__":
    main()
