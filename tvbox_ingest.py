
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TVBox 配置生态摄取 v2（lead, 2026-11-23）
①CMS站点→vod_sources.py候选池  ②直播源→aggregate.py并池  ③T4接口(2026生态已灭绝,留桩)
设计原则：独立模块+全程容错——任何异常只打印跳过，绝不影响主管线。
"""
import json, re, urllib.request
from urllib.parse import urljoin

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Version/17.4 Safari/605.1.15"}

TVBOX_CONFIGS = [
    "https://raw.githubusercontent.com/cluntop/tvbox/main/box.json",          # 721★ 19CMS+16lives
    "https://raw.githubusercontent.com/huangweiping6666/tvbox-top100/main/top100.json",  # 71CMS 自动验证
    "https://raw.githubusercontent.com/qist/tvbox/master/9918.json",          # 13k★ 30CMS
    "https://raw.githubusercontent.com/qist/tvbox/master/0827.json",          # 6CMS
]

def _fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")

def _load(url):
    raw = _fetch(url)
    i = raw.find("{")
    txt = raw[i:] if i > 0 else raw
    try:
        return json.loads(txt)
    except Exception:
        return json.JSONDecoder().raw_decode(txt)[0]   # 容忍尾随杂数据

def _private(h):
    return h.startswith(("localhost", "127.", "192.168.", "10.", "172."))

def collect(existing=(), limit=60):
    existing = set(existing)
    hosts = []
    for cfg_url in TVBOX_CONFIGS:
        try:
            d = _load(cfg_url)
        except Exception as e:
            print("tvbox_ingest: config skip", cfg_url.rsplit("/", 1)[-1], str(e)[:60])
            continue
        for s in d.get("sites") or []:
            if not isinstance(s, dict):
                continue
            t = str(s.get("type"))
            api = str(s.get("api") or "")
            if t not in ("0", "1", "cms"):
                continue
            if "provide/vod" not in api and "api.php" not in api:
                continue
            m = re.match(r"https?://([^/]+)", api)
            if not m:
                continue
            h = m.group(1)
            if _private(h) or h in existing or h in hosts:
                continue
            hosts.append(h)
    return hosts[:limit]

# ---------- ② 直播源 ----------
def collect_lives(limit=6):
    """提取配置里的直播订阅URL（相对路径已解析为绝对）"""
    out = []
    for cfg_url in TVBOX_CONFIGS:
        try:
            d = _load(cfg_url)
        except Exception:
            continue
        for l in d.get("lives") or []:
            if not isinstance(l, dict):
                continue
            urls = []
            g = l.get("group")
            if isinstance(g, list):
                urls += [it.get("url") for it in g if isinstance(it, dict) and it.get("url")]
            if l.get("url"):
                urls.append(l["url"])
            for u in urls:
                if isinstance(u, str) and u and not u.startswith(("csp_", "JS")):
                    out.append(urljoin(cfg_url, u))
    seen, res = set(), []
    for u in out:
        if u not in seen:
            seen.add(u); res.append(u)
    return res[:limit]

def _clean(u):
    """剥 TVBox 专用标记：$LR•IPV4 / $办事处 等——取 $ 前的真实地址"""
    return u.split("$")[0].strip() if "$" in u else u.strip()

def clean_m3u(text):
    """m3u 直播源清洗：剥 $ 标记"""
    lines = []
    for l in text.splitlines():
        l = l.strip()
        if l and not l.startswith("#"):
            l = _clean(l)
        if l:
            lines.append(l)
    return "\n".join(lines)

def txt_to_m3u(text):
    """TVBox txt 直播格式（'分组,#genre\\n' + '频道,url'）转 m3u"""
    out = ["#EXTM3U"]
    grp = "直播"
    for l in text.splitlines():
        l = l.strip()
        if not l:
            continue
        if l.endswith(",#genre#"):
            grp = l.split(",")[0]
            continue
        if l.startswith("#"):
            continue
        if "," in l:
            name, url = l.split(",", 1)
            url = _clean(url)
            if url.startswith(("http", "rtmp", "rtp", "udp")):
                out.append('#EXTINF:-1 group-title="%s",%s' % (grp, name.strip()))
                out.append(url)
    return "\n".join(out)

# ---------- ③ T4 接口 ----------
def collect_t4():
    """2026-11 勘探结论：主流TVBox配置中 type4 已灭绝(被 type3 蜘蛛取代)。
    若未来配置中出现 type4 站点，其 api 通常接受 ac=videolist 查询——
    届时在 vod_sources.py 的候选里支持完整URL即可（本函数预留）。"""
    t4 = []
    for cfg_url in TVBOX_CONFIGS:
        try:
            d = _load(cfg_url)
        except Exception:
            continue
        for s in d.get("sites") or []:
            if isinstance(s, dict) and str(s.get("type")) == "4" and str(s.get("api") or "").startswith("http"):
                t4.append((str(s.get("name")), str(s["api"])))
    return t4

if __name__ == "__main__":
    hosts = collect()
    print("CMS:", len(hosts))
    lives = collect_lives()
    print("LIVES:", len(lives), [u[-45:] for u in lives[:4]])
    t4 = collect_t4()
    print("T4:", len(t4))
