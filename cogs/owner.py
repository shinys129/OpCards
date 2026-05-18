"""
Owner & Admin commands triggered by bot mentions.
Examples:
  @Bot admin givecurrency @User 1000000
  @Bot admin setcurrency @User 500000
  @Bot admin takecurrency @User 100000
  @Bot admin givecard @User Pikachu
  @Bot admin takecard @User Charizard
  @Bot admin ban @User cheating
  @Bot admin unban @User
  @Bot admin userinfo @User
  @Bot admin stats
  @Bot admin findcard Charizard
  @Bot admin help
"""
import re
import datetime

import discord
from discord.ext import commands

ADMIN_HELP_TEXT = """
**Admin / Owner Commands** *(triggered by mentioning the bot + "admin")*

✅ **Currency**
`admin givecurrency @user <amount>` — Give money to a user
`admin setcurrency @user <amount>` — Set a user's money to exact amount
`admin takecurrency @user <amount>` — Remove money from a user

✅ **Cards**
`admin givecard @user <card_name>` — Give a card to a user (searches by name)
`admin givecard @user <card_id>` — Give a card by exact ID
`admin takecard @user <card_id>` — Remove one copy of a card from a user
`admin findcard <name>` — Search cards by partial name

✅ **Users**
`admin ban @user [reason]` — Ban a user from using the bot globally
`admin unban @user` — Unban a user
`admin bannedlist` — List all banned users
`admin userinfo @user` — Show full profile + stats for a user
`admin listusers` — Show top users by money (paged)
`admin resetdaily @user` — Reset a user's daily cooldown

✅ **Other**
`admin stats` — Show global bot stats
`admin guilds` — List servers the bot is in
`admin reload` — Reload all cogs
`admin help` — Show this menu
"""


