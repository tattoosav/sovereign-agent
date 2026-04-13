"""
Telegram bot integration for Sovereign Agent.

Run: python -m src.integrations.telegram_bot

Requires:
  TELEGRAM_BOT_TOKEN  — from @BotFather
  SOVEREIGN_BASE_URL  — agent API URL (default: http://localhost:8000)
  SOVEREIGN_API_KEY   — API key for the agent
"""

import asyncio
import html
import logging
import os
import sys
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Telegram Bot API base URL
TG_API = "https://api.telegram.org/bot{token}/{method}"

# Limits
TG_MSG_LIMIT = 4096  # Telegram max message length


class TelegramBot:
    """Minimal Telegram bot that forwards messages to the Sovereign Agent API."""

    def __init__(
        self,
        bot_token: str,
        agent_url: str = "http://localhost:8000",
        agent_api_key: str = "",
        allowed_users: list[int] | None = None,
    ):
        self.bot_token = bot_token
        self.agent_url = agent_url.rstrip("/")
        self.agent_api_key = agent_api_key
        self.allowed_users = allowed_users  # None = allow all
        self._client = httpx.AsyncClient(timeout=600)
        self._sessions: dict[int, str] = {}  # chat_id -> agent session_id
        self._offset = 0

    # ─────────────────────────── Telegram helpers ──────────────────────────

    async def _tg(self, method: str, **kwargs) -> dict:
        """Call a Telegram Bot API method."""
        url = TG_API.format(token=self.bot_token, method=method)
        resp = await self._client.post(url, json=kwargs)
        data = resp.json()
        if not data.get("ok"):
            logger.error(f"Telegram API error: {data}")
        return data

    async def send(self, chat_id: int, text: str, parse_mode: str = "HTML") -> dict:
        """Send a message, splitting if it exceeds Telegram's limit."""
        chunks = self._split_message(text)
        result = {}
        for chunk in chunks:
            result = await self._tg("sendMessage", chat_id=chat_id, text=chunk, parse_mode=parse_mode)
        return result

    async def send_typing(self, chat_id: int) -> None:
        """Show typing indicator."""
        await self._tg("sendChatAction", chat_id=chat_id, action="typing")

    async def edit_message(self, chat_id: int, message_id: int, text: str) -> dict:
        """Edit an existing message."""
        chunks = self._split_message(text)
        # Edit with last chunk (most relevant for streaming)
        return await self._tg(
            "editMessageText", chat_id=chat_id, message_id=message_id,
            text=chunks[-1], parse_mode="HTML"
        )

    @staticmethod
    def _split_message(text: str) -> list[str]:
        """Split a message into chunks that fit Telegram's limit."""
        if len(text) <= TG_MSG_LIMIT:
            return [text]
        chunks = []
        while text:
            if len(text) <= TG_MSG_LIMIT:
                chunks.append(text)
                break
            # Try to split at a newline
            split_at = text.rfind('\n', 0, TG_MSG_LIMIT)
            if split_at < TG_MSG_LIMIT // 2:
                split_at = TG_MSG_LIMIT
            chunks.append(text[:split_at])
            text = text[split_at:]
        return chunks

    # ─────────────────────────── Agent API calls ───────────────────────────

    def _headers(self) -> dict:
        """Auth headers for agent API."""
        h = {"Content-Type": "application/json"}
        if self.agent_api_key:
            h["Authorization"] = f"Bearer {self.agent_api_key}"
        return h

    async def _get_session(self, chat_id: int) -> str:
        """Get or create an agent session for a Telegram chat."""
        if chat_id in self._sessions:
            return self._sessions[chat_id]

        resp = await self._client.post(
            f"{self.agent_url}/session/new", headers=self._headers()
        )
        data = resp.json()
        session_id = data.get("session_id", "")
        self._sessions[chat_id] = session_id
        return session_id

    async def _chat(self, chat_id: int, message: str) -> str:
        """Send a message to the agent and return the response."""
        session_id = await self._get_session(chat_id)

        resp = await self._client.post(
            f"{self.agent_url}/chat",
            headers=self._headers(),
            json={"message": message, "session_id": session_id},
            timeout=600,
        )

        if resp.status_code == 429:
            return "Rate limit reached. Please wait a moment before trying again."
        if resp.status_code == 401:
            return "Authentication error. Check the bot's API key configuration."

        data = resp.json()

        if data.get("status") == "error":
            return f"Error: {data.get('error', 'Unknown error')}"

        return data.get("response", "No response")

    async def _reset_session(self, chat_id: int) -> str:
        """Reset the agent session for a chat."""
        if chat_id in self._sessions:
            session_id = self._sessions[chat_id]
            await self._client.post(
                f"{self.agent_url}/session/{session_id}/reset",
                headers=self._headers(),
            )
            del self._sessions[chat_id]
        return "Session cleared. Starting fresh."

    # ─────────────────────────── Message handling ──────────────────────────

    async def handle_update(self, update: dict) -> None:
        """Process a single Telegram update."""
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        text = message.get("text", "")

        if not chat_id or not text:
            return

        # Access control
        if self.allowed_users and user_id not in self.allowed_users:
            await self.send(chat_id, "Access denied. Your user ID is not authorized.")
            return

        # Handle commands
        if text.startswith("/start"):
            await self.send(chat_id, (
                "<b>Sovereign Agent</b>\n\n"
                "Send me any coding question or task.\n\n"
                "Commands:\n"
                "/clear - Reset conversation\n"
                "/help - Show this message"
            ))
            return

        if text.startswith("/help"):
            await self.send(chat_id, (
                "<b>Commands:</b>\n"
                "/clear - Reset conversation history\n"
                "/help - Show this help\n\n"
                "Just send a message to chat with the agent. "
                "It has full access to tools: file read/write, git, code search, shell, and more."
            ))
            return

        if text.startswith("/clear"):
            result = await self._reset_session(chat_id)
            await self.send(chat_id, result)
            return

        # Regular message → forward to agent
        await self.send_typing(chat_id)

        # Send a placeholder that we'll update
        placeholder = await self._tg("sendMessage", chat_id=chat_id, text="Thinking...")
        placeholder_id = placeholder.get("result", {}).get("message_id")

        try:
            response = await self._chat(chat_id, text)

            # Escape HTML entities in the response for safe Telegram rendering
            safe_response = html.escape(response)

            if placeholder_id:
                await self.edit_message(chat_id, placeholder_id, safe_response)
            else:
                await self.send(chat_id, safe_response)

        except Exception as e:
            error_msg = f"Error: {html.escape(str(e))}"
            if placeholder_id:
                await self.edit_message(chat_id, placeholder_id, error_msg)
            else:
                await self.send(chat_id, error_msg)

    # ─────────────────────────── Polling loop ──────────────────────────────

    async def run(self) -> None:
        """Run the bot with long polling."""
        logger.info("Starting Telegram bot...")

        # Verify connection
        me = await self._tg("getMe")
        bot_info = me.get("result", {})
        logger.info(f"Bot: @{bot_info.get('username', '?')} ({bot_info.get('first_name', '?')})")
        print(f"Bot running: @{bot_info.get('username', '?')}")

        while True:
            try:
                data = await self._tg("getUpdates", offset=self._offset, timeout=30)
                updates = data.get("result", [])

                for update in updates:
                    self._offset = update["update_id"] + 1
                    try:
                        await self.handle_update(update)
                    except Exception as e:
                        logger.exception(f"Error handling update: {e}")

            except httpx.TimeoutException:
                continue
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def close(self) -> None:
        """Clean up resources."""
        await self._client.aclose()


def main() -> None:
    """Entry point for the Telegram bot."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        print("Error: Set TELEGRAM_BOT_TOKEN environment variable")
        print("Get one from @BotFather on Telegram")
        sys.exit(1)

    agent_url = os.getenv("SOVEREIGN_BASE_URL", "http://localhost:8000")
    agent_key = os.getenv("SOVEREIGN_API_KEY", "")

    # Optional: restrict to specific Telegram user IDs
    allowed_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
    allowed_users = [int(x.strip()) for x in allowed_str.split(",") if x.strip()] or None

    bot = TelegramBot(
        bot_token=bot_token,
        agent_url=agent_url,
        agent_api_key=agent_key,
        allowed_users=allowed_users,
    )

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\nBot stopped.")
    finally:
        asyncio.run(bot.close())


if __name__ == "__main__":
    main()
