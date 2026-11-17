
import json, re, time, urllib.request, urllib.parse, datetime, concurrent.futures

SRC_CFG = "https://raw.githubusercontent.com/hafrey1/LunaTV-config/main/LunaTV-config.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"}

def fetch(url, timeout):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()

cfg = json.loads(fetch(SRC_CFG, 30).decode("utf-8", "replace"))
sites = cfg.get("api_site") or []
if isinstance(sites, dict):
    sites = list(sites.values())
cands = []
for s in sites:
    api = (s.get("api") or s.get("url") or "").strip()
    m = re.match(r"https?://([^/]+)", api)
    if m:
        cands.append(m.group(1))
cands = list(dict.fromkeys(cands))
print("候选站:", len(cands))

def probe(host):
    url = "http://" + host + "/api.php/provide/vod?ac=videolist&wd=test"
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=8).read()
        j = json.loads(raw.decode("utf-8", "replace"))
        lst = j.get("list") or j.get("vodlist") or []
        if not isinstance(lst, list) or not lst:
            return None
        return (host, round(time.time() - t0, 2), len(lst))
    except Exception:
        return None

with concurrent.futures.ThreadPoolExecutor(20) as ex:
    res = [r for r in ex.map(probe, cands) if r]
res.sort(key=lambda x: x[1])
top = [r[0] for r in res[:8]]
out = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "hosts": top,
       "probed": len(cands), "alive": len(res),
       "detail": [{"host": h, "sec": s, "n": n} for h, s, n in res[:15]]}
open("vod-sources.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False))
