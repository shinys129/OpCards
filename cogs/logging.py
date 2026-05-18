import logging
import os

from discord.ext import commands

formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")

os.makedirs("logs", exist_ok=True)

class Logging(commands.Cog):
    """Logs for dayz"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        cluster_name = getattr(self.bot, "cluster_name", "Main")
        self.log = logging.getLogger(f"Cluster#{cluster_name}")
        handler = logging.FileHandler(f"logs/commands-{cluster_name}.log")
        handler.setFormatter(formatter)
        self.log.handlers = [handler]

        dlog = logging.getLogger("discord")
        dhandler = logging.FileHandler(f"logs/discord-{self.bot.cluster_name}.log")
        dhandler.setFormatter(formatter)
        dlog.handlers = [dhandler]

        self.log.setLevel(logging.DEBUG)
        dlog.setLevel(logging.INFO)

async def setup(bot):
    await bot.add_cog(Logging(bot))
