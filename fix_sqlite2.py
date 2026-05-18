import re

with open('cogs/db.py', 'r') as f:
    content = f.read()

# Fix 1: Convert [a, b] params to (a, b) in execute calls
# Pattern: execute('...', [params]) -> execute('...', (params))

def fix_list_params(text):
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        if 'execute(' in line and '[' in line and ']' in line:
            # Find the [ ... ] part and replace with ( ... )
            # Simple approach: replace [ with ( and ] with ) for params
            # But only if it's after execute and after a comma
            match = re.search(r"(execute\(.+?,\s*)\[(.+?)\](\s*\))", line)
            if match:
                line = line[:match.start()] + match.group(1) + '(' + match.group(2) + ')' + match.group(3) + line[match.end():]
        new_lines.append(line)
    return '\n'.join(new_lines)

content = fix_list_params(content)

# Fix 2: Fix single-item tuples in execute calls
# SQLite requires (value,) not (value) for single params
# Pattern: execute('...', (value)) -> execute('...', (value,))
# But be careful not to mess up function calls inside tuples

def fix_single_tuples(text):
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        if 'execute(' in line:
            # Find execute calls with single-item tuples missing comma
            # execute('...', (something))
            # Need to convert to execute('...', (something,))
            # Only if there's exactly one item in the parens
            match = re.search(r"(execute\(.+?,\s*)\(([^(),]+)\)(\s*\))", line)
            if match:
                inner = match.group(2).strip()
                # Make sure it's not a nested call like str(x) where str is inside
                if not inner.startswith('str(') and not '(' in inner:
                    line = line[:match.start()] + match.group(1) + '(' + inner + ',)' + match.group(3) + line[match.end():]
                elif inner.startswith('str(') and inner.count('(') == 1 and inner.endswith(')'):
                    # It's str(something) - still single item
                    line = line[:match.start()] + match.group(1) + '(' + inner + ',)' + match.group(3) + line[match.end():]
        new_lines.append(line)
    return '\n'.join(new_lines)

content = fix_single_tuples(content)

with open('cogs/db.py', 'w') as f:
    f.write(content)

# Check remaining issues
lines = content.split('\n')
issues = []
for i, line in enumerate(lines, 1):
    if 'execute(' in line:
        if '%s' in line:
            issues.append(f"Line {i}: still has %s")
        if '[' in line and ']' in line:
            issues.append(f"Line {i}: still has [params]")

if issues:
    print("Remaining issues:")
    for issue in issues[:10]:
        print(issue)
else:
    print("All execute calls look good!")
