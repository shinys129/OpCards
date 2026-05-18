import re

with open('cogs/db.py', 'r') as f:
    content = f.read()

# Step 1: Replace all %s with ? inside execute calls
# We need to handle multiline execute calls

# Pattern for execute calls: find execute( ... ) blocks that contain %s
# We'll do a simpler approach: replace %s -> ? globally within SQL strings
# First, let's find all string literals and replace %s inside them

def fix_sql_strings(text):
    """Replace %s with ? inside SQL string literals, and [a,b] with (a,b) for execute params."""
    # Handle single-line execute calls with %s
    # Pattern: execute('... %s ...', [args])
    def repl_execute(match):
        before = match.group(1)
        sql = match.group(2)
        after_sql = match.group(3)
        params = match.group(4)
        end = match.group(5)

        # Replace %s in SQL
        sql = sql.replace('%s', '?')

        # Convert [args] to (args) for params
        params_stripped = params.strip()
        if params_stripped.startswith('[') and params_stripped.endswith(']'):
            params = '(' + params_stripped[1:-1] + ')'

        return before + sql + after_sql + params + end

    # Match: execute('...sql...', [params]) or execute("...sql...", [params])
    # The SQL can contain newlines
    text = re.sub(
        r"(execute\(['\"]\s*)(.+?)(\s*['\"]\s*,\s*)(\[[^\]]*\])(\s*\))",
        repl_execute,
        text,
        flags=re.DOTALL
    )

    # Handle triple-quoted strings
    text = re.sub(
        r"(execute\('''\s*)(.+?)(\s*'''\s*,\s*)(\[[^\]]*\])(\s*\))",
        repl_execute,
        text,
        flags=re.DOTALL
    )

    return text

# Apply the fix
content = fix_sql_strings(content)

# Step 2: Handle any remaining %s in SQL strings that might be in multiline formats
# Find all remaining %s not already replaced
remaining = content.count('%s')
if remaining > 0:
    print(f"Remaining %s after first pass: {remaining}")
    # More aggressive: find lines with execute that still have %s
    lines = content.split('\n')
    new_lines = []
    in_execute = False
    execute_lines = []

    for line in lines:
        if 'execute(' in line and '%s' in line:
            in_execute = True
        if in_execute:
            execute_lines.append(line)
            if ')' in line and line.count(')') >= line.count('('):
                # End of execute call - process it
                block = '\n'.join(execute_lines)
                # Replace %s with ?
                block = block.replace('%s', '?')
                # Try to find and convert [params] to (params)
                block = re.sub(r"\[([\w\s.,\(\)\[\]'\"_\-]+?)\]\s*\)", r"(\1))", block)
                new_lines.extend(block.split('\n'))
                in_execute = False
                execute_lines = []
            continue
        if not in_execute:
            new_lines.append(line)

    if in_execute:
        # Unclosed execute - just append
        new_lines.extend(execute_lines)

    content = '\n'.join(new_lines)

with open('cogs/db.py', 'w') as f:
    f.write(content)

remaining = content.count('%s')
print(f'Final remaining %s: {remaining}')
