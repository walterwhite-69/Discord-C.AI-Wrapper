



import traceback
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cai_client import CAIClient
from config import DISCORD_TOKEN
from session_manager import ActiveCharacter, sessions
from webhook_manager import create_webhook, delete_webhook, send_streaming_via_webhook, send_via_webhook


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def require_login(interaction: discord.Interaction) -> str | None:
    return sessions.get_token(interaction.user.id)


def build_search_avatar_url(avatar_file_name: str) -> str:
    if not avatar_file_name:
        return ""
    if avatar_file_name.startswith("http://") or avatar_file_name.startswith("https://"):
        return avatar_file_name
    cleaned = avatar_file_name.lstrip("/")
    return f"https://characterai.io/i/200/static/avatars/{cleaned}?webp=true&anim=0"


async def cai_error_embed(description: str) -> discord.Embed:
    return discord.Embed(
        title="Error",
        description=description,
        color=discord.Color.red(),
    )


async def cai_success_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green(),
    )


async def spawn_character_to_channel(
    *,
    token: str,
    char_id: str,
    channel: discord.TextChannel,
    fallback_name: str | None = None,
    fallback_avatar_url: str | None = None,
    follow_mode: str = "auto",
) -> tuple[ActiveCharacter, str | None, str | None]:
    existing = sessions.get_active(channel.id)
    if existing:
        await delete_webhook(bot, existing.webhook_id)
        sessions.despawn(channel.id)

    client = CAIClient(token)
    chat_data = await client.start_chat(char_id)
    await client.close()

    char_name = (chat_data.get("char_name") or "").strip()
    if not char_name or char_name == char_id:
        char_name = (fallback_name or char_name or "Character").strip()
    avatar_url = (chat_data.get("avatar_url") or fallback_avatar_url or "").strip()
    greeting = chat_data.get("greeting")
    greeting_turn_id = chat_data.get("greeting_turn_id")
    chat_id = chat_data["chat_id"]

    webhook = await create_webhook(channel, char_name, avatar_url)
    active = ActiveCharacter(
        char_id=char_id,
        chat_id=chat_id,
        name=char_name,
        avatar_url=avatar_url,
        webhook_id=webhook.id,
        webhook_url=webhook.url,
        follow_mode=follow_mode,
    )
    sessions.spawn(channel.id, active)
    return active, greeting, greeting_turn_id


async def dispatch_character_reply(
    *,
    channel_id: int,
    char: ActiveCharacter,
    reply_text: str,
    turn_id: Optional[str],
    partial_updates: Optional[list[str]] = None,
) -> list[int]:
    updates = partial_updates or []
    if updates and len(reply_text) <= 1990:
        message_ids = await send_streaming_via_webhook(
            webhook_url=char.webhook_url,
            name=char.name,
            avatar_url=char.avatar_url,
            partial_updates=updates,
            final_content=reply_text,
            max_edits=3,
        )
    else:
        message_ids = await send_via_webhook(
            webhook_url=char.webhook_url,
            name=char.name,
            avatar_url=char.avatar_url,
            content=reply_text,
        )
    if turn_id:
        sessions.track_bot_message_turn(channel_id, message_ids, str(turn_id))
    return message_ids


async def despawn_channel(interaction: discord.Interaction) -> None:
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send(
            embed=await cai_error_embed("This command only works in text channels.")
        )
        return

    char = sessions.get_active(channel.id)
    if not char:
        await interaction.followup.send(
            embed=await cai_error_embed("No character is active in this channel.")
        )
        return

    await delete_webhook(bot, char.webhook_id)
    sessions.despawn(channel.id)
    await interaction.followup.send(
        embed=await cai_success_embed(
            f"{char.name} has left the chat.",
            "Use `/search` or `/spawn` to bring in another character.",
        )
    )


