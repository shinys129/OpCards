# for database updates/inserts

import datetime
import random
from discord.ext import commands, tasks
import discord_ext_flags_compat as flags
from helpers import constants
from db_compat import DbSqlite

DAILY_MONEY = 200 # 200 base daily money, more if event
STORE = [ # 10 cards booster pack, 6 common, 3 uncommon, 1 rare and above, rare+ is 5th from bottom?
    {'name': 'Sword & Shield', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'Sun & Moon', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'XY', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'Black & White', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'HeartGold & SoulSilver', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'Platinum', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'Diamond & Pearl', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'EX', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'E-Card', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'Neo', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'POP', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'Base', 'cost': 900, 'description': 'Booster Pack (10 cards)'},
    {'name': 'Common', 'cost': 50, 'description': 'Random Common card'},
    {'name': 'Uncommon', 'cost': 100, 'description': 'Random Uncommon card'},
    {'name': 'Rare', 'cost': 300, 'description': 'Random Rare card'}
]

# TODO should clean up and merge similar functions together


class Db(commands.Cog, DbSqlite):
    def __init__(self, bot):
        self.bot = bot
        DbSqlite.__init__(self, bot)

    async def sort_list_of_dict(self, dictionary, criteria, skip = None, limit = None):
        # amount,rarity -> amount takes precedence, then sorts by rarity
        # rarity,amount -> rarity has precedence
        criteria = criteria.replace('rarity', 'rarityN').replace('amount', 'amountN').replace('series', 'seriesN')
        crit = criteria.split(',')
        # series should have recent be first
        series = {'Sword & Shield': 1, 'Sun & Moon': 2, 'XY': 3, 'Black & White': 4, 'HeartGold & SoulSilver': 5,
                    'Platinum': 6, 'POP': 7,'Diamond & Pearl': 8, 'EX': 9, 'E-Card': 10, 'Neo': 11,
                    'Gym': 12, 'Base': 13, 'IDK': 999}
        # rarity should have the most rare be first
        rarity = {'LEGEND': 1, 'Rare Rainbow': 2, 'VM': 3, 'V': 5, 'Shining': 6,
                    'Amazing Rare': 7, 'BREAK': 10,
                    'Rare Secret': 11, 'GX': 12, 'EX': 13, 'Rare Ultra': 14,
                    'Rare Holo': 15, 'Rare': 16, 'Uncommon': 17, 'Common': 18, 'None': 19}
        dictionary = [dict(item, **{'rarityN': rarity[item['rarity']]}) for item in dictionary] if 'rarityN' in criteria else dictionary
        dictionary = [dict(item, **{'seriesN': series[item['series']] if item['series'] in series else series['IDK']}) for item in dictionary] if 'seriesN' in criteria else dictionary
        dictionary = [dict(item, **{'amountN': item['amount'] * (-1)}) for item in dictionary] if 'amountN' in criteria else dictionary
        if len(crit) == 2:
            out = sorted(dictionary, key = lambda i: (i[crit[0]], i[crit[1]]))
        elif len(crit) == 1:
            out = sorted(dictionary, key = lambda i: i[crit[0]])
        else:
            out = sorted(dictionary, key = lambda i: i['amount'], reverse = True)
        if skip and limit:
            return out[skip:limit+skip]
        elif skip:
            return out[skip:]
        elif limit:
            return out[:limit]
        else:
            return out


async def setup(bot):
    await bot.add_cog(Db(bot))