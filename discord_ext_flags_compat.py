"""
Compatibility shim for discord-ext-flags (which is no longer available).
This provides the add_flag decorator and flags.command wrapper so the bot's
cogs can load without the original package.
"""

import functools
from discord.ext import commands


class ArgumentParsingError(commands.UserInputError):
    """Raised when a flags command fails to parse arguments."""
    pass


def add_flag(name, nargs=None, type=None, default=None, action=None):
    """Decorator that adds a flag parameter to a command. (no-op compat shim)"""
    def decorator(func):
        # Store flag metadata on the function for potential future use
        if not hasattr(func, '__flags__'):
            func.__flags__ = []
        func.__flags__.append({
            'name': name,
            'nargs': nargs,
            'type': type,
            'default': default,
            'action': action,
        })
        return func
    return decorator

def command(*args, **kwargs):
    """Wrapper around discord.ext.commands.command that handles flags compat."""
    def decorator(func):
        return commands.command(*args, **kwargs)(func)
    return decorator
