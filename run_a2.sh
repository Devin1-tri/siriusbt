#!/bin/bash
# A2 pipeline: solve Turnstile -> register -> bind invite code -> start mining.
cd /home/ubuntu/bot/sirius || exit 1

before=$(/home/ubuntu/bot/.venv/bin/python -c "import json;print(' '.join(sorted(json.load(open('accounts.json')))))")
echo "=== [A2] akun lama: $before"

echo "=== [A2] solve Turnstile ==="
rm -f ts_token.json
DISPLAY=:99 timeout 480 /home/ubuntu/bot/cfsolve/bin/python solve_ts.py 2>&1 |
    grep -vE 'LeakWarning|result = self' | tail -6
[ -f ts_token.json ] || { echo "A2: token gagal"; exit 2; }

echo "=== [A2] register ==="
timeout 120 /home/ubuntu/bot/.venv/bin/python do_register.py 2>&1 | tail -8

newkey=$(/home/ubuntu/bot/.venv/bin/python -c "
import json
b = set('$before'.split())
new = [k for k in sorted(json.load(open('accounts.json'))) if k not in b]
print(new[-1] if new else '')")
echo "=== [A2] key=$newkey ==="
[ -n "$newkey" ] || { echo "A2: akun baru tidak ada"; exit 3; }

echo "=== [A2] bind f34UvL + start mining ==="
timeout 120 /home/ubuntu/bot/.venv/bin/python next_steps.py f34UvL "$newkey" 2>&1 | tail -20
echo "A2_EXIT=$?"
