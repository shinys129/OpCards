"""
SQLite database drop-in replacement for the MySQL-based Db cog.
Creates and populates all tables needed by the bot.
"""

import sqlite3
import datetime
import json
import os
import random

DB_PATH = os.environ.get("SQLITE_DB_PATH", "munchbot.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS servers (
            server_id TEXT PRIMARY KEY,
            name TEXT,
            server_owner_name TEXT,
            server_owner_id TEXT,
            region TEXT,
            joined_at TEXT,
            msgs_per_day INTEGER DEFAULT 0,
            total_interactions INTEGER DEFAULT 0,
            messages INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS servers_config (
            server_id TEXT PRIMARY KEY,
            prefix TEXT,
            channel_id_to_spam TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            money INTEGER DEFAULT 0,
            total_interactions INTEGER DEFAULT 0,
            joined_at TEXT,
            sort TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pokemon_cards (
            id TEXT PRIMARY KEY,
            name TEXT,
            national_pokedex_number INTEGER,
            types TEXT,
            sub_type TEXT,
            super_type TEXT,
            hp INTEGER,
            pc_number TEXT,
            artist TEXT,
            rarity TEXT,
            series TEXT,
            pc_set TEXT,
            set_code TEXT,
            retreat_cost TEXT,
            converted_retreat_cost INTEGER,
            pc_text TEXT,
            attacks TEXT,
            weakness TEXT,
            resistances TEXT,
            ability TEXT,
            ancient_trait TEXT,
            evolves_from TEXT,
            obtainable TEXT DEFAULT 'yes'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS users_cards (
            user_id TEXT,
            pokemon_card_id TEXT,
            amount INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, pokemon_card_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cost INTEGER,
            rarity TEXT,
            card_name TEXT,
            card_id TEXT,
            amount INTEGER,
            owner_id TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS statistics (
            current_servers_total INTEGER DEFAULT 0,
            current_users_total INTEGER DEFAULT 0,
            current_cards_total INTEGER DEFAULT 0,
            current_money_total INTEGER DEFAULT 0,
            cards_earned_total INTEGER DEFAULT 0,
            money_earned_total INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily (
            user_id TEXT PRIMARY KEY,
            redeemed_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS current_drop (
            id TEXT,
            name TEXT,
            channel_id TEXT PRIMARY KEY
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_cards (
            id TEXT PRIMARY KEY,
            name TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS support (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            flags TEXT,
            message TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id TEXT PRIMARY KEY,
            banned_at TEXT,
            reason TEXT,
            banned_by TEXT
        )
    """)

    # Seed statistics if empty
    c.execute("SELECT COUNT(*) FROM statistics")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO statistics DEFAULT VALUES")

    conn.commit()
    conn.close()

def load_cards_from_json():
    """Load pokemon cards from JSON data files if db is empty."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pokemon_cards")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    data_path = "database/pokemon_cards_202102101411.json"
    if not os.path.exists(data_path):
        conn.close()
        return

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cards = data.get("pokemon_cards", [])
    for card in cards:
        c.execute("""
            INSERT OR IGNORE INTO pokemon_cards (
                id, name, national_pokedex_number, types, sub_type, super_type,
                hp, pc_number, artist, rarity, series, pc_set, set_code,
                retreat_cost, converted_retreat_cost, pc_text, attacks,
                weakness, resistances, ability, ancient_trait, evolves_from, obtainable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card.get("id"),
            card.get("name"),
            card.get("national_pokedex_number"),
            card.get("types"),
            card.get("sub_type"),
            card.get("super_type"),
            card.get("hp"),
            card.get("pc_number"),
            card.get("artist"),
            card.get("rarity"),
            card.get("series"),
            card.get("pc_set"),
            card.get("set_code"),
            card.get("retreat_cost"),
            card.get("converted_retreat_cost"),
            card.get("pc_text"),
            card.get("attacks"),
            card.get("weakness"),
            card.get("resistances"),
            card.get("ability"),
            card.get("ancient_trait"),
            card.get("evolves_from"),
            card.get("obtainable", "yes"),
        ))

    # Load custom cards
    custom_path = "database/custom_cards_202102101411.json"
    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            custom = json.load(f)
        for card in custom.get("custom_cards", []):
            c.execute("INSERT OR IGNORE INTO custom_cards (id, name) VALUES (?, ?)",
                      (card.get("id"), card.get("name")))

    conn.commit()
    conn.close()
    print(f"Loaded {len(cards)} cards into SQLite database.")


def seed_database():
    init_db()
    load_cards_from_json()
