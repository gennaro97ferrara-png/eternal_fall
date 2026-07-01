#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — monitor YouTube (self-heal del broadcast).
# La live del 2026-06-30 e' caduta a 28h perche' YouTube ha terminato il
# broadcast su un blip di rete mentre ffmpeg continuava a spingere su un
# ingest "zombie" (nessun broadcast pubblico legato). Poi, quando l'utente
# arma un NUOVO broadcast, una connessione ffmpeg STANTIA non lo fa transitare
# a "live": serve una riconnessione FRESCA (verificato).
#
# Questo monitor, ogni 60s:
#   - rileva a bassa latenza (playlist uploads) se il canale e' LIVE / UPCOMING;
#   - se LIVE: sincronizza YT_VIDEO_ID nel .env (chat/comandi sul broadcast giusto);
#   - se NON live ma UPCOMING armato: forza una riconnessione ffmpeg fresca
#     (kill -> lo streamloop respawna) -> auto-start del broadcast. Con cooldown.
#   - se ne' live ne' upcoming: logga OUTAGE (serve armare una diretta in Studio;
#     senza OAuth in scrittura non e' automatizzabile).
# ============================================================================
import json, os, re, subprocess, sys, time, urllib.request

ENV = "/root/eternal-fall/.env"
CHANNEL = "UCynrYln7HHhT1hSeQdt7uDQ"
LOG = "/tmp/ef-monitor.log"
PERIOD = 60           # s tra i controlli
RECONNECT_COOLDOWN = 180   # s minimi tra due riconnessioni forzate
FFMPEG_MIN_AGE = 90        # non killare un ffmpeg piu' giovane di cosi'

def say(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S", time.gmtime()), msg)
    try:
        with open(LOG, "a") as f: f.write(line + "\n")
    except Exception: pass

def env_get(key):
    try:
        for ln in open(ENV):
            m = re.match(r"\s*%s\s*=\s*(.*)\s*$" % key, ln)
            if m: return m.group(1).strip().strip('"\'')
    except Exception: pass
    return ""

def env_set_video_id(vid):
    try:
        lines = open(ENV).read().splitlines()
        out, found = [], False
        for ln in lines:
            if re.match(r"\s*YT_VIDEO_ID\s*=", ln):
                out.append("YT_VIDEO_ID=" + vid); found = True
            else:
                out.append(ln)
        if not found: out.append("YT_VIDEO_ID=" + vid)
        open(ENV, "w").write("\n".join(out) + "\n")
        return True
    except Exception as e:
        say("env_set errore: %s" % e); return False

def api(url):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)

def channel_state(key):
    """Ritorna (live_id|None, upcoming_id|None) via playlist uploads (bassa latenza)."""
    ch = api("https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id=%s&key=%s" % (CHANNEL, key))
    up = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = api("https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId=%s&maxResults=8&key=%s" % (up, key))
    ids = ",".join(i["contentDetails"]["videoId"] for i in pl.get("items", []))
    if not ids: return None, None
    vs = api("https://www.googleapis.com/youtube/v3/videos?part=snippet&id=%s&key=%s" % (ids, key))
    live = upcoming = None
    for it in vs.get("items", []):
        c = it["snippet"].get("liveBroadcastContent")
        if c == "live" and not live: live = it["id"]
        elif c == "upcoming" and not upcoming: upcoming = it["id"]
    return live, upcoming

def ffmpeg_age():
    try:
        pid = subprocess.check_output(["pgrep", "-x", "ffmpeg"]).split()[0].decode()
        et = subprocess.check_output(["ps", "-o", "etimes=", "-p", pid]).strip()
        return int(et)
    except Exception:
        return -1

def force_reconnect(reason):
    say("RICONNESSIONE ffmpeg forzata: %s" % reason)
    subprocess.call(["pkill", "-x", "ffmpeg"])   # lo streamloop respawna una connessione fresca

def main():
    key = env_get("YT_API_KEY")
    if not key:
        say("YT_API_KEY assente nel .env — monitor inerte");
    say("===== monitor avviato =====")
    last_reconnect = 0.0
    while True:
        try:
            key = env_get("YT_API_KEY") or key
            live, upcoming = channel_state(key)
            if live:
                cur = env_get("YT_VIDEO_ID")
                if cur != live:
                    say("LIVE=%s (era YT_VIDEO_ID=%s) -> aggiorno .env + restart ef-server" % (live, cur))
                    if env_set_video_id(live):
                        subprocess.call(["systemctl", "restart", "ef-server"])
                # tutto ok: nessun'altra azione
            elif upcoming:
                age = ffmpeg_age()
                now = time.time()
                if age >= FFMPEG_MIN_AGE and (now - last_reconnect) >= RECONNECT_COOLDOWN:
                    force_reconnect("broadcast UPCOMING=%s non live, ffmpeg stantio (%ss)" % (upcoming, age))
                    last_reconnect = now
                else:
                    say("upcoming=%s, non-live; attendo (ffmpeg_age=%ss, cooldown)" % (upcoming, age))
            else:
                say("OUTAGE: nessun broadcast live ne' upcoming — armare una diretta in YouTube Studio")
        except Exception as e:
            say("errore ciclo: %s" % e)
        time.sleep(PERIOD)

if __name__ == "__main__":
    main()
