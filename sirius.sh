#!/usr/bin/env bash
# siriusbt control script — use this inside the screen session.
#
#   ./sirius.sh start     dashboard + keep-alive every 30m (foreground; Ctrl+C
#                         stops it, the screen session stays alive)
#   ./sirius.sh once      one keeper pass (bind invite + mining round)
#   ./sirius.sh status    one dashboard snapshot
#   ./sirius.sh new [KODE]  register a new account (Turnstile -> register -> bind -> mine)
#   ./sirius.sh ensure    make sure the two local services the solver needs are up
#   ./sirius.sh logs [n]  tail the cron keeper's log
set -u
cd "$(dirname "$0")"

if [ -x /home/ubuntu/bot/.venv/bin/python ]; then PY="/home/ubuntu/bot/.venv/bin/python"
elif command -v python3 >/dev/null; then PY="python3"
else echo "python3 tidak ditemukan"; exit 1; fi

listening() { ss -ltn 2>/dev/null | grep -q ":$1 "; }

ensure() {
  # 1. local page for the Turnstile widget (the sitekey refuses `localhost`)
  if ! listening 8002; then
    (cd turnstile && nohup python3 -m http.server 8002 >/tmp/ts_http.log 2>&1 &)
    sleep 1
    listening 8002 && echo "http :8002 started" || echo "http :8002 GAGAL"
  else
    echo "http :8002 ok"
  fi
  # 2. WARP egress (SOCKS5) — the CF challenge resolves a Cloudflare-owned IP
  if ! listening 25344; then
    if [ -x /tmp/wireproxy ] && [ -f /tmp/wp.conf ]; then
      (cd /tmp && nohup ./wireproxy -c /tmp/wp.conf >/tmp/wireproxy.log 2>&1 &)
      sleep 2
      listening 25344 && echo "wireproxy :25344 started" || echo "wireproxy GAGAL (cek /tmp/wireproxy.log)"
    else
      echo "wireproxy belum ada di /tmp (butuh SOCKS5 WARP untuk solve Turnstile)"
    fi
  else
    echo "wireproxy :25344 ok"
  fi
}

case "${1:-start}" in
  start)  exec "$PY" sirius_dashboard.py ;;
  once)   exec "$PY" mine_daily.py ;;
  status) exec "$PY" sirius_dashboard.py --once ;;
  ensure) ensure ;;
  new)    shift; ensure; exec "$PY" new_account.py "$@" ;;
  logs)   tail -n "${2:-40}" keeper.log 2>/dev/null || echo "(belum ada log)" ;;
  *)
    cat <<'EOF'
siriusbt — perintah:
  ./sirius.sh start           # dashboard live + keep-alive tiap 30 menit (Ctrl+C = stop)
  ./sirius.sh once            # satu pass keeper: bind kode undangan + start round
  ./sirius.sh status          # satu snapshot (tanpa live)
  ./sirius.sh new [KODE]      # daftar akun baru (Turnstile -> register -> bind -> mining)
  ./sirius.sh ensure          # cek/start http :8002 + WARP SOCKS :25344 (dipakai solver)
  ./sirius.sh logs [n]        # log cron keeper
EOF
    ;;
esac
