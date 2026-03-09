import aiohttp
import discord
from typing import Optional


async def create_webhook(
    channel: discord.TextChannel,
    name: str,
    avatar_url: str,
) -> discord.Webhook:

    avatar_bytes: Optional[bytes] = None


    if avatar_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
        except Exception:
            pass

    webhook = await channel.create_webhook(
        name=name[:80],
        avatar=avatar_bytes,
        reason="CharacterAI Discord Bot — character spawned",
    )
    return webhook


async def send_via_webhook(
    webhook_url: str,
    name: str,
    avatar_url: str,
    content: str,
    wait: bool = True,
) -> list[int]:
    message_ids: list[int] = []
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(webhook_url, session=session)
        chunks = [content[i:i+1990] for i in range(0, len(content), 1990)]
        for chunk in chunks:
            sent = await webhook.send(
                content=chunk,
                username=name[:80],
                avatar_url=avatar_url or discord.utils.MISSING,
                wait=wait,
            )
            if wait and sent:
                message_ids.append(sent.id)
    return message_ids


async def send_streaming_via_webhook(
    webhook_url: str,
    name: str,
    avatar_url: str,
    partial_updates: list[str],
    final_content: str,
    max_edits: int = 3,
) -> list[int]:
    if not final_content:
        final_content = "(empty response)"

    if len(final_content) > 1990:
        return await send_via_webhook(
            webhook_url=webhook_url,
            name=name,
            avatar_url=avatar_url,
            content=final_content,
            wait=True,
        )

    updates: list[str] = []
    for u in partial_updates:
        if u and isinstance(u, str):
            if not updates or updates[-1] != u:
                updates.append(u)
    updates = updates[: max(0, max_edits - 1)]

    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(webhook_url, session=session)
        initial = updates[0] if updates else "..."
        msg = await webhook.send(
            content=initial[:1990],
            username=name[:80],
            avatar_url=avatar_url or discord.utils.MISSING,
            wait=True,
        )

        edits_used = 0
        for upd in updates[1:]:
            if edits_used >= max_edits:
                break
            await webhook.edit_message(msg.id, content=upd[:1990])
            edits_used += 1

        if edits_used < max_edits and msg.content != final_content[:1990]:
            await webhook.edit_message(msg.id, content=final_content[:1990])

        return [msg.id]


async def delete_webhook(bot: discord.Client, webhook_id: int) -> None:




    try:
        webhook = await bot.fetch_webhook(webhook_id)
        await webhook.delete(reason="CharacterAI Discord Bot — character despawned")
    except discord.NotFound:
        pass
    except Exception as e:
        print(f"[webhook_manager] Failed to delete webhook {webhook_id}: {e}")
