
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VOD 源管线 v2：探测源 + 抓取内容
产出 vod-sources.json（源清单8强）+ vod-content.json（货架150 + 搜索索引1500）
App 默认走 CDN 静态层，彻底摆脱对局域网代理的依赖"""
import json, re, time, urllib.request, urllib.parse, datetime, concurrent.futures

SRC_CFG = "https://raw.githubusercontent.com/hafrey1/LunaTV-config/main/LunaTV-config.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"}
KEEP = ("vod_id", "vod_name", "vod_pic", "vod_remarks", "vod_play_url",
        "vod_douban_score", "vod_area", "vod_year", "vod_class", "type_name")
BAD_WORDS = ("伦理", "情色", "无码", "有码", "女优", "里番", "巨乳", "人妻",
             "熟女", "丝袜", "美腿", "激情片", "偷拍", "欧美AV", "日本AV",
             "国产AV", "成人", "福利姬", "肉欲", "艳舞")

def is_adult(it):
    blob = " ".join(str(it.get(k) or "") for k in ("vod_name", "vod_class", "type_name", "vod_remarks"))
    return any(w in blob for w in BAD_WORDS)

def fetch(url, timeout):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()

def slim_list(j):
    lst = j.get("list") or j.get("vodlist") or []
    return [{k: it.get(k) for k in KEEP} for it in lst
            if isinstance(it, dict) and it.get("vod_name") and it.get("vod_play_url") and not is_adult(it)]

def q(host, qs, timeout=10):
    url = "http://" + host + "/api.php/provide/vod?" + qs
    return slim_list(json.loads(fetch(url, timeout).decode("utf-8", "replace")))

# ---- 1) 源探测（同 v1） ----
cfg = json.loads(fetch(SRC_CFG, 30).decode("utf-8", "replace"))
sites = cfg.get("api_site") or []
if isinstance(sites, dict):
    sites = list(sites.values())
cands = []
for s in sites:
    m = re.match(r"https?://([^/]+)", (s.get("api") or s.get("url") or "").strip())
    if m:
        cands.append(m.group(1))
cands = list(dict.fromkeys(cands))

def probe(host):
    t0 = time.time()
    try:
        lst = q(host, "ac=videolist&wd=test", 8)
        return (host, round(time.time() - t0, 2)) if lst else None
    except Exception:
        return None

with concurrent.futures.ThreadPoolExecutor(20) as ex:
    res = [r for r in ex.map(probe, cands) if r]
res.sort(key=lambda x: x[1])
top = [r[0] for r in res[:8]]
src_out = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "hosts": top,
           "probed": len(cands), "alive": len(res)}
open("vod-sources.json", "w", encoding="utf-8").write(json.dumps(src_out, ensure_ascii=False, indent=1))
print("sources:", src_out)

# ---- 2) 内容抓取：货架（h=24 最新） + 索引（多页全库近期） ----
def dedup(items, cap):
    seen, out = set(), []
    for it in items:
        if it["vod_name"] not in seen:
            seen.add(it["vod_name"])
            out.append(it)
            if len(out) >= cap:
                break
    return out

shelf_raw = []
def shelf_job(h):
    try:
        return q(h, "ac=videolist&h=24&pg=1", 12)
    except Exception:
        return []
with concurrent.futures.ThreadPoolExecutor(6) as ex:
    for r_ in ex.map(shelf_job, top[:4]):
        shelf_raw.extend(r_)

idx_raw = []
def idx_job(arg):
    h, pg = arg
    try:
        return q(h, "ac=videolist&pg=" + str(pg), 12)
    except Exception:
        return []
jobs = [(h, pg) for h in top[:4] for pg in range(1, 16)]
with concurrent.futures.ThreadPoolExecutor(16) as ex:
    for r_ in ex.map(idx_job, jobs):
        idx_raw.extend(r_)

shelf = dedup(shelf_raw, 150)
index = dedup(idx_raw, 1500)
content = {"updated": datetime.datetime.utcnow().isoformat() + "Z",
           "shelf": shelf, "index": index,
           "stats": {"shelf_raw": len(shelf_raw), "idx_raw": len(idx_raw)}}
open("vod-content.json", "w", encoding="utf-8").write(json.dumps(content, ensure_ascii=False))
print("content: shelf", len(shelf), "index", len(index),
      "size", len(json.dumps(content, ensure_ascii=False)) // 1024, "KB")
