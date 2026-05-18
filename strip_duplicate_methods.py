import ast
import inspect
from cogs import db as db_mod
from db_compat import DbSqlite

# Find methods unique to Db (not in DbSqlite)
db_methods = {name for name, _ in inspect.getmembers(db_mod.Db, predicate=inspect.isfunction) if not name.startswith('_')}
sqlite_methods = {name for name, _ in inspect.getmembers(DbSqlite, predicate=inspect.isfunction) if not name.startswith('_')}
unique_to_db = db_methods - sqlite_methods
print(f"Keeping {len(unique_to_db)} methods: {sorted(unique_to_db)}")
print(f"Removing {len(db_methods & sqlite_methods)} methods")

with open('cogs/db.py', 'r') as f:
    source = f.read()

tree = ast.parse(source)

# Find the class Db node
class_node = None
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'Db':
        class_node = node
        break

if not class_node:
    print("ERROR: Could not find Db class")
    exit(1)

# Get line ranges for methods to keep
keep_ranges = []
for item in class_node.body:
    if isinstance(item, ast.AsyncFunctionDef) and item.name in unique_to_db:
        start = item.lineno - 1  # 0-indexed
        end = item.end_lineno  # exclusive (ast.end_lineno is 1-indexed, so this is exclusive in 0-indexed)
        keep_ranges.append((start, end, item.name))
        print(f"Keep {item.name}: lines {item.lineno}-{item.end_lineno}")

# Also keep __init__
for item in class_node.body:
    if isinstance(item, ast.FunctionDef) and item.name == '__init__':
        start = item.lineno - 1
        end = item.end_lineno
        keep_ranges.append((start, end, '__init__'))
        print(f"Keep __init__: lines {item.lineno}-{item.end_lineno}")

# Sort by line number
keep_ranges.sort()

# Now rebuild the file
lines = source.split('\n')

# Lines before class (imports, constants, etc.)
class_start = class_node.lineno - 1  # 0-indexed
class_end = class_node.end_lineno  # exclusive in 0-indexed

# Build new class body
new_class_body = []
for start, end, name in keep_ranges:
    # Get the lines including any decorators
    # start might not include decorators - check
    method_lines = lines[start:end]
    new_class_body.extend(method_lines)
    new_class_body.append('')  # blank line between methods

# Build new file: everything before class + class def + new body + setup function
new_lines = lines[:class_start]
new_lines.append('class Db(commands.Cog, DbSqlite):')
new_lines.append('    def __init__(self, bot):')
new_lines.append('        self.bot = bot')
new_lines.append('        DbSqlite.__init__(self, bot)')
new_lines.append('')

# Add unique methods
for start, end, name in keep_ranges:
    if name == '__init__':
        continue
    method_lines = lines[start:end]
    for ml in method_lines:
        new_lines.append(ml)
    new_lines.append('')

# Add async def setup at the end
new_lines.append('')
new_lines.append('async def setup(bot):')
new_lines.append('    await bot.add_cog(Db(bot))')

new_content = '\n'.join(new_lines)

with open('cogs/db.py', 'w') as f:
    f.write(new_content)

print(f"\nNew file has {len(new_lines)} lines (was {len(lines)})")
print("Done!")
