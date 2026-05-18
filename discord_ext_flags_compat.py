"""
Compatibility shim for discord-ext-flags (which is no longer available).
This provides the add_flag decorator and flags.command wrapper so the bot's
cogs can load without the original package.

This version actually parses flags from message content, unlike the previous no-op shim.
"""

import functools
import inspect
from discord.ext import commands


class ArgumentParsingError(commands.UserInputError):
    """Raised when a flags command fails to parse arguments."""
    pass


def _get_metadata_target(func):
    """Return the object to store/read flag metadata from.

    When `add_flag` is applied BEFORE `command`, the target is `func` itself.
    When `add_flag` is applied AFTER `command`, the target is `func.callback`
    (since `func` is already a `discord.ext.commands.Command`).
    """
    if isinstance(func, commands.Command):
        return func.callback
    return func


def _parse_flags_from_content(ctx, func):
    """Parse flags from the message content according to the flag metadata."""
    content = ctx.message.content
    prefix = ctx.prefix or ""
    invoked = ctx.invoked_with or func.__name__

    # Remove prefix + command from content to get raw args
    cmd_part = prefix + invoked
    idx = content.find(cmd_part)
    if idx == -1:
        idx = content.lower().find(invoked.lower())
        if idx != -1:
            args_text = content[idx + len(invoked):].strip()
        else:
            args_text = ""
    else:
        args_text = content[idx + len(cmd_part):].strip()

    target = _get_metadata_target(func)
    flags_meta = getattr(target, '_flag_metadata', [])
    flags = {}

    # Initialize with defaults
    for meta in flags_meta:
        name = meta['name'].lstrip('-')
        default = meta.get('default')
        if meta.get('action') == 'store_true':
            flags[name] = False
        elif meta.get('action') == 'store_false':
            flags[name] = True
        else:
            flags[name] = default

    if not args_text:
        return flags

    tokens = args_text.split()

    positional_flags = [m for m in flags_meta if not m['name'].startswith('--')]
    positional_idx = 0
    i = 0

    while i < len(tokens):
        token = tokens[i]

        if token.startswith('--'):
            flag_name = token.lstrip('-')
            meta = next((m for m in flags_meta if m['name'].lstrip('-') == flag_name), None)
            if meta is None:
                i += 1
                continue

            i += 1  # move past flag name

            if meta.get('action') == 'store_true':
                flags[flag_name] = True
                continue
            elif meta.get('action') == 'store_false':
                flags[flag_name] = False
                continue

            values = []
            nargs = meta.get('nargs')

            if nargs == '?':
                if i < len(tokens) and not tokens[i].startswith('--'):
                    values.append(tokens[i])
                    i += 1
            elif nargs == '+':
                while i < len(tokens) and not tokens[i].startswith('--'):
                    values.append(tokens[i])
                    i += 1
            elif nargs == '*':
                while i < len(tokens) and not tokens[i].startswith('--'):
                    values.append(tokens[i])
                    i += 1
            elif isinstance(nargs, int):
                for _ in range(nargs):
                    if i < len(tokens) and not tokens[i].startswith('--'):
                        values.append(tokens[i])
                        i += 1
            else:
                if i < len(tokens) and not tokens[i].startswith('--'):
                    values.append(tokens[i])
                    i += 1

            flag_type = meta.get('type')
            if flag_type:
                converted = []
                for v in values:
                    try:
                        converted.append(flag_type(v))
                    except (ValueError, TypeError):
                        converted.append(v)
                values = converted

            if meta.get('action') == 'append':
                if flags.get(flag_name) is None:
                    flags[flag_name] = []
                flags[flag_name].append(values)
            elif meta.get('action') == 'append_const':
                if flags.get(flag_name) is None:
                    flags[flag_name] = []
                flags[flag_name].append(meta.get('const'))
            else:
                if len(values) == 1:
                    flags[flag_name] = values[0]
                else:
                    flags[flag_name] = values
        else:
            if positional_idx < len(positional_flags):
                meta = positional_flags[positional_idx]
                flag_name = meta['name'].lstrip('-')
                flag_type = meta.get('type')
                value = token
                if flag_type:
                    try:
                        value = flag_type(value)
                    except (ValueError, TypeError):
                        pass
                flags[flag_name] = value
                positional_idx += 1
                i += 1
            else:
                i += 1

    return flags


def add_flag(name, nargs=None, type=None, default=None, action=None, const=None):
    """Decorator that adds a flag parameter to a command.

    Works both before and after flags.command() is applied.
    """
    def decorator(func):
        target = _get_metadata_target(func)
        if not hasattr(target, '_flag_metadata'):
            target._flag_metadata = []
        target._flag_metadata.append({
            'name': name,
            'nargs': nargs,
            'type': type,
            'default': default,
            'action': action,
            'const': const,
        })
        return func
    return decorator


def command(*args, **kwargs):
    """Wrapper around discord.ext.commands.command that handles flags compat."""
    def decorator(func):
        target = _get_metadata_target(func)
        meta = getattr(target, '_flag_metadata', [])

        async def wrapper(self, ctx, *_ignored_args):
            flags = _parse_flags_from_content(ctx, wrapper)
            return await func(self, ctx, **flags)

        # Manually copy key attributes (but NOT __signature__ which
        # would hide *args from discord.py and make it drop extra tokens)
        wrapper.__name__ = func.__name__
        wrapper.__qualname__ = getattr(func, '__qualname__', func.__name__)
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__

        # Copy over flags metadata so other code can inspect it
        wrapper._flag_metadata = list(meta)
        return commands.command(*args, **kwargs)(wrapper)
    return decorator