class FollowModeView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        token: str,
        character: dict[str, Any],
        channel: discord.TextChannel,
    ):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.token = token
        self.character = character
        self.channel = channel

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This action belongs to another user.", ephemeral=True)
            return False
        return True

    async def _spawn_with_mode(self, interaction: discord.Interaction, mode: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            active, greeting, greeting_turn_id = await spawn_character_to_channel(
                token=self.token,
                char_id=str(self.character["char_id"]),
                channel=self.channel,
                fallback_name=str(self.character.get("name") or "Character"),
                fallback_avatar_url=str(self.character.get("avatar_url") or ""),
                follow_mode=mode,
            )

            mode_text = "Auto-follow enabled (responds to every message)." if mode == "auto" else "Reply-only mode enabled (responds only when users reply to bot messages)."
            embed = discord.Embed(
                title=f"{active.name} spawned",
                description=f"Channel: {self.channel.mention}\n{mode_text}",
                color=discord.Color.green(),
            )
            if active.avatar_url:
                embed.set_thumbnail(url=active.avatar_url)
            await interaction.followup.send(embed=embed, ephemeral=True)

            if greeting:
                message_ids = await send_via_webhook(
                    webhook_url=active.webhook_url,
                    name=active.name,
                    avatar_url=active.avatar_url,
                    content=greeting,
                )
                if greeting_turn_id:
                    sessions.track_bot_message_turn(self.channel.id, message_ids, greeting_turn_id)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=await cai_error_embed(
                    f"I need Manage Webhooks permission in {self.channel.mention}."
                ),
                ephemeral=True,
            )
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(
                embed=await cai_error_embed(f"Failed to spawn character: {e}"),
                ephemeral=True,
            )

    @discord.ui.button(label="Yes (auto follow-up)", style=discord.ButtonStyle.success)
    async def btn_auto(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._spawn_with_mode(interaction, "auto")

    @discord.ui.button(label="No (reply-only)", style=discord.ButtonStyle.secondary)
    async def btn_reply(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._spawn_with_mode(interaction, "reply")


class ChannelSpawnView(discord.ui.View):
    def __init__(self, owner_id: int, token: str, character: dict[str, Any]):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.token = token
        self.character = character

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This selector belongs to another user.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Pick a channel to spawn this character",
        min_values=1,
        max_values=1,
        channel_types=[discord.ChannelType.text],
    )
    async def select_channel(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ) -> None:
        selected = select.values[0]
        selected_id = int(getattr(selected, "id", 0) or 0)
        guild_channel = interaction.guild.get_channel(selected_id) if interaction.guild else None
        channel = guild_channel if isinstance(guild_channel, discord.TextChannel) else None
        if channel is None and isinstance(selected, discord.TextChannel):
            channel = selected

        if channel is None:
            await interaction.response.send_message(
                embed=await cai_error_embed("Please pick a text channel."),
                ephemeral=True,
            )
            return

        mode_view = FollowModeView(
            owner_id=self.owner_id,
            token=self.token,
            character=self.character,
            channel=channel,
        )
        embed = discord.Embed(
            title=f"Follow-up Mode for {self.character.get('name', 'Character')}",
            description=(
                f"Channel: {channel.mention}\n"
                "Yes = bot responds to every message.\n"
                "No = bot responds only when users reply to a bot message."
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=mode_view, ephemeral=True)


class SearchResultsView(discord.ui.View):
    PAGE_SIZE = 5

    def __init__(
        self,
        owner_id: int,
        token: str,
        query: str,
        characters: list[dict[str, Any]],
    ):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.token = token
        self.query = query
        self.characters = characters
        self.page = 0
        self.total_pages = max(1, (len(characters) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._refresh_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This search view belongs to another user.",
                ephemeral=True,
            )
            return False
        return True

    def _page_items(self) -> list[dict[str, Any]]:
        start = self.page * self.PAGE_SIZE
        return self.characters[start : start + self.PAGE_SIZE]

    def _refresh_buttons(self) -> None:
        items = self._page_items()
        self.btn_prev.disabled = self.page == 0
        self.btn_next.disabled = self.page >= self.total_pages - 1
        number_buttons = [
            self.btn_pick1,
            self.btn_pick2,
            self.btn_pick3,
            self.btn_pick4,
            self.btn_pick5,
        ]
        for idx, btn in enumerate(number_buttons):
            btn.disabled = idx >= len(items)
            btn.label = str(idx + 1)

    def build_embeds(self) -> list[discord.Embed]:
        items = self._page_items()
        start_index = self.page * self.PAGE_SIZE
        embeds: list[discord.Embed] = []
        for idx, char in enumerate(items, start=1):
            name = char.get("name", "Unknown")
            title = char.get("title") or ""
            description = (char.get("description") or "No description.").strip()
            chats = int(char.get("participant__num_interactions") or 0)
            char_id = char.get("char_id", "—")
            avatar_url = char.get("avatar_url") or ""

            header = f"{idx}. {name}"
            if title:
                header += f" — {title}"
            embed = discord.Embed(
                title=header,
                description=(
                    f"{description[:600]}\n\n"
                    f"ID: `{char_id}`\n"
                    f"Chats: {chats:,}"
                ),
                color=discord.Color.blurple(),
            )
            if avatar_url:
                embed.set_image(url=avatar_url)
            embed.set_footer(
                text=(
                    f'Query: "{self.query}" | '
                    f"Page {self.page + 1}/{self.total_pages} | "
                    f"Result {start_index + idx} of {len(self.characters)}"
                )
            )
            embeds.append(embed)
        return embeds

    async def _open_channel_picker(self, interaction: discord.Interaction, local_index: int) -> None:
        items = self._page_items()
        if local_index >= len(items):
            await interaction.response.send_message(
                embed=await cai_error_embed("That result slot is empty on this page."),
                ephemeral=True,
            )
            return

        chosen = items[local_index]
        channel_view = ChannelSpawnView(
            owner_id=self.owner_id,
            token=self.token,
            character=chosen,
        )
        embed = discord.Embed(
            title=f"Spawn {chosen.get('name', 'Character')}",
            description=(
                f"Character ID: `{chosen.get('char_id', '—')}`\n"
                "Select the channel where the webhook should be created."
            ),
            color=discord.Color.green(),
        )
        if chosen.get("avatar_url"):
            embed.set_thumbnail(url=chosen["avatar_url"])

        await interaction.response.send_message(embed=embed, view=channel_view, ephemeral=True)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def btn_prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        self._refresh_buttons()
        await interaction.response.edit_message(embeds=self.build_embeds(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def btn_next(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
        self._refresh_buttons()
        await interaction.response.edit_message(embeds=self.build_embeds(), view=self)

    @discord.ui.button(label="1", style=discord.ButtonStyle.primary, row=1)
    async def btn_pick1(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._open_channel_picker(interaction, 0)

    @discord.ui.button(label="2", style=discord.ButtonStyle.primary, row=1)
    async def btn_pick2(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._open_channel_picker(interaction, 1)

    @discord.ui.button(label="3", style=discord.ButtonStyle.primary, row=1)
    async def btn_pick3(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._open_channel_picker(interaction, 2)

    @discord.ui.button(label="4", style=discord.ButtonStyle.primary, row=1)
    async def btn_pick4(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._open_channel_picker(interaction, 3)

    @discord.ui.button(label="5", style=discord.ButtonStyle.primary, row=1)
    async def btn_pick5(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._open_channel_picker(interaction, 4)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Slash commands synced.")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.webhook_id:
        return

    char = sessions.get_active(message.channel.id)
    if char is None:
        await bot.process_commands(message)
        return

    token = sessions.get_token(message.author.id)
    if token is None:
        await bot.process_commands(message)
        return

    if char.follow_mode == "reply":
        ref_id = message.reference.message_id if message.reference else None
        if not ref_id or not sessions.is_tracked_bot_message(message.channel.id, ref_id):
            await bot.process_commands(message)
            return

    try:
        client = CAIClient(token)
        result = await client.send_message_with_meta(char.char_id, char.chat_id, message.content)
        await client.close()
        reply = str(result.get("text") or "")
        turn_id = result.get("turn_id")
        updates = result.get("updates") or []
        await dispatch_character_reply(
            channel_id=message.channel.id,
            char=char,
            reply_text=reply,
            turn_id=turn_id,
            partial_updates=updates,
        )
    except Exception as e:
        await message.channel.send(
            embed=await cai_error_embed(f"Failed to get response: {e}"),
            delete_after=10,
        )

    await bot.process_commands(message)


@bot.tree.command(name="login", description="Link your Character.AI account using your email address")
@app_commands.describe(email="Your Character.AI email address")
async def cmd_login(interaction: discord.Interaction, email: str):
    await interaction.response.defer(ephemeral=True)

    try:
        import login as cai_login_flow
        from recaptcha import solve_recaptcha

        async def on_email_sent(_: str, user_email: str):
            await interaction.followup.send(
                embed=await cai_success_embed(
                    "Magic Link Sent",
                    (
                        f"Check your inbox for **{user_email}** and click the Character.AI login link.\n"
                        "Waiting for verification..."
                    ),
                ),
                ephemeral=True,
            )

        rc_token = await solve_recaptcha()
        result = await cai_login_flow.login(email, rc_token, on_email_sent_hook=on_email_sent)
        token = result["token"]

        client = CAIClient(token)
        user_data = await client.validate_token()
        await client.close()

        username = user_data.get("user", {}).get("user", {}).get("username", "Unknown")
        sessions.set_token(interaction.user.id, token)

        await interaction.followup.send(
            embed=await cai_success_embed(
                "Logged in",
                (
                    f"Authenticated as **{username}**.\n"
                    "Session is stored in memory for this bot runtime."
                ),
            ),
            ephemeral=True,
        )
    except TimeoutError:
        await interaction.followup.send(
            embed=await cai_error_embed("Login timed out before magic link verification."),
            ephemeral=True,
        )
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(
            embed=await cai_error_embed(f"Login failed: {e}"),
            ephemeral=True,
        )


@bot.tree.command(name="logout", description="Remove your Character.AI session")
async def cmd_logout(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not sessions.has_session(interaction.user.id):
        await interaction.followup.send(
            embed=await cai_error_embed("You are not logged in."),
            ephemeral=True,
        )
        return
    sessions.remove_token(interaction.user.id)
    await interaction.followup.send(
        embed=await cai_success_embed("Logged out", "Your session was removed."),
        ephemeral=True,
    )


@bot.tree.command(name="search", description="Search for characters on Character.AI")
@app_commands.describe(query="Search term, e.g. Naruto or therapist")
async def cmd_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True)

    token = require_login(interaction)
    if not token:
        await interaction.followup.send(
            embed=await cai_error_embed("You need to `/login` first."),
            ephemeral=True,
        )
        return

    try:
        client = CAIClient(token)
        raw_chars = await client.search_characters(query)
        await client.close()

        if not raw_chars:
            await interaction.followup.send(
                embed=await cai_error_embed(f'No characters found for "{query}".'),
                ephemeral=True,
            )
            return

        normalized: list[dict[str, Any]] = []
        for char in raw_chars:
            avatar_file_name = str(char.get("avatar_file_name") or "")
            normalized.append(
                {
                    "char_id": str(char.get("external_id") or ""),
                    "name": str(char.get("name") or "Unknown"),
                    "title": str(char.get("title") or ""),
                    "description": str(char.get("description") or "No description."),
                    "participant__num_interactions": int(char.get("participant__num_interactions") or 0),
                    "avatar_url": build_search_avatar_url(avatar_file_name),
                }
            )

        view = SearchResultsView(
            owner_id=interaction.user.id,
            token=token,
            query=query,
            characters=normalized,
        )
        await interaction.followup.send(embeds=view.build_embeds(), view=view, ephemeral=True)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(
            embed=await cai_error_embed(f"Search failed: {e}"),
            ephemeral=True,
        )


@bot.tree.command(name="spawn", description="Spawn a character as a webhook in this channel")
@app_commands.describe(char_id="Character external_id from /search")
async def cmd_spawn(interaction: discord.Interaction, char_id: str):
    token = require_login(interaction)
    if not token:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            embed=await cai_error_embed("You need to `/login` first."),
            ephemeral=True,
        )
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            embed=await cai_error_embed("This command only works in text channels."),
            ephemeral=True,
        )
        return

    follow_view = FollowModeView(
        owner_id=interaction.user.id,
        token=token,
        character={"char_id": char_id, "name": char_id, "avatar_url": ""},
        channel=channel,
    )
    embed = discord.Embed(
        title=f"Follow-up Mode for `{char_id}`",
        description=(
            f"Channel: {channel.mention}\n"
            "Yes = bot responds to every message.\n"
            "No = bot responds only when users reply to a bot message."
        ),
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, view=follow_view, ephemeral=True)


@bot.tree.command(name="despawn", description="Remove the active character from this channel")
async def cmd_despawn(interaction: discord.Interaction):
    await interaction.response.defer()
    await despawn_channel(interaction)


@bot.tree.command(name="delete", description="Delete the active webhook from this channel")
async def cmd_delete(interaction: discord.Interaction):
    await interaction.response.defer()
    await despawn_channel(interaction)


@bot.tree.command(name="chat", description="Send a message to the active character in this channel")
@app_commands.describe(message="What you want to say to the character")
async def cmd_chat(interaction: discord.Interaction, message: str):
    await interaction.response.defer()

    token = require_login(interaction)
    if not token:
        await interaction.followup.send(
            embed=await cai_error_embed("You need to `/login` first."),
            ephemeral=True,
        )
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send(
            embed=await cai_error_embed("This command only works in text channels.")
        )
        return

    char = sessions.get_active(channel.id)
    if not char:
        await interaction.followup.send(
            embed=await cai_error_embed("No active character here. Use `/search` or `/spawn` first.")
        )
        return

    try:
        client = CAIClient(token)
        result = await client.send_message_with_meta(char.char_id, char.chat_id, message)
        await client.close()
        reply = str(result.get("text") or "")
        turn_id = result.get("turn_id")
        updates = result.get("updates") or []

        await interaction.followup.send(f"**You:** {message}", ephemeral=True)
        await dispatch_character_reply(
            channel_id=channel.id,
            char=char,
            reply_text=reply,
            turn_id=turn_id,
            partial_updates=updates,
        )
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(
            embed=await cai_error_embed(f"Failed to get response: {e}")
        )


@bot.tree.command(name="regenerate", description="Regenerate a previous bot reply")
@app_commands.describe(message_id="Optional: message ID of a bot reply. If omitted, uses latest bot reply.")
async def cmd_regenerate(interaction: discord.Interaction, message_id: Optional[str] = None):
    await interaction.response.defer(ephemeral=True)

    token = require_login(interaction)
    if not token:
        await interaction.followup.send(embed=await cai_error_embed("You need to `/login` first."), ephemeral=True)
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send(embed=await cai_error_embed("This command only works in text channels."), ephemeral=True)
        return

    char = sessions.get_active(channel.id)
    if not char:
        await interaction.followup.send(embed=await cai_error_embed("No active character in this channel."), ephemeral=True)
        return

    target_turn_id: Optional[str] = None
    if message_id:
        try:
            msg_id_int = int(message_id)
        except ValueError:
            await interaction.followup.send(embed=await cai_error_embed("`message_id` must be a valid integer."), ephemeral=True)
            return
        target_turn_id = sessions.get_turn_for_message(channel.id, msg_id_int)
    else:
        target_turn_id = sessions.get_latest_tracked_turn(channel.id)

    if not target_turn_id:
        await interaction.followup.send(
            embed=await cai_error_embed("Could not find a tracked bot reply to regenerate in this channel."),
            ephemeral=True,
        )
        return

    try:
        client = CAIClient(token)
        result = await client.regenerate_turn_candidate(char.char_id, char.chat_id, target_turn_id)
        await client.close()

        reply = str(result.get("text") or "")
        new_turn_id = result.get("turn_id")
        message_ids = await send_via_webhook(
            webhook_url=char.webhook_url,
            name=char.name,
            avatar_url=char.avatar_url,
            content=reply,
        )
        if new_turn_id:
            sessions.track_bot_message_turn(channel.id, message_ids, str(new_turn_id))

        await interaction.followup.send("Regenerated.", ephemeral=True)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(embed=await cai_error_embed(f"Regenerate failed: {e}"), ephemeral=True)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
