"""
Compatibility wrapper that injects a SQLite-based Db class into cogs.db
so the bot can run without MySQL.
"""
import sqlite3
import datetime
import random
from helpers import constants
from db_sqlite import get_db, init_db, load_cards_from_json

DAILY_MONEY = 200
STORE = constants.STORE

class DbSqlite:
    """SQLite replacement for the MySQL Db cog."""

    def __init__(self, bot):
        self.bot = bot
        init_db()
        load_cards_from_json()
        self.connection = get_db()

    async def get_connection(self):
        return self.connection

    async def reconnect(self):
        pass

    async def manual_reconnect(self):
        return True, "SQLite is always connected"

    async def get_server_prefix(self, serverID):
        try:
            c = self.connection.cursor()
            c.execute("SELECT prefix FROM servers_config WHERE server_id = ?", (serverID,))
            row = c.fetchone()
            return row[0] if row else "p!"
        except Exception:
            return "p!"

    async def delete_server(self, server_id):
        c = self.connection.cursor()
        c.execute("DELETE FROM servers_config WHERE server_id = ?", (server_id,))
        c.execute("DELETE FROM servers WHERE server_id = ?", (server_id,))
        self.connection.commit()
        await self.decrement_servers_statistics()

    async def add_server(self, server):
        now = datetime.datetime.now().isoformat()
        c = self.connection.cursor()
        c.execute("""
            INSERT OR IGNORE INTO servers (name, server_id, server_owner_name, server_owner_id, region, joined_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (server.name, str(server.id), str(server.owner), str(server.owner_id), str(getattr(server, 'preferred_locale', 'unknown')), now))
        c.execute("INSERT OR IGNORE INTO servers_config (server_id) VALUES (?)", (str(server.id),))
        self.connection.commit()
        await self.increment_servers_statistics()

    async def get_server_msgs_per_day(self, server_id):
        c = self.connection.cursor()
        c.execute("SELECT msgs_per_day FROM servers WHERE server_id = ?", (server_id,))
        row = c.fetchone()
        return row[0] if row else 0

    async def add_server_interactions_count(self, serverID):
        c = self.connection.cursor()
        c.execute("UPDATE servers SET total_interactions = total_interactions + 1 WHERE server_id = ?", (serverID,))
        self.connection.commit()

    async def increment_servers_statistics(self):
        c = self.connection.cursor()
        c.execute("UPDATE statistics SET current_servers_total = current_servers_total + 1")
        self.connection.commit()

    async def decrement_servers_statistics(self):
        c = self.connection.cursor()
        c.execute("UPDATE statistics SET current_servers_total = MAX(0, current_servers_total - 1)")
        self.connection.commit()

    async def get_server_ids(self):
        c = self.connection.cursor()
        c.execute("SELECT server_id FROM servers")
        return [row[0] for row in c.fetchall()]

    async def on_guild_update(self, before, after):
        c = self.connection.cursor()
        if str(before.name) != str(after.name):
            c.execute("UPDATE servers SET name = ? WHERE server_id = ?", (str(after.name), str(after.id)))
        if str(before.owner) != str(after.owner):
            c.execute("UPDATE servers SET server_owner_name = ?, server_owner_id = ? WHERE server_id = ?",
                      (str(after.owner), str(after.owner_id), str(after.id)))
        self.connection.commit()

    async def user_name_update(self, before, after):
        pass

    async def update_server_prefix(self, serverID, prefix):
        c = self.connection.cursor()
        c.execute("INSERT OR IGNORE INTO servers_config (server_id) VALUES (?)", (serverID,))
        c.execute("UPDATE servers_config SET prefix = ? WHERE server_id = ?", (prefix, serverID))
        self.connection.commit()

    async def get_server_channel_id_to_spam(self, serverID):
        c = self.connection.cursor()
        c.execute("SELECT channel_id_to_spam FROM servers_config WHERE server_id = ?", (serverID,))
        row = c.fetchone()
        return row[0] if row else None

    async def update_server_channel_id_to_spam(self, serverID, channelID):
        c = self.connection.cursor()
        c.execute("INSERT OR IGNORE INTO servers_config (server_id) VALUES (?)", (serverID,))
        c.execute("UPDATE servers_config SET channel_id_to_spam = ? WHERE server_id = ?", (channelID, serverID))
        self.connection.commit()

    async def get_everyones_collection(self):
        c = self.connection.cursor()
        c.execute("""
            SELECT card.rarity, SUM(users_cards.amount) FROM pokemon_cards AS card
            JOIN users_cards ON users_cards.pokemon_card_id = card.id
            GROUP BY card.rarity
        """)
        rarities = dict(c.fetchall())
        c.execute("""
            SELECT card.super_type, SUM(users_cards.amount) FROM pokemon_cards AS card
            JOIN users_cards ON users_cards.pokemon_card_id = card.id
            GROUP BY card.super_type
        """)
        supertypes = dict(c.fetchall())
        c.execute("SELECT SUM(amount) FROM users_cards")
        total = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(id) FROM pokemon_cards")
        bot_total = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT pokemon_card_id) FROM users_cards")
        unique = c.fetchone()[0]
        percent = round(unique / bot_total * 100, 2) if bot_total > 0 else 0
        return {'rarity': rarities, 'supertype': supertypes, 'total': total, 'percent': percent}

    async def get_global_stats(self):
        c = self.connection.cursor()
        c.execute("SELECT * FROM statistics")
        return c.fetchone()

    async def get_total_cards_bot(self):
        c = self.connection.cursor()
        c.execute("SELECT COUNT(id) FROM pokemon_cards")
        return c.fetchone()[0]

    async def get_unique_total_cards_all(self):
        c = self.connection.cursor()
        c.execute("SELECT COUNT(DISTINCT pokemon_card_id) FROM users_cards")
        return c.fetchone()[0]

    async def get_bot_collection(self):
        c = self.connection.cursor()
        c.execute("SELECT rarity, COUNT(rarity) FROM pokemon_cards GROUP BY rarity")
        rarities = dict(c.fetchall())
        c.execute("SELECT super_type, COUNT(super_type) FROM pokemon_cards GROUP BY super_type")
        supertypes = dict(c.fetchall())
        c.execute("SELECT COUNT(id) FROM pokemon_cards")
        total = c.fetchone()[0]
        return rarities, supertypes, total

    async def get_user_stats(self, user_id):
        c = self.connection.cursor()
        c.execute("""
            SELECT rarity, SUM(users_cards.amount) FROM pokemon_cards
            JOIN users_cards ON users_cards.pokemon_card_id = pokemon_cards.id
            WHERE users_cards.user_id = ? GROUP BY rarity
        """, (user_id,))
        rows = c.fetchall()
        rarity_dict = {r[0]: r[1] for r in rows}
        total = sum(rarity_dict.values()) if rarity_dict else 0
        c.execute("SELECT COUNT(id) FROM pokemon_cards")
        bot_total = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT pokemon_card_id) FROM users_cards WHERE user_id = ?", (user_id,))
        unique = c.fetchone()[0]
        percent = (unique / bot_total * 100) if bot_total > 0 else 0
        return rarity_dict, total, percent

    async def get_total_cards_user(self, user_id):
        c = self.connection.cursor()
        c.execute("SELECT SUM(amount) FROM users_cards WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return row[0] or 0

    async def get_total_unique_cards_user(self, user_id):
        c = self.connection.cursor()
        c.execute("SELECT COUNT(pokemon_card_id) FROM users_cards WHERE user_id = ?", (user_id,))
        return c.fetchone()[0]

    async def get_money(self, user):
        c = self.connection.cursor()
        c.execute("SELECT money FROM users WHERE user_id = ?", (str(user.id),))
        row = c.fetchone()
        return row[0] if row else 0

    async def add_user(self, user):
        now = datetime.datetime.now().isoformat()
        c = self.connection.cursor()
        c.execute("""
            INSERT OR IGNORE INTO users (user_id, name, money, total_interactions, joined_at)
            VALUES (?, ?, ?, ?, ?)
        """, (str(user.id), str(user), 0, 0, now))
        self.connection.commit()
        await self.increment_users_statistics()

    async def increment_users_statistics(self):
        c = self.connection.cursor()
        c.execute("UPDATE statistics SET current_users_total = current_users_total + 1")
        self.connection.commit()

    async def buy(self, user, item):
        from helpers import constants

        # Find the store item by name (case-insensitive)
        store_item = None
        for si in constants.STORE:
            if si['name'].lower() == item.lower():
                store_item = si
                break
        if not store_item:
            return None

        # Ensure user exists in the database before checking money
        await self.add_user(user)

        # Check the user has enough money
        current_money = await self.get_money(user)
        if current_money < store_item['cost']:
            return None

        # Deduct the cost
        await self.subtract_money(user, store_item['cost'])

        cards = []
        item_name = store_item['name']

        # ── Single-rarity purchases (Common / Uncommon / Rare) ──
        if item_name in ('Common', 'Uncommon', 'Rare'):
            card = await self.get_rng_cards(rarity=item_name)
            if card:
                await self.add_user_card(user, card['id'])
                cards.append(card)
            return cards

        # ── Booster packs — 10 cards from a specific series ──
        series = item_name
        # 6 Common cards
        for _ in range(6):
            card = await self._get_card_for_pack(series, 'Common')
            if card:
                await self.add_user_card(user, card['id'])
                cards.append(card)
        # 3 Uncommon cards
        for _ in range(3):
            card = await self._get_card_for_pack(series, 'Uncommon')
            if card:
                await self.add_user_card(user, card['id'])
                cards.append(card)
        # 1 Rare+ card
        card = await self._get_card_for_pack(series, rare_plus=True)
        if card:
            await self.add_user_card(user, card['id'])
            cards.append(card)

        return cards

    async def _get_card_for_pack(self, series=None, rarity=None, rare_plus=False):
        """Pick a random card by series and/or rarity. Falls back to any series if needed."""
        c = self.connection.cursor()
        if rare_plus:
            # Any rarity that is NOT Common or Uncommon
            c.execute("""
                SELECT name, rarity, series, id, types FROM pokemon_cards
                WHERE series = ? AND obtainable = 'yes'
                AND rarity NOT IN ('Common', 'Uncommon', 'None')
                ORDER BY RANDOM() LIMIT 1
            """, (series,))
            row = c.fetchone()
            if not row:
                # Fallback: any rare+ from any series
                c.execute("""
                    SELECT name, rarity, series, id, types FROM pokemon_cards
                    WHERE obtainable = 'yes'
                    AND rarity NOT IN ('Common', 'Uncommon', 'None')
                    ORDER BY RANDOM() LIMIT 1
                """)
                row = c.fetchone()
        elif rarity and series:
            c.execute("""
                SELECT name, rarity, series, id, types FROM pokemon_cards
                WHERE series = ? AND rarity = ? AND obtainable = 'yes'
                ORDER BY RANDOM() LIMIT 1
            """, (series, rarity))
            row = c.fetchone()
            if not row:
                # Fallback: any series with this rarity
                c.execute("""
                    SELECT name, rarity, series, id, types FROM pokemon_cards
                    WHERE rarity = ? AND obtainable = 'yes'
                    ORDER BY RANDOM() LIMIT 1
                """, (rarity,))
                row = c.fetchone()
        else:
            c.execute("""
                SELECT name, rarity, series, id, types FROM pokemon_cards
                WHERE obtainable = 'yes' ORDER BY RANDOM() LIMIT 1
            """)
            row = c.fetchone()
        if row:
            return {"name": row[0], "rarity": row[1], "series": row[2], "id": row[3], "types": row[4]}
        return None

    async def get_rng_cards(self, rarity=None):
        c = self.connection.cursor()
        if rarity:
            c.execute("""
                SELECT name, rarity, series, id, types FROM pokemon_cards
                WHERE rarity = ? AND obtainable = 'yes' ORDER BY RANDOM() LIMIT 1
            """, (rarity,))
        else:
            c.execute("""
                SELECT name, rarity, series, id, types FROM pokemon_cards
                WHERE obtainable = 'yes' ORDER BY RANDOM() LIMIT 1
            """)
        row = c.fetchone()
        if row:
            return {"name": row[0], "rarity": row[1], "series": row[2], "id": row[3], "types": row[4]}
        return None

    async def add_user_card(self, user, card_id):
        c = self.connection.cursor()
        c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user.id), card_id))
        row = c.fetchone()
        if row:
            c.execute("UPDATE users_cards SET amount = amount + 1 WHERE user_id = ? AND pokemon_card_id = ?",
                      (str(user.id), card_id))
        else:
            c.execute("INSERT INTO users_cards (user_id, pokemon_card_id, amount) VALUES (?, ?, 1)",
                      (str(user.id), card_id))
        self.connection.commit()

    async def get_row_from_users(self, user_id):
        c = self.connection.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return c.fetchone()

    async def get_row_from_users_cards(self, user_id, card_id):
        c = self.connection.cursor()
        c.execute("SELECT * FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user_id), card_id))
        return c.fetchone()

    async def increment_card_statistics(self):
        c = self.connection.cursor()
        c.execute("UPDATE statistics SET current_cards_total = current_cards_total + 1, cards_earned_total = cards_earned_total + 1")
        self.connection.commit()

    async def increment_users_card(self, user_id, card_id):
        c = self.connection.cursor()
        c.execute("UPDATE users_cards SET amount = amount + 1 WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user_id), card_id))
        self.connection.commit()

    async def get_market(self, args=None):
        c = self.connection.cursor()
        if args:
            pass
        c.execute("SELECT id, cost, rarity, card_name, card_id, amount FROM market")
        return c.fetchall()

    async def get_card_info(self, card_id):
        c = self.connection.cursor()
        c.execute("SELECT name, id FROM custom_cards WHERE id = ?", (card_id,))
        row = c.fetchone()
        if row:
            return {"name": row[0], "id": row[1], "custom": True}
        c.execute("SELECT name, rarity, id FROM pokemon_cards WHERE id = ?", (card_id,))
        row = c.fetchone()
        if row:
            return {"name": row[0], "rarity": row[1], "id": row[2]}
        return None

    async def remove_card(self, user, card_id, amount=1):
        c = self.connection.cursor()
        c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user.id), card_id))
        row = c.fetchone()
        if row and row[0] <= amount:
            c.execute("DELETE FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                      (str(user.id), card_id))
        else:
            c.execute("UPDATE users_cards SET amount = amount - ? WHERE user_id = ? AND pokemon_card_id = ?",
                      (amount, str(user.id), card_id))
        self.connection.commit()

    async def decrement_card(self, user_id, card_id, amount=1):
        uid = str(user_id.id) if hasattr(user_id, 'id') else str(user_id)
        c = self.connection.cursor()
        c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (uid, card_id))
        row = c.fetchone()
        if row and row[0] <= amount:
            c.execute("DELETE FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                      (uid, card_id))
        else:
            c.execute("UPDATE users_cards SET amount = amount - ? WHERE user_id = ? AND pokemon_card_id = ?",
                      (amount, uid, card_id))
        self.connection.commit()

    async def add_to_market(self, user, card_id, cost, rarity, card_name, amount):
        c = self.connection.cursor()
        c.execute("""
            INSERT INTO market (cost, card_name, card_id, amount, owner_id, rarity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cost, card_name, card_id, amount, str(user.id), rarity))
        self.connection.commit()
        return True

    async def get_market_listing(self, market_id):
        c = self.connection.cursor()
        c.execute("SELECT id, cost, rarity, card_name, card_id, amount FROM market WHERE id = ?", (market_id,))
        row = c.fetchone()
        if row:
            return {"id": row[0], "cost": row[1], "rarity": row[2], "card_name": row[3], "card_id": row[4], "amount": row[5]}
        return None

    async def get_market_listings(self, args=None):
        c = self.connection.cursor()
        if args and "owner_id" in args:
            c.execute("SELECT id, cost, rarity, card_name, card_id, amount FROM market WHERE owner_id = ?",
                      (args["owner_id"],))
        else:
            c.execute("SELECT id, cost, rarity, card_name, card_id, amount FROM market")
        return c.fetchall()

    async def get_custom_cards(self, user_id):
        c = self.connection.cursor()
        c.execute("""
            SELECT custom_cards.id, custom_cards.name FROM custom_cards
            JOIN users_cards ON users_cards.pokemon_card_id = custom_cards.id
            WHERE users_cards.user_id = ?
        """, (str(user_id),))
        return c.fetchall()

    async def get_user_sort(self, user_id):
        uid = str(user_id.id) if hasattr(user_id, 'id') else str(user_id)
        c = self.connection.cursor()
        c.execute("SELECT sort FROM users WHERE user_id = ?", (uid,))
        row = c.fetchone()
        return row[0] if row else None

    async def update_user_sort(self, user_id, sort):
        uid = str(user_id.id) if hasattr(user_id, 'id') else str(user_id)
        c = self.connection.cursor()
        c.execute("UPDATE users SET sort = ? WHERE user_id = ?", (sort, uid))
        self.connection.commit()

    async def get_all_cards(self):
        c = self.connection.cursor()
        c.execute("SELECT name, rarity, series, id, types FROM pokemon_cards")
        return [{"name": r[0], "rarity": r[1], "series": r[2], "id": r[3], "types": r[4]} for r in c.fetchall()]

    async def get_dex(self, user_id):
        uid = str(user_id.id) if hasattr(user_id, 'id') else str(user_id)
        c = self.connection.cursor()
        c.execute("SELECT DISTINCT pokemon_card_id FROM users_cards WHERE user_id = ?", (uid,))
        return {row[0] for row in c.fetchall()}

    def _build_where_conditions(self, queries):
        """Build WHERE clause parts and params from a queries dict."""
        parts = []
        params = []
        for key, val in queries.items():
            if isinstance(val, tuple):
                placeholders = ','.join(['?'] * len(val))
                parts.append(f"{key} IN ({placeholders})")
                params.extend(val)
            elif isinstance(val, str) and val[:1] in ('>', '<', '='):
                parts.append(f"{key} {val}")
            else:
                parts.append(f"{key} LIKE ?")
                params.append(val)
        return parts, params

    def _get_user_cards_sort_sql(self, sort):
        """Convert sort string (e.g. 'amount,rarity') to SQL ORDER BY clause."""
        if not sort:
            return "users_cards.amount DESC"
        parts = []
        for crit in sort.split(','):
            crit = crit.strip()
            if crit == 'amount':
                parts.append("users_cards.amount DESC")
            elif crit == 'name':
                parts.append("pokemon_cards.name ASC")
            elif crit == 'id':
                parts.append("pokemon_cards.id ASC")
            elif crit == 'series':
                parts.append("""CASE pokemon_cards.series
                    WHEN 'Sword & Shield' THEN 1 WHEN 'Sun & Moon' THEN 2 WHEN 'XY' THEN 3
                    WHEN 'Black & White' THEN 4 WHEN 'HeartGold & SoulSilver' THEN 5
                    WHEN 'Platinum' THEN 6 WHEN 'POP' THEN 7 WHEN 'Diamond & Pearl' THEN 8
                    WHEN 'EX' THEN 9 WHEN 'E-Card' THEN 10 WHEN 'Neo' THEN 11
                    WHEN 'Gym' THEN 12 WHEN 'Base' THEN 13 ELSE 999 END ASC""")
            elif crit == 'rarity':
                parts.append("""CASE pokemon_cards.rarity
                    WHEN 'LEGEND' THEN 1 WHEN 'Rare Rainbow' THEN 2 WHEN 'VM' THEN 3
                    WHEN 'V' THEN 5 WHEN 'Shining' THEN 6 WHEN 'Amazing Rare' THEN 7
                    WHEN 'BREAK' THEN 10 WHEN 'Rare Secret' THEN 11 WHEN 'GX' THEN 12
                    WHEN 'EX' THEN 13 WHEN 'Rare Ultra' THEN 14 WHEN 'Rare Holo' THEN 15
                    WHEN 'Rare' THEN 16 WHEN 'Uncommon' THEN 17 WHEN 'Common' THEN 18
                    ELSE 19 END ASC""")
        return ', '.join(parts) if parts else "users_cards.amount DESC"

    async def get_marketV2(self, skip=0, limit=20, queries=None, sort=False):
        c = self.connection.cursor()
        base = """
            SELECT market.id, market.cost, market.rarity, market.card_name,
                   market.card_id, market.amount, market.owner_id,
                   pokemon_cards.name
            FROM market
            JOIN pokemon_cards ON pokemon_cards.id = market.card_id
        """
        params = []
        if queries:
            where_parts, extra_params = self._build_where_conditions(queries)
            if where_parts:
                base += " WHERE " + " AND ".join(where_parts)
                params.extend(extra_params)
        if sort:
            base += " ORDER BY market.cost ASC"
        base += " LIMIT ? OFFSET ?"
        params.extend([limit, skip])
        c.execute(base, params)
        rows = c.fetchall()
        return [{"market_id": r[0], "cost": r[1], "rarity": r[2], "card_name": r[3],
                 "card_id": r[4], "amount": r[5], "owner_id": r[6], "name": r[7]}
                for r in rows]

    async def get_market_count(self, queries=None):
        c = self.connection.cursor()
        base = """
            SELECT COUNT(*) FROM market
            JOIN pokemon_cards ON pokemon_cards.id = market.card_id
        """
        params = []
        if queries:
            where_parts, extra_params = self._build_where_conditions(queries)
            if where_parts:
                base += " WHERE " + " AND ".join(where_parts)
                params.extend(extra_params)
        c.execute(base, params)
        return c.fetchone()[0]

    async def get_user_cardsV2(self, user_id, skip=0, limit=20, queries=None, sort=None):
        uid = str(user_id.id) if hasattr(user_id, 'id') else str(user_id)
        c = self.connection.cursor()
        base = """
            SELECT pokemon_cards.name, pokemon_cards.rarity, pokemon_cards.series,
                   pokemon_cards.id, users_cards.amount, pokemon_cards.types
            FROM pokemon_cards
            JOIN users_cards ON users_cards.pokemon_card_id = pokemon_cards.id
            WHERE users_cards.user_id = ?
        """
        params = [uid]
        if queries:
            where_parts, extra_params = self._build_where_conditions(queries)
            if where_parts:
                base += " AND " + " AND ".join(where_parts)
                params.extend(extra_params)
        order = self._get_user_cards_sort_sql(sort)
        base += f" ORDER BY {order} LIMIT ? OFFSET ?"
        params.extend([limit, skip])
        c.execute(base, params)
        rows = c.fetchall()
        return [{"name": r[0], "rarity": r[1], "series": r[2], "id": r[3],
                 "amount": r[4], "types": r[5]} for r in rows]

    async def get_user_cards_count(self, user_id, queries=None):
        uid = str(user_id.id) if hasattr(user_id, 'id') else str(user_id)
        c = self.connection.cursor()
        base = """
            SELECT COUNT(*) FROM pokemon_cards
            JOIN users_cards ON users_cards.pokemon_card_id = pokemon_cards.id
            WHERE users_cards.user_id = ?
        """
        params = [uid]
        if queries:
            where_parts, extra_params = self._build_where_conditions(queries)
            if where_parts:
                base += " AND " + " AND ".join(where_parts)
                params.extend(extra_params)
        c.execute(base, params)
        return c.fetchone()[0]

    async def get_user_cards(self, user_id, page=1, limit=10):
        c = self.connection.cursor()
        offset = (page - 1) * limit
        c.execute("""
            SELECT name, rarity, series, id, users_cards.amount, types FROM pokemon_cards
            JOIN users_cards ON users_cards.pokemon_card_id = pokemon_cards.id
            WHERE users_cards.user_id = ? LIMIT ? OFFSET ?
        """, (str(user_id), limit, offset))
        return c.fetchall()

    async def remove_from_market(self, user, market_id):
        c = self.connection.cursor()
        c.execute("SELECT id, card_name, owner_id FROM market WHERE id = ?", (market_id,))
        row = c.fetchone()
        if not row:
            return False, None
        owner_id = row[2]
        card_name = row[1]
        if str(user.id) != str(owner_id):
            return False, None
        c.execute("DELETE FROM market WHERE id = ?", (market_id,))
        self.connection.commit()
        return True, card_name

    async def buy_from_market(self, user, market_id):
        c = self.connection.cursor()
        c.execute("SELECT id, cost, card_id, card_name, amount FROM market WHERE id = ?", (market_id,))
        row = c.fetchone()
        if not row:
            return False, "Market listing not found"
        listing_id, cost, card_id, card_name, card_amount = row
        user_money = await self.get_money(user)
        if user_money < cost:
            return False, f"You need **${cost}** but only have **${user_money}**"
        await self.subtract_money(user, cost)
        c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user.id), card_id))
        existing = c.fetchone()
        if existing:
            c.execute("UPDATE users_cards SET amount = amount + ? WHERE user_id = ? AND pokemon_card_id = ?",
                      (card_amount, str(user.id), card_id))
        else:
            c.execute("INSERT INTO users_cards (user_id, pokemon_card_id, amount) VALUES (?, ?, ?)",
                      (str(user.id), card_id, card_amount))
        c.execute("DELETE FROM market WHERE id = ?", (listing_id,))
        self.connection.commit()
        return True, f"Bought **{card_name}** (x{card_amount}) for **${cost}**"

    async def increment_user_interactions(self, userID):
        c = self.connection.cursor()
        c.execute("UPDATE users SET total_interactions = total_interactions + 1 WHERE user_id = ?", (userID,))
        self.connection.commit()

    async def get_support_tickets(self, args=None, skip=None, limit=None, count=False):
        c = self.connection.cursor()
        conditions = []
        params = []
        if args:
            if args.get("error"):
                conditions.append("flags LIKE '%error%'")
            if args.get("help"):
                conditions.append("flags LIKE '%help%'")
            if args.get("suggestion"):
                conditions.append("flags LIKE '%suggestion%'")
            if args.get("id"):
                conditions.append("id = ?")
                params.append(args["id"])
        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        if count:
            c.execute(f"SELECT COUNT(*) FROM support{where_clause}", params)
            return c.fetchone()[0]
        stmt = f"SELECT id, user_id, flags, message FROM support{where_clause}"
        if limit is not None and skip is not None:
            stmt += " LIMIT ? OFFSET ?"
            params.extend([limit, skip])
        elif limit is not None:
            stmt += " LIMIT ?"
            params.append(limit)
        c.execute(stmt, params)
        rows = c.fetchall()
        return [{"id": r[0], "user_id": r[1], "flags": r[2], "message": r[3]} for r in rows]

    async def get_daily(self, user):
        now = datetime.datetime.now()
        # Ensure user exists before giving daily reward
        await self.add_user(user)
        c = self.connection.cursor()
        c.execute("SELECT redeemed_at FROM daily WHERE user_id = ?", (str(user.id),))
        row = c.fetchone()
        if row:
            redeemed = datetime.datetime.fromisoformat(row[0])
            if (now - redeemed).total_seconds() < 86400:
                # Calculate remaining time
                remaining = 86400 - (now - redeemed).total_seconds()
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                return False, f"{hours}h {minutes}m"
            c.execute("UPDATE daily SET redeemed_at = ? WHERE user_id = ?", (now.isoformat(), str(user.id)))
        else:
            c.execute("INSERT INTO daily (user_id, redeemed_at) VALUES (?, ?)", (str(user.id), now.isoformat()))
        c.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (DAILY_MONEY, str(user.id)))
        # Give a random card as well
        card = await self.get_rng_cards()
        if card:
            await self.add_user_card(user, card['id'])
        self.connection.commit()
        return True, card

    async def add_money(self, user, amount):
        c = self.connection.cursor()
        c.execute("SELECT money FROM users WHERE user_id = ?", (str(user.id),))
        row = c.fetchone()
        if row:
            c.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (amount, str(user.id)))
        else:
            now = datetime.datetime.now().isoformat()
            c.execute("INSERT INTO users (user_id, name, money, total_interactions, joined_at) VALUES (?, ?, ?, ?, ?)",
                      (str(user.id), str(user), amount, 0, now))
        self.connection.commit()

    async def subtract_money(self, user, amount):
        c = self.connection.cursor()
        c.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (amount, str(user.id)))
        self.connection.commit()

    async def set_money(self, user, amount):
        c = self.connection.cursor()
        c.execute("SELECT money FROM users WHERE user_id = ?", (str(user.id),))
        row = c.fetchone()
        if row:
            c.execute("UPDATE users SET money = ? WHERE user_id = ?", (amount, str(user.id)))
        else:
            now = datetime.datetime.now().isoformat()
            c.execute("""
                INSERT INTO users (user_id, name, money, total_interactions, joined_at)
                VALUES (?, ?, ?, ?, ?)
            """, (str(user.id), str(user), amount, 0, now))
        self.connection.commit()

    async def remove_money(self, user, amount):
        c = self.connection.cursor()
        c.execute("UPDATE users SET money = max(0, money - ?) WHERE user_id = ?", (amount, str(user.id)))
        self.connection.commit()

    async def ban_user(self, user_id, reason, banned_by):
        now = datetime.datetime.now().isoformat()
        c = self.connection.cursor()
        c.execute("""
            INSERT OR REPLACE INTO banned_users (user_id, banned_at, reason, banned_by)
            VALUES (?, ?, ?, ?)
        """, (str(user_id), now, reason or "No reason given", str(banned_by)))
        self.connection.commit()

    async def unban_user(self, user_id):
        c = self.connection.cursor()
        c.execute("DELETE FROM banned_users WHERE user_id = ?", (str(user_id),))
        self.connection.commit()

    async def is_banned(self, user_id):
        c = self.connection.cursor()
        c.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (str(user_id),))
        return c.fetchone() is not None

    async def get_banned_users(self):
        c = self.connection.cursor()
        c.execute("SELECT user_id, banned_at, reason, banned_by FROM banned_users ORDER BY banned_at DESC")
        rows = c.fetchall()
        return [{
            "user_id": r[0], "banned_at": r[1], "reason": r[2], "banned_by": r[3]
        } for r in rows]

    async def get_user_info(self, user_id):
        c = self.connection.cursor()
        c.execute("SELECT user_id, name, money, total_interactions, joined_at FROM users WHERE user_id = ?", (str(user_id),))
        row = c.fetchone()
        if not row:
            return None
        c.execute("SELECT COUNT(*) FROM users_cards WHERE user_id = ?", (str(user_id),))
        card_count = c.fetchone()[0]
        c.execute("SELECT SUM(amount) FROM users_cards WHERE user_id = ?", (str(user_id),))
        total_cards = c.fetchone()[0] or 0
        banned = await self.is_banned(user_id)
        return {
            "user_id": row[0], "name": row[1], "money": row[2],
            "interactions": row[3], "joined_at": row[4],
            "unique_cards": card_count, "total_cards": total_cards,
            "banned": banned
        }

    async def get_all_users_paginated(self, page=1, limit=20):
        offset = (page - 1) * limit
        c = self.connection.cursor()
        c.execute("""
            SELECT user_id, name, money, total_interactions, joined_at
            FROM users ORDER BY money DESC LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = c.fetchall()
        return [{
            "user_id": r[0], "name": r[1], "money": r[2],
            "interactions": r[3], "joined_at": r[4]
        } for r in rows]

    async def count_all_users(self):
        c = self.connection.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        return c.fetchone()[0]

    async def get_card_by_id(self, card_id):
        c = self.connection.cursor()
        c.execute("SELECT id, name, rarity, series FROM pokemon_cards WHERE id = ?", (card_id,))
        row = c.fetchone()
        if row:
            return {"id": row[0], "name": row[1], "rarity": row[2], "series": row[3]}
        return None

    async def search_cards_by_name(self, name):
        c = self.connection.cursor()
        c.execute("""
            SELECT id, name, rarity, series FROM pokemon_cards
            WHERE name LIKE ? LIMIT 10
        """, (f"%{name}%",))
        return [{"id": r[0], "name": r[1], "rarity": r[2], "series": r[3]} for r in c.fetchall()]

    async def add_card_to_user(self, user_id, card_id):
        c = self.connection.cursor()
        c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user_id), card_id))
        row = c.fetchone()
        if row:
            c.execute("UPDATE users_cards SET amount = amount + 1 WHERE user_id = ? AND pokemon_card_id = ?",
                      (str(user_id), card_id))
        else:
            c.execute("INSERT INTO users_cards (user_id, pokemon_card_id, amount) VALUES (?, ?, 1)",
                      (str(user_id), card_id))
        self.connection.commit()

    async def remove_card_from_user(self, user_id, card_id):
        c = self.connection.cursor()
        c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user_id), card_id))
        row = c.fetchone()
        if not row:
            return False
        if row[0] > 1:
            c.execute("UPDATE users_cards SET amount = amount - 1 WHERE user_id = ? AND pokemon_card_id = ?",
                      (str(user_id), card_id))
        else:
            c.execute("DELETE FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                      (str(user_id), card_id))
        self.connection.commit()
        return True

    async def reset_daily(self, user_id):
        c = self.connection.cursor()
        c.execute("DELETE FROM daily WHERE user_id = ?", (str(user_id),))
        self.connection.commit()

    async def random_card(self, rarity=None, type_=None):
        c = self.connection.cursor()
        conditions = ["obtainable = 'yes'"]
        params = []
        if rarity and rarity.lower() == 'rare+':
            conditions.append("rarity NOT IN ('Common', 'Uncommon', 'None')")
        elif rarity:
            conditions.append("rarity = ?")
            params.append(rarity)
        if type_:
            conditions.append("types LIKE ?")
            params.append(f"%{type_}%")
        query = ("SELECT name, rarity, series, id, types FROM pokemon_cards"
                 f" WHERE {' AND '.join(conditions)} ORDER BY RANDOM() LIMIT 1")
        c.execute(query, params)
        row = c.fetchone()
        if row:
            return {"name": row[0], "rarity": row[1], "series": row[2], "id": row[3], "types": row[4]}
        # Fallback: any obtainable card
        return await self.get_rng_cards()

    async def get_random_card(self):
        c = self.connection.cursor()
        c.execute("SELECT id, name, rarity FROM pokemon_cards WHERE obtainable = 'yes' ORDER BY RANDOM() LIMIT 1")
        row = c.fetchone()
        if row:
            card = {"id": row[0], "name": row[1], "rarity": row[2]}
            if card["rarity"] not in ["Common", "None", "Rare", "Uncommon"] or "jp" in card["id"]:
                row = c.execute("SELECT id, name, rarity FROM pokemon_cards WHERE obtainable = 'yes' ORDER BY RANDOM() LIMIT 1").fetchone()
                if row:
                    card = {"id": row[0], "name": row[1], "rarity": row[2]}
            return card
        raise ValueError("Unable to get random card")

    async def get_user_card(self, user, card_id):
        c = self.connection.cursor()
        c.execute("SELECT pokemon_card_id, amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user.id), card_id))
        row = c.fetchone()
        if row:
            return {"id": row[0], "amount": row[1]}
        return {}

    async def get_drop(self, channel_id):
        c = self.connection.cursor()
        c.execute("SELECT name, id FROM current_drop WHERE channel_id = ?", (channel_id,))
        row = c.fetchone()
        if row:
            return {"name": row[0], "id": row[1]}
        return None

    async def redeem_drop(self, name, channel_id, user):
        c = self.connection.cursor()
        c.execute("SELECT name, id FROM current_drop WHERE channel_id = ?", (channel_id,))
        row = c.fetchone()
        if not row:
            return 3, None, None
        if name.lower() == row[0].lower() or name.lower().replace("'", "'") == row[0].lower().replace("'", "'"):
            c.execute("DELETE FROM current_drop WHERE channel_id = ?", (channel_id,))
            self.connection.commit()
            await self.add_user_card(user, row[1])
            return True, row[0], row[1]
        else:
            right = row[0].lower().replace("'", "'")
            answer = name.lower().replace("'", "'")
            diff = sum(1 for a, b in zip(right, answer) if a != b)
            diff += abs(len(right) - len(answer))
            return False, diff, row[1]

    async def add_server_messages_count(self, serverID):
        c = self.connection.cursor()
        c.execute("UPDATE servers SET messages = messages + 1 WHERE server_id = ?", (serverID,))
        self.connection.commit()

    async def get_server_messages_count(self, server_id):
        c = self.connection.cursor()
        c.execute("SELECT messages FROM servers WHERE server_id = ?", (server_id,))
        row = c.fetchone()
        return row[0] if row else None

    async def store_drop(self, card, channelID):
        c = self.connection.cursor()
        c.execute("DELETE FROM current_drop WHERE channel_id = ?", (channelID,))
        c.execute("INSERT OR REPLACE INTO current_drop (id, name, channel_id) VALUES (?, ?, ?)",
                  (card["id"], card["name"], channelID))
        self.connection.commit()

    async def is_valid_card(self, card_id):
        c = self.connection.cursor()
        c.execute("SELECT id, name, types, rarity, series FROM pokemon_cards WHERE id = ?", (card_id,))
        row = c.fetchone()
        if row:
            return {"id": row[0], "name": row[1], "types": row[2], "rarity": row[3], "series": row[4]}
        return False

    async def give_card_to_user(self, giver, card_id, recipient):
        try:
            c = self.connection.cursor()
            c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                      (str(giver.id), card_id))
            row = c.fetchone()
            if not row or row[0] == 0:
                return False
            if row[0] - 1 == 0:
                c.execute("DELETE FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                          (str(giver.id), card_id))
            else:
                c.execute("UPDATE users_cards SET amount = amount - 1 WHERE user_id = ? AND pokemon_card_id = ?",
                          (str(giver.id), card_id))
            user_table = await self.get_row_from_users(str(recipient.id))
            if user_table:
                users_cards = await self.get_row_from_users_cards(recipient.id, card_id)
                if users_cards:
                    await self.increment_users_card(recipient.id, card_id)
                else:
                    await self.insert_users_card(recipient.id, card_id)
            else:
                await self.add_user(recipient)
                await self.insert_users_card(str(recipient.id), card_id)
            self.connection.commit()
            return True
        except Exception:
            return False

    async def insert_users_card(self, user_id, card_id, amount=1):
        c = self.connection.cursor()
        c.execute("INSERT INTO users_cards (user_id, pokemon_card_id, amount) VALUES (?, ?, ?)",
                  (str(user_id), card_id, amount))
        self.connection.commit()

    async def give_money(self, giver, amount, receiver):
        try:
            c = self.connection.cursor()
            c.execute("SELECT money FROM users WHERE user_id = ?", (str(giver.id),))
            row = c.fetchone()
            giver_money = row[0] if row else 0
            if giver_money - amount < 0:
                return False
            c.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (amount, str(giver.id)))
            self.connection.commit()
            await self.add_money(receiver, amount)
            return True
        except Exception:
            return False

    async def card_obtainability(self, status, rarity=None, series=None, types=None):
        c = self.connection.cursor()
        if rarity:
            for rare in rarity:
                c.execute("UPDATE pokemon_cards SET obtainable = ? WHERE rarity = ?", (status, rare))
        if series:
            for ser in series:
                c.execute("UPDATE pokemon_cards SET obtainable = ? WHERE series = ?", (status, ser))
        if types:
            for ty in types:
                c.execute("UPDATE pokemon_cards SET obtainable = ? WHERE types LIKE ?", (status, "%" + ty + "%"))
        self.connection.commit()

    async def get_obtainability(self, rarity):
        c = self.connection.cursor()
        c.execute("SELECT obtainable FROM pokemon_cards WHERE rarity = ? LIMIT 1", (rarity,))
        row = c.fetchone()
        return row[0] if row else "yes"
