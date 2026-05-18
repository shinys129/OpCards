import re

with open('cogs/db.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if 'execute(' in line and '?' in line:
        # Find execute('sql', (param)) and fix to execute('sql', (param,))
        # Use regex to find the pattern
        match = re.search(r"(execute\(['\"].*?['\"]\s*,\s*)\(([^,()]+)\)(\s*\))", line)
        if match:
            inner = match.group(2).strip()
            # Make sure it's truly a single param (no nested parens in the inner)
            if inner.count('(') == inner.count(')'):
                old = f"({inner})"
                new = f"({inner},)"
                # Only replace the LAST occurrence (the params, not the SQL)
                parts = line.rsplit(old, 1)
                if len(parts) == 2:
                    line = new.join(parts)
    new_lines.append(line)

with open('cogs/db.py', 'w') as f:
    f.writelines(new_lines)

# Verify
with open('cogs/db.py', 'r') as f:
    content = f.read()

# Find remaining problematic single-param calls
issues = []
for i, line in enumerate(content.split('\n'), 1):
    if 'execute(' in line and '?' in line:
        # Check if it has a single param tuple without comma
        if re.search(r"execute\(['\"].*?['\"]\s*,\s*\([^,]+\)\s*\)", line):
            if not re.search(r"execute\(['\"].*?['\"]\s*,\s*\([^,]+,\)\s*\)", line):
                # Also exclude lines with triple quotes
                if "'''" not in line or '?' in line.split("'''")[-1] if "'''" in line else True:
                    issues.append(f"Line {i}: {line.strip()}")

if issues:
    print("Remaining issues:")
    for issue in issues[:20]:
        print(issue)
else:
    print("All single-param execute calls look good!")
