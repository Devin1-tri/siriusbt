
import json, uuid
import sirius_api as S
a = json.load(open("/home/ubuntu/bot/sirius/accounts.json"))
k = sorted(a)[0]; acct = a[k]
c = S.Sirius()
variants = {
 "flat": {"identityId": acct["identityId"], "installationId": acct["installationId"], "platform": "android"},
 "flat+avatar": {"identityId": acct["identityId"], "installationId": acct["installationId"], "platform": "android", "avatarCode": "AVATAR_01"},
 "nested": {"credentials": {"identityId": acct["identityId"], "installationId": acct["installationId"]}, "platform": "android"},
 "ident_only": {"identityId": acct["identityId"]},
 "flat_noInst": {"identityId": acct["identityId"], "platform": "android"},
}
for name, body in variants.items():
    r = c.call("POST", "/auth/login", body=body)
    print(name, "->", r.get("_status"), json.dumps(r.get("body"), default=str)[:220], flush=True)