class Owner(commands.Cog):
    """Mention-based owner & admin commands."""

    def __init__(self, bot):
        self.bot = bot

    async def _is_owner_or_admin(self, member: discord.Member) -> bool:
        """Return True if the member is the bot owner or has admin perms."""
        try:
            is_owner = await self.bot.is_owner(member)
            if is_owner:
                return True
        except Exception:
            pass
        if member.guild_permissions.administrator:
            return True
        return False

    def _parse_mention_command(self, content: str) -> list:
        """Strip only the bot's own mention, keep other mentions."""
        bot_id = self.bot.user.id
        # Match <@ID> or <@!ID> where ID is the bot's ID only
        pattern = rf"<@!?{bot_id}>"
        cleaned = re.sub(pattern, "", content)
        # Strip extra whitespace and split
        return cleaned.strip().split()

    def _extract_user_mention(self, words: list) -> tuple:
        """Find first user mention ID in words, return (user_id, remaining_words)."""
        for idx, word in enumerate(words):
            match = re.match(r"<@!?" + r"(\d+)>", word)
            if match:
                user_id = int(match.group(1))
                remaining = words[:idx] + words[idx + 1:]
                return user_id, remaining
        return None, words

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Only process if the bot is mentioned
        if self.bot.user.id not in [m.id for m in message.mentions]:
            return
        if message.author.bot:
            return
        if not message.guild:
            return

        words = self._parse_mention_command(message.content)
        if not words:
            return

        # Must start with "admin" (case-insensitive)
        if words[0].lower() != "admin":
            return

        # Authorization: only bot owner or server admin
        if not await self._is_owner_or_admin(message.author):
            return await message.reply("You don't have permission to use admin commands.", mention_author=False)

        args = words[1:]
        if not args:
            return await message.reply("What admin command? Try `@bot admin help`", mention_author=False)

        sub = args[0].lower()
        ctx = await self.bot.get_context(message)

        # ── Help ──
        if sub == "help":
            embed = self.bot.Embed(title="Bot Admin Commands", description=ADMIN_HELP_TEXT)
            return await message.reply(embed=embed, mention_author=False)

        # ── Currency ──
        elif sub in ("givecurrency", "givemoney", "addmoney"):
            await self._cmd_givecurrency(ctx, message, args[1:])
        elif sub in ("setcurrency", "setmoney"):
            await self._cmd_setcurrency(ctx, message, args[1:])
        elif sub in ("takecurrency", "takemoney", "removemoney", "deductmoney"):
            await self._cmd_takecurrency(ctx, message, args[1:])

        # ── Cards ──
        elif sub in ("givecard", "addcard"):
            await self._cmd_givecard(ctx, message, args[1:])
        elif sub in ("takecard", "removecard"):
            await self._cmd_takecard(ctx, message, args[1:])
        elif sub in ("findcard", "searchcard"):
            await self._cmd_findcard(ctx, message, args[1:])

        # ── Users ──
        elif sub == "ban":
            await self._cmd_ban(ctx, message, args[1:])
        elif sub == "unban":
            await self._cmd_unban(ctx, message, args[1:])
        elif sub in ("bannedlist", "banlist", "bans"):
            await self._cmd_bannedlist(ctx, message)
        elif sub in ("userinfo", "user", "profile"):
            await self._cmd_userinfo(ctx, message, args[1:])
        elif sub in ("listusers", "users", "leaderboard"):
            await self._cmd_listusers(ctx, message, args[1:])
        elif sub == "resetdaily":
            await self._cmd_resetdaily(ctx, message, args[1:])

        # ── Misc ──
        elif sub in ("stats", "statistics"):
            await self._cmd_stats(ctx, message)
        elif sub in ("guilds", "servers"):
            await self._cmd_guilds(ctx, message)
        elif sub in ("reload", "reloadcogs"):
            await self._cmd_reload(ctx, message)
        else:
            await message.reply(f"Unknown admin command: `{sub}`. Try `@bot admin help`", mention_author=False)

    # ═══════════════════════════════════════════════════════════
    #  Currency sub-commands
    # ═══════════════════════════════════════════════════════════

    async def _cmd_givecurrency(self, ctx, message, args):
        user_id, rest = self._extract_user_mention(args)
        if not user_id or not rest:
            return await message.reply("Usage: `@bot admin givecurrency @user <amount>`", mention_author=False)
        try:
            amount = int(rest[0])
        except ValueError:
            return await message.reply("Amount must be a number.", mention_author=False)
        member = message.guild.get_member(user_id) or await self.bot.fetch_user(user_id)
        await self.bot.db.add_money(member, amount)
        new_bal = await self.bot.db.get_money(member)
        embed = self.bot.Embed(title="Currency Given", color=0x00FF00)
        embed.add_field(name="User", value=f"{member.mention}", inline=True)
        embed.add_field(name="Given", value=f"{amount:,}", inline=True)
        embed.add_field(name="New Balance", value=f"{new_bal:,}", inline=True)
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_setcurrency(self, ctx, message, args):
        user_id, rest = self._extract_user_mention(args)
        if not user_id or not rest:
            return await message.reply("Usage: `@bot admin setcurrency @user <amount>`", mention_author=False)
        try:
            amount = int(rest[0])
        except ValueError:
            return await message.reply("Amount must be a number.", mention_author=False)
        member = message.guild.get_member(user_id) or await self.bot.fetch_user(user_id)
        await self.bot.db.set_money(member, amount)
        embed = self.bot.Embed(title="Currency Set", color=0xFFA500)
        embed.add_field(name="User", value=f"{member.mention}", inline=True)
        embed.add_field(name="Set To", value=f"{amount:,}", inline=True)
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_takecurrency(self, ctx, message, args):
        user_id, rest = self._extract_user_mention(args)
        if not user_id or not rest:
            return await message.reply("Usage: `@bot admin takecurrency @user <amount>`", mention_author=False)
        try:
            amount = int(rest[0])
        except ValueError:
            return await message.reply("Amount must be a number.", mention_author=False)
        member = message.guild.get_member(user_id) or await self.bot.fetch_user(user_id)
        old_bal = await self.bot.db.get_money(member)
        await self.bot.db.remove_money(member, amount)
        new_bal = await self.bot.db.get_money(member)
        embed = self.bot.Embed(title="Currency Taken", color=0xFF4444)
        embed.add_field(name="User", value=f"{member.mention}", inline=True)
        embed.add_field(name="Taken", value=f"{amount:,}", inline=True)
        embed.add_field(name="Balance", value=f"{old_bal:,} → {new_bal:,}", inline=True)
        await message.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════
    #  Card sub-commands
    # ═══════════════════════════════════════════════════════════

    async def _cmd_givecard(self, ctx, message, args):
        user_id, rest = self._extract_user_mention(args)
        if not user_id or not rest:
            return await message.reply("Usage: `@bot admin givecard @user <card_name_or_id>`", mention_author=False)
        query = " ".join(rest)

        # Try exact ID first, then search by name
        card = await self.bot.db.get_card_by_id(query)
        if not card:
            results = await self.bot.db.search_cards_by_name(query)
            if not results:
                return await message.reply(f"No card found matching `**{query}**`.", mention_author=False)
            if len(results) > 1:
                lines = "\n".join([f"`{c['id']}` — **{c['name']}** ({c['rarity']})" for c in results[:5]])
                return await message.reply(
                    f"Multiple matches for `{query}`. Be more specific or use the exact card ID:\n{lines}",
                    mention_author=False
                )
            card = results[0]

        await self.bot.db.add_card_to_user(str(user_id), card["id"])
        embed = self.bot.Embed(title="Card Given", color=0x00FF00)
        embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
        embed.add_field(name="Card", value=f"**{card['name']}**\n`{card['id']}`", inline=True)
        embed.add_field(name="Rarity", value=card.get("rarity", "Unknown"), inline=True)
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_takecard(self, ctx, message, args):
        user_id, rest = self._extract_user_mention(args)
        if not user_id or not rest:
            return await message.reply("Usage: `@bot admin takecard @user <card_id>`", mention_author=False)
        card_id = rest[0]
        removed = await self.bot.db.remove_card_from_user(str(user_id), card_id)
        if removed:
            embed = self.bot.Embed(title="Card Removed", color=0xFF4444)
            embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
            embed.add_field(name="Card ID", value=f"`{card_id}`", inline=True)
        else:
            embed = self.bot.Embed(title="Card Not Found", color=0x888888)
            embed.description = f"<@{user_id}> doesn't have card `{card_id}`."
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_findcard(self, ctx, message, args):
        if not args:
            return await message.reply("Usage: `@bot admin findcard <name>`", mention_author=False)
        query = " ".join(args)
        results = await self.bot.db.search_cards_by_name(query)
        if not results:
            return await message.reply(f"No cards found for `{query}`.", mention_author=False)
        lines = "\n".join([f"`{c['id']}` — **{c['name']}** ({c['rarity']})" for c in results[:10]])
        embed = self.bot.Embed(title=f"Card Search: {query}", description=lines)
        await message.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════
    #  User sub-commands
    # ═══════════════════════════════════════════════════════════

    async def _cmd_ban(self, ctx, message, args):
        user_id, rest = self._extract_user_mention(args)
        if not user_id:
            return await message.reply("Usage: `@bot admin ban @user [reason]`", mention_author=False)
        reason = " ".join(rest) if rest else "No reason given"
        await self.bot.db.ban_user(user_id, reason, message.author.id)
        embed = self.bot.Embed(title="User Banned", color=0xFF0000)
        embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="By", value=message.author.mention, inline=True)
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_unban(self, ctx, message, args):
        user_id, rest = self._extract_user_mention(args)
        if not user_id:
            return await message.reply("Usage: `@bot admin unban @user`", mention_author=False)
        await self.bot.db.unban_user(user_id)
        embed = self.bot.Embed(title="User Unbanned", color=0x00FF00)
        embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
        embed.add_field(name="By", value=message.author.mention, inline=True)
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_bannedlist(self, ctx, message):
        bans = await self.bot.db.get_banned_users()
        if not bans:
            return await message.reply("No banned users.", mention_author=False)
        lines = []
        for b in bans[:20]:
            ts = b["banned_at"][:16].replace("T", " ") if b["banned_at"] else "?"
            lines.append(f"<@{b['user_id']}> — `{ts}` — {b.get('reason', 'N/A')}")
        embed = self.bot.Embed(title="Banned Users", description="\n".join(lines))
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_userinfo(self, ctx, message, args):
        user_id, _ = self._extract_user_mention(args)
        if not user_id:
            user_id = message.author.id
        info = await self.bot.db.get_user_info(user_id)
        if not info:
            return await message.reply("User not found in the database.", mention_author=False)
        member = message.guild.get_member(user_id) or await self.bot.fetch_user(user_id)
        embed = self.bot.Embed(title=f"User Info: {member}", color=0x3498db)
        embed.add_field(name="Money", value=f"{info['money']:,}", inline=True)
        embed.add_field(name="Interactions", value=f"{info['interactions']:,}", inline=True)
        embed.add_field(name="Cards", value=f"{info['total_cards']:,} ({info['unique_cards']} unique)", inline=True)
        embed.add_field(name="Joined", value=info["joined_at"][:10] if info["joined_at"] else "?", inline=True)
        embed.add_field(name="Banned", value="Yes" if info["banned"] else "No", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_listusers(self, ctx, message, args):
        page = 1
        if args:
            try:
                page = max(1, int(args[0]))
            except ValueError:
                pass
        users = await self.bot.db.get_all_users_paginated(page, 15)
        total = await self.bot.db.count_all_users()
        if not users:
            return await message.reply("No users found.", mention_author=False)
        lines = []
        for i, u in enumerate(users, start=(page - 1) * 15 + 1):
            lines.append(f"`{i}.` {u['name']} — **{u['money']:,}** coins")
        embed = self.bot.Embed(title=f"Top Users (Page {page})", description="\n".join(lines))
        embed.set_footer(text=f"Total users: {total:,}")
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_resetdaily(self, ctx, message, args):
        user_id, _ = self._extract_user_mention(args)
        if not user_id:
            return await message.reply("Usage: `@bot admin resetdaily @user`", mention_author=False)
        await self.bot.db.reset_daily(user_id)
        await message.reply(f"Daily cooldown reset for <@{user_id}>.", mention_author=False)

    # ═══════════════════════════════════════════════════════════
    #  Misc sub-commands
    # ═══════════════════════════════════════════════════════════

    async def _cmd_stats(self, ctx, message):
        stats = await self.bot.db.get_global_stats()
        total_cards = await self.bot.db.get_total_cards_bot()
        embed = self.bot.Embed(title="Bot Global Statistics", color=0x9b59b6)
        if stats:
            embed.add_field(name="Servers", value=stats["current_servers_total"], inline=True)
            embed.add_field(name="Users", value=stats["current_users_total"], inline=True)
            embed.add_field(name="Cards (DB)", value=total_cards, inline=True)
            embed.add_field(name="Total Money", value=f"{stats['current_money_total']:,}", inline=True)
            embed.add_field(name="Cards Earned", value=stats["cards_earned_total"], inline=True)
            embed.add_field(name="Money Earned", value=f"{stats['money_earned_total']:,}", inline=True)
        embed.add_field(name="Guilds Live", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Shard Count", value=len(self.bot.shards), inline=True)
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_guilds(self, ctx, message):
        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)
        lines = []
        for g in guilds[:30]:
            lines.append(f"`{g.id}` — **{g.name}** ({g.member_count or '?'} members)")
        embed = self.bot.Embed(title=f"Servers ({len(self.bot.guilds)} total)", description="\n".join(lines))
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_reload(self, ctx, message):
        errors = []
        for ext in list(self.bot.extensions.keys()):
            if ext == "jishaku":
                continue
            try:
                await self.bot.reload_extension(ext)
            except Exception as e:
                errors.append(f"{ext}: {e}")
        if errors:
            embed = self.bot.Embed(title="Reloaded with errors", color=0xFF8800)
            embed.description = "\n".join(errors)
        else:
            embed = self.bot.Embed(title="All cogs reloaded", color=0x00FF00)
        await message.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(Owner(bot))
