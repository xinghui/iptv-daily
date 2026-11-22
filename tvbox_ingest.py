
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TVBox 配置生态摄取（lead, 2026-11-22）
从社区流通的 TVBox 配置订阅里提取苹果CMS型站点，并入 vod_sources.py 候选池。
设计原则：独立模块 + 全程 try/except——本模块任何异常只打印跳过，绝不影响主管线。
新增配置订阅：往 TVBOX_CONFIGS 追加 URL 即可（无需改 vod_sources.py）。
"""
import json, re, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Version/17.4 Safari/605.1.15"}

TVBOX_CONFIGS = [
    "https://raw.githubusercontent.com/cluntop/tvbox/main/box.json",     # 721★ 昨日更新，19+ CMS 站
    "https://raw.githubusercontent.com/qist/tvbox/master/0827.json",     # 13k★ 11-21 更新
    # 社区生态提示：饭太硬/肥猫/王二小等聚合配置大多为 type3 蜘蛛源(需Java,电视跑不了,自动跳过)
    # 发现新的高质量 CMS 型配置往这里加
]

def _fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")

def _private(h):
    return h.startswith(("localhost", "127.", "192.168.", "10.", "172."))

def collect(existing=(), limit=40):
    existing = set(existing)
    hosts = []
    for cfg_url in TVBOX_CONFIGS:
        try:
            raw = _fetch(cfg_url)
            i = raw.find("{")
            d = json.loads(raw[i:] if i > 0 else raw)
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

if __name__ == "__main__":
    got = collect()
    print(len(got), got)
