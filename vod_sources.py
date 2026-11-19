
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VOD 源管线 v3：类目白名单制
1) 探测源(延迟排序) → 2) 拉各站类目树，须有>=2个干净类目才收编(纯成人站自动出局)
→ 3) 只从干净类目抓货架+索引 → 4) 关键词黑名单终审"""
import json, re, time, urllib.request, datetime, concurrent.futures

SRC_CFG = "https://raw.githubusercontent.com/hafrey1/LunaTV-config/main/LunaTV-config.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"}
KEEP = ("vod_id", "vod_name", "vod_pic", "vod_remarks", "vod_play_url",
        "vod_douban_score", "vod_area", "vod_year", "vod_class", "type_name")
BAD_WORDS = ("伦理", "强奸", "乱伦", "轮奸", "情色", "无码", "有码", "女优", "里番", "巨乳",
             "人妻", "熟女", "丝袜", "美腿", "激情片", "偷拍", "欧美AV", "日本AV", "国产AV",
             "成人", "福利姬", "肉欲", "艳舞", "网曝", "制服诱惑", "角色扮演", "主播直播", "私密", "换妻")
CLEAN_CAT = re.compile(r"电影|连续剧|电视剧|剧集|综艺|动漫|动画|少儿|纪录|体育|音乐|短剧|曲艺|教育|科技|喜剧|动作|爱情|科幻|恐怖|惊悚|悬疑|战争|犯罪|剧情|奇幻|冒险|武侠|古装|历史|家庭|都市|青春|谍战|军旅|抗战|年代|农村|脱口秀|真人秀")

def fetch(url, timeout):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()

def is_adult(it):
    blob = " ".join(str(it.get(k) or "") for k in ("vod_name", "vod_class", "type_name", "vod_remarks"))
    return any(w in blob for w in BAD_WORDS)

def slim_list(j):
    lst = j.get("list") or j.get("vodlist") or []
    return [{k: it.get(k) for k in KEEP} for it in lst
            if isinstance(it, dict) and it.get("vod_name") and it.get("vod_play_url") and not is_adult(it)]

def q(host, qs, timeout=10):
    return slim_list(json.loads(fetch("http://" + host + "/api.php/provide/vod?" + qs, timeout).decode("utf-8", "replace")))

# ---- 1) 源探测 ----
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
        return (host, round(time.time() - t0, 2)) if q(host, "ac=videolist&wd=test", 8) else None
    except Exception:
        return None

with concurrent.futures.ThreadPoolExecutor(20) as ex:
    res = sorted([r for r in ex.map(probe, cands) if r], key=lambda x: x[1])

# ---- 2) 类目树白名单筛站 ----
def clean_cats(host):
    try:
        j = json.loads(fetch("http://" + host + "/api.php/provide/vod?ac=list", 10).decode("utf-8", "replace"))
        cls = j.get("class") or []
        good = [(str(c.get("type_id")), str(c.get("type_name") or "")) for c in cls
                if c.get("type_id") and CLEAN_CAT.search(str(c.get("type_name") or ""))]
        return good[:6]
    except Exception:
        return []

kept = []
for host, sec in res[:20]:
    cats = clean_cats(host)
    if len(cats) >= 2:
        kept.append((host, sec, cats))
    if len(kept) >= 6:
        break
top = [h for h, s, c in kept]
print("clean stations:", top)
src_out = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "hosts": top[:8],
           "probed": len(cands), "alive": len(res), "clean": len(kept)}
open("vod-sources.json", "w", encoding="utf-8").write(json.dumps(src_out, ensure_ascii=False, indent=1))

# ---- 3) 干净类目抓内容 ----
def dedup(items, cap):
    seen, out = set(), []
    for it in items:
        if it["vod_name"] not in seen:
            seen.add(it["vod_name"]); out.append(it)
            if len(out) >= cap: break
    return out

shelf_raw, idx_raw = [], []
def job(arg):
    host, tid, pg = arg
    try:
        return q(host, "ac=videolist&t=" + tid + "&pg=" + str(pg), 12)
    except Exception:
        return []
jobs_shelf = [(h, c[0][0], 1) for h, s, c in kept[:4]]
jobs_idx = [(h, cid, pg) for h, s, c in kept[:4] for cid, _ in c[:3] for pg in (1, 2, 3, 4)]
with concurrent.futures.ThreadPoolExecutor(16) as ex:
    for r_ in ex.map(job, jobs_shelf):
        shelf_raw.extend(r_)
with concurrent.futures.ThreadPoolExecutor(16) as ex:
    for r_ in ex.map(job, jobs_idx):
        idx_raw.extend(r_)

shelf = dedup(shelf_raw, 150)
index = dedup(idx_raw, 1500)
content = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "shelf": shelf, "index": index,
           "stats": {"shelf_raw": len(shelf_raw), "idx_raw": len(idx_raw)}}
open("vod-content.json", "w", encoding="utf-8").write(json.dumps(content, ensure_ascii=False))
print("content: shelf", len(shelf), "index", len(index), "size", len(json.dumps(content, ensure_ascii=False)) // 1024, "KB")
