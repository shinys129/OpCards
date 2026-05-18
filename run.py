"""
Simple runner for the Munch Discord bot.
Loads the bot with a single process instead of the multi-cluster launcher.
"""
import asyncio
import os
import logging

import discord
from discord.ext import commands

import config
import cogs
import helpers
import db_sqlite

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s %(name)s/%(levelname)s] %(message)s"
)
log = logging.getLogger("MunchBot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.typing = False
intents.presences = False

async def determine_prefix(bot, message):
    cog = bot.get_cog("Bot")
    if cog and message.guild:
        return await cog.determine_prefix(message.guild)
    return ["p!", "P!", bot.user.mention + " ", bot.user.mention[:2] + "!" + bot.user.mention[2:] + " "]

def is_enabled(ctx):
    if not ctx.bot.enabled:
        raise commands.CheckFailure("Bot is currently down for maintenance. Try again later.")
    return True

class MunchBot(commands.AutoShardedBot):
    class Embed(discord.Embed):
        def __init__(self, **kwargs):
            color = kwargs.pop("color", 0xF44336)
            super().__init__(**kwargs, color=color)

    def __init__(self):
        self.config = config
        self.ready = False
        self.cluster_name = "Main"
        self.cluster_idx = 0
        super().__init__(
            command_prefix=determine_prefix,
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
            intents=intents,
        )
        self.add_check(
            commands.bot_has_permissions(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
                add_reactions=True,
                external_emojis=True,
            ).predicate
        )
        self.add_check(is_enabled)

    async def setup_hook(self):
        # Initialize SQLite database and load cards
        db_sqlite.seed_database()

        # Load extensions
        try:
            await self.load_extension("jishaku")
        except Exception as e:
            log.warning(f"jishaku not loaded: {e}")

        for i in cogs.default:
            try:
                await self.load_extension(f"cogs.{i}")
                log.info(f"Loaded cog: {i}")
            except Exception as e:
                log.error(f"Failed to load cog {i}: {e}")
                import traceback
                traceback.print_exc()

    async def on_ready(self):
        self.ready = True
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"Guilds: {len(self.guilds)}")

        # Add any missing servers to db
        db_cog = self.get_cog("Db")
        if db_cog:
            try:
                current_servers_in_db = await db_cog.get_server_ids()
                for server in self.guilds:
                    if str(server.id) not in current_servers_in_db:
                        log.info(f"Adding server {server.id} to db")
                        await db_cog.add_server(server)
            except Exception as e:
                log.error(f"Error syncing servers: {e}")

    @property
    def pokemon(self):
        return self.get_cog("Pokemon")

    @property
    def embeds(self):
        return self.get_cog("Embeds")

    @property
    def db(self):
        return self.get_cog("Db")

    @property
    def log(self):
        return self.get_cog("Logging").log if self.get_cog("Logging") else logging.getLogger("MunchBot")

    @property
    def enabled(self):
        for cog in self.cogs.values():
            try:
                if not getattr(cog, "ready", True):
                    return False
            except AttributeError:
                pass
        return self.ready

    async def on_message(self, message: discord.Message):
        if message.author == self.user or message.author.bot or message.guild is None:
            return

        # Check if user is globally banned
        db_cog = self.get_cog("Db")
        if db_cog:
            try:
                is_banned = await db_cog.is_banned(str(message.author.id))
                if is_banned:
                    return
            except Exception:
                pass

        # Escape quotes to prevent parsing issues
        message.content = (
            message.content.replace("\u2014", "--")
            .replace("\u2032", "\\'")
            .replace("\u2018", "\\'")
            .replace("\u2019", "\\'")
            .replace("'", "\\'")
        )

        try:
            await self.process_commands(message)
        except Exception as e:
            log.error(f"ERROR in on_message: {e}")

        server_id = str(message.guild.id)
        prefixes = await determine_prefix(self, message)
        if message.content.startswith(tuple(prefixes)):
            db_cog = self.get_cog("Db")
            if db_cog:
                try:
                    await db_cog.increment_user_interactions(str(message.author.id))
                    await db_cog.add_server_interactions_count(server_id)
                except Exception:
                    pass
            return

        db_cog = self.get_cog("Db")
        if db_cog:
            try:
                await db_cog.add_server_messages_count(server_id)
                total_server_messages = await db_cog.get_server_messages_count(server_id)
                if total_server_messages:
                    TO_DROP = 22
                    server_msgs_per_day = await db_cog.get_server_msgs_per_day(server_id)
                    if server_msgs_per_day and server_msgs_per_day / 300 > 22:
                        TO_DROP = int(server_msgs_per_day / 300)
                    drop = total_server_messages % TO_DROP
                    if drop == 0:
                        await self.pokemon.card_drop(server_id)
            except Exception as e:
                log.error(f"Error in message handler: {e}")

    async def close(self):
        log.info("Shutting down")
        await super().close()

if __name__ == "__main__":
    bot = MunchBot()
    bot.run(config.TOKEN)
