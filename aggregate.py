#!/usr/bin/env python3
"""聚合多个 IPTV 源仓库为单个精选 iptv.m3u（按归一化名去重，每频道最多 3 源）。"""
import re
import urllib.request

REPOS = [
    'https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u',
    'https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u',
    'https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u',
    'https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv6.m3u',
]


def norm(s):
    return re.sub(r'[^a-z0-9一-鿿]', '', s.lower())


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def parse(text):
    out, name = [], ''
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF'):
            name = line.split(',')[-1].strip()
        elif line and not line.startswith('#'):
            if name:
                out.append((name, line))
    return out


merged = {}
for repo in REPOS:
    try:
        for name, url in parse(fetch(repo)):
            key = next((k for k in merged if norm(k) == norm(name)), name)
            merged.setdefault(key, [])
            if url not in merged[key] and len(merged[key]) < 3:
                merged[key].append(url)
        print(f'ok {repo}')
    except Exception as e:
        print(f'fail {repo}: {e}')


def group_of(name):
    up = name.upper()
    if 'CCTV' in up or '央视' in name:
        return '央视频道'
    if '卫视' in name:
        return '卫视频道'
    return '其他频道'

lines = ['#EXTM3U']
total = 0
for g in ('央视频道', '卫视频道', '其他频道'):
    chans = [(n, u) for n, u in merged.items() if u]
    for n, u in sorted(chans, key=lambda x: x[0]):
        if group_of(n) != g:
            continue
        total += 1
        lines.append(f'#EXTINF:-1 group-title="{g}",{n}')
        for url in u:
            lines.append(url)
with open('iptv.m3u', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print(f'wrote iptv.m3u: {total} channels / {sum(len(v) for v in merged.values())} urls')
