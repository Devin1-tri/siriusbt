
import json, os, sys
import sirius_api as S
ACC = "/home/ubuntu/bot/sirius/accounts.json"
accounts = json.load(open(ACC))
key = sorted(accounts)[0]
sess = accounts[key]["session"]
# rotate-in the refresh token handed out by the last successful refresh (single-use scheme)
if len(sys.argv) > 1:
    sess["refreshToken"] = sys.argv[1]
    json.dump(accounts, open(ACC, "w"), indent=1); os.chmod(ACC, 0o600)
c = S.Sirius()
r = c.call("POST", "/auth/refresh", body={"refreshToken": sess["refreshToken"]})
print("refresh:", json.dumps(r.get("body"), default=str)[:400])
data = (r.get("body") or {}).get("data") or {}
if data.get("accessToken"):
    sess.update(data)
    json.dump(accounts, open(ACC, "w"), indent=1); os.chmod(ACC, 0o600)
    print("SAVED new session tokens")
else:
    sys.exit(1)
