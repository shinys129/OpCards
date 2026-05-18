import re

with open('cogs/db.py', 'r') as f:
    content = f.read()

def replace_placeholders(match):
    sql = match.group(1)
    params = match.group(2)
    count = sql.count('%s')
    if count == 0:
        return match.group(0)
    new_sql = sql.replace('%s', '?')
    # Convert [a, b] to (a, b)
    params_stripped = params.strip()
    if params_stripped.startswith('[') and params_stripped.endswith(']'):
        new_params = '(' + params_stripped[1:-1] + ')'
        return "execute('" + new_sql + "', " + new_params + ")"
    return "execute('" + new_sql + "', " + params + ")"

# Single/double quoted strings with execute('...', [])
pattern = r"execute\(['\"](.+?)['\"]\s*,\s*(\[[^\]]*\])\)"
content = re.sub(pattern, replace_placeholders, content)

# Triple-quoted strings with execute('''...''', [])
pattern2 = r"execute\('''(.+?)'''\s*,\s*(\[[^\]]*\])\)"
content = re.sub(pattern2, replace_placeholders, content)

with open('cogs/db.py', 'w') as f:
    f.write(content)

remaining = content.count("'%s")
print(f'Done. Remaining %s in single quotes: {remaining}')
