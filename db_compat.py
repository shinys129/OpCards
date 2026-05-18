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
        c.execute("INSERT OR REPLACE INTO servers_config (server_id, prefix) VALUES (?, ?)", (serverID, prefix))
        self.connection.commit()

    async def get_server_channel_id_to_spam(self, serverID):
        c = self.connection.cursor()
        c.execute("SELECT channel_id_to_spam FROM servers_config WHERE server_id = ?", (serverID,))
        row = c.fetchone()
        return row[0] if row else None

    async def update_server_channel_id_to_spam(self, serverID, channelID):
        c = self.connection.cursor()
        c.execute("INSERT OR REPLACE INTO servers_config (server_id, channel_id_to_spam) VALUES (?, ?)", (serverID, channelID))
        self.connection.commit()

    async def get_everyones_collection(self, page):
        c = self.connection.cursor()
        c.execute("""
            SELECT card.rarity, SUM(users_cards.amount) FROM pokemon_cards AS card
            JOIN users_cards ON users_cards.pokemon_card_id = card.id
            GROUP BY card.rarity
        """)
        return c.fetchall()

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
        return c.fetchall()

    async def get_user_stats(self, user_id):
        c = self.connection.cursor()
        c.execute("""
            SELECT rarity, SUM(users_cards.amount) FROM pokemon_cards
            JOIN users_cards ON users_cards.pokemon_card_id = pokemon_cards.id
            WHERE users_cards.user_id = ? GROUP BY rarity
        """, (user_id,))
        return c.fetchall()

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
        pass

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

    async def remove_card(self, user, card_id, amount):
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
        c = self.connection.cursor()
        c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user_id), card_id))
        row = c.fetchone()
        if row and row[0] <= amount:
            c.execute("DELETE FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                      (str(user_id), card_id))
        else:
            c.execute("UPDATE users_cards SET amount = amount - ? WHERE user_id = ? AND pokemon_card_id = ?",
                      (amount, str(user_id), card_id))
        self.connection.commit()

    async def add_to_market(self, user, card_id, cost, rarity, card_name, amount):
        c = self.connection.cursor()
        c.execute("""
            INSERT INTO market (cost, card_name, card_id, amount, owner_id, rarity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cost, card_name, card_id, amount, str(user.id), rarity))
        self.connection.commit()

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
        c = self.connection.cursor()
        c.execute("SELECT sort FROM users WHERE user_id = ?", (str(user_id),))
        row = c.fetchone()
        return row[0] if row else None

    async def update_user_sort(self, user_id, sort):
        c = self.connection.cursor()
        c.execute("UPDATE users SET sort = ? WHERE user_id = ?", (sort, str(user_id)))
        self.connection.commit()

    async def get_all_cards(self):
        c = self.connection.cursor()
        c.execute("SELECT name, rarity, series, id, types FROM pokemon_cards")
        return c.fetchall()

    async def get_dex(self, user_id):
        c = self.connection.cursor()
        c.execute("SELECT DISTINCT pokemon_card_id FROM users_cards WHERE user_id = ?", (str(user_id),))
        return c.fetchall()

    async def get_marketV2(self, args=None):
        c = self.connection.cursor()
        c.execute("""
            SELECT market.id, market.cost, market.rarity, market.card_name,
                   market.card_id, market.amount, market.owner_id,
                   pokemon_cards.name FROM market
            JOIN pokemon_cards ON pokemon_cards.id = market.card_id
        """)
        return c.fetchall()

    async def get_market_count(self, args=None):
        c = self.connection.cursor()
        c.execute("SELECT COUNT(*) FROM market")
        return c.fetchone()[0]

    async def get_user_cardsV2(self, user_id):
        c = self.connection.cursor()
        c.execute("""
            SELECT name, rarity, series, id, users_cards.amount, types FROM pokemon_cards
            JOIN users_cards ON users_cards.pokemon_card_id = pokemon_cards.id
            WHERE users_cards.user_id = ?
        """, (str(user_id),))
        return c.fetchall()

    async def get_user_cards_count(self, user_id):
        c = self.connection.cursor()
        c.execute("SELECT COUNT(*) FROM users_cards WHERE user_id = ?", (str(user_id),))
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

    async def remove_from_market(self, market, user=None):
        c = self.connection.cursor()
        c.execute("DELETE FROM market WHERE owner_id = ? AND id = ?",
                  (market["owner_id"], market["id"]))
        self.connection.commit()

    async def buy_from_market(self, market, user):
        c = self.connection.cursor()
        # Remove from market
        c.execute("DELETE FROM market WHERE id = ?", (market["id"],))
        # Add card to buyer
        c.execute("SELECT amount FROM users_cards WHERE user_id = ? AND pokemon_card_id = ?",
                  (str(user.id), market["card_id"]))
        row = c.fetchone()
        if row:
            c.execute("UPDATE users_cards SET amount = amount + ? WHERE user_id = ? AND pokemon_card_id = ?",
                      (market["amount"], str(user.id), market["card_id"]))
        else:
            c.execute("INSERT INTO users_cards (user_id, pokemon_card_id, amount) VALUES (?, ?, ?)",
                      (str(user.id), market["card_id"], market["amount"]))
        self.connection.commit()

    async def increment_user_interactions(self, userID):
        c = self.connection.cursor()
        c.execute("UPDATE users SET total_interactions = total_interactions + 1 WHERE user_id = ?", (userID,))
        self.connection.commit()

    async def get_support_tickets(self, args=None):
        c = self.connection.cursor()
        stmt = "SELECT id, user_id, flags, message FROM support"
        if args:
            conditions = []
            params = []
            if args.get("error"):
                conditions.append("flags LIKE '%error%'")
            if args.get("help"):
                conditions.append("flags LIKE '%help%'")
            if args.get("suggestion"):
                conditions.append("flags LIKE '%suggestion%'")
            if conditions:
                stmt += " WHERE " + " OR ".join(conditions)
            if args.get("id"):
                stmt += " AND id = ?" if conditions else " WHERE id = ?"
                params.append(args["id"])
        c.execute(stmt, params if 'params' in dir() else ())
        return c.fetchall()

    async def get_daily(self, user):
        now = datetime.datetime.now()
        c = self.connection.cursor()
        c.execute("SELECT redeemed_at FROM daily WHERE user_id = ?", (str(user.id),))
        row = c.fetchone()
        if row:
            redeemed = datetime.datetime.fromisoformat(row[0])
            if (now - redeemed).total_seconds() < 86400:
                return False
            c.execute("UPDATE daily SET redeemed_at = ? WHERE user_id = ?", (now.isoformat(), str(user.id)))
        else:
            c.execute("INSERT INTO daily (user_id, redeemed_at) VALUES (?, ?)", (str(user.id), now.isoformat()))
        c.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (DAILY_MONEY, str(user.id)))
        self.connection.commit()
        return True

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

    async def random_card(self, rarity=None):
        return await self.get_rng_cards(rarity)

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

    async def get_obtainability(self, card_id):
        c = self.connection.cursor()
        c.execute("SELECT obtainable FROM pokemon_cards WHERE id = ?", (card_id,))
        row = c.fetchone()
        return row[0] if row else "yes"
