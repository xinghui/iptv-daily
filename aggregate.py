#!/usr/bin/env python3
"""聚合多个 IPTV 源仓库为单个精选 iptv.m3u（按归一化名去重，每频道最多 3 源）。"""
import re
import urllib.request

REPOS = [
    'https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u',
    'https://raw.githubusercontent.com/jamsluuuuu/iptv/main/china-hk-mo-tw-live.m3u',
    'https://raw.githubusercontent.com/best-fan/iptv-sources/master/cn_all.m3u8',
    'https://raw.githubusercontent.com/TianmuTNT/iptv/main/iptv.m3u',
    'https://iptv-zb-zy.pages.dev/output/ipv4/result.m3u',
    'https://raw.githubusercontent.com/zilong7728/Collect-IPTV/main/best_sorted.m3u',
]


DECOR = re.compile(r'(综合|高清|超清|标清|频道|纯享|冨二代|富二代)$')

def norm(s):
    s = re.sub(r'[^a-z0-9一-鿿]', '', s.lower())
    s2 = DECOR.sub('', s)
    return s2 if s2 else s


def fetch(url):
    import time as _t
    last = None
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
            _t.sleep(2 * (i + 1))
    raise last


def parse(text):
    out, name = [], ''
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF'):
            name = line.split(',')[-1].strip()
            name = re.sub(r'\[[^\]]*\]', '', name).replace('✓', '').replace('已核验', '').strip()
        elif line and not line.startswith('#'):
            if name:
                out.append((name, line))
    return out


merged = {}
for repo in REPOS:
    try:
        for name, url in parse(fetch(repo)):
            key = next((k for k in merged if norm(k) == norm(name)), name)
            if key in merged and len(name) < len(key):
                merged[name] = merged.pop(key)   # 保留更短的主名（CCTV1 而非 CCTV1 综合）
                key = name
            merged.setdefault(key, [])
            if url not in merged[key] and len(merged[key]) < 8:
                merged[key].append(url)
        print(f'ok {repo}')
    except Exception as e:
        print(f'fail {repo}: {e}')


def check(url):
    """源验证：404/403=死；真直播=窗口滚动（二次抓取确认）；静态录像/ENDLIST=点播降级"""
    import urllib.error
    import time as _time

    def _fetch(u):
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        return urllib.request.urlopen(req, timeout=6).read(20000).decode('utf-8', 'replace')

    try:
        t1 = _fetch(url)
    except urllib.error.HTTPError as e:
        return 'dead' if e.code in (403, 404, 410) else 'unknown'
    except Exception:
        return 'unknown'
    if '#EXTM3U' not in t1 and '#EXTINF' not in t1:
        return 'unknown'
    if '#EXT-X-ENDLIST' in t1:
        return 'vod'
    s1 = re.search(r'MEDIA-SEQUENCE:(\d+)', t1)
    if not s1:
        return 'live'
    _time.sleep(8)
    try:
        s2 = re.search(r'MEDIA-SEQUENCE:(\d+)', _fetch(url))
        if s2 and int(s2.group(1)) > int(s1.group(1)):
            return 'live'
        return 'vod'   # SEQ 不滚动 = 录像伪装直播
    except Exception:
        return 'live'  # 二次抓取失败不冤枉，保守按直播


def group_of(name):
    up = name.upper()
    if 'CCTV' in up or '央视' in name:
        return '央视频道'
    if '卫视' in name:
        return '卫视频道'
    return '其他频道'

# ---- 源验证（并发）----
import concurrent.futures

urls_all = []
for v in merged.values():
    urls_all.extend(v)
print(f'validating {len(urls_all)} urls...')
with concurrent.futures.ThreadPoolExecutor(40) as ex:
    verdicts = dict(zip(urls_all, ex.map(check, urls_all)))
from collections import Counter
print(Counter(verdicts.values()))

RANK = {'live': 0, 'unknown': 1, 'vod': 2, 'dead': 9}
for name in merged:
    merged[name].sort(key=lambda u: RANK.get(verdicts.get(u, 'unknown'), 1))

lines = ['#EXTM3U']
total = 0
for g in ('央视频道', '卫视频道', '其他频道'):
    chans = [(n, u) for n, u in merged.items() if u]
    for n, u in sorted(chans, key=lambda x: x[0]):
        if group_of(n) != g:
            continue
        kept = [x for x in u if verdicts.get(x) != 'dead'][:5]
        if not kept:
            continue
        total += 1
        lines.append(f'#EXTINF:-1 group-title="{g}",{n}')
        for url in kept:
            lines.append(url)
with open('iptv.m3u', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print(f'wrote iptv.m3u: {total} channels / {sum(len(v) for v in merged.values())} urls (validated, dead dropped)')
