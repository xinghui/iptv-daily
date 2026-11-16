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
    t = re.sub(r'\([^()]*\)', '', s.lower())     # 括号段整体去掉：(720p)（高清）等
    t = re.sub(r'\d{3,4}[pi]', '', t)               # 裸画质标记：720p/1080i
    m = re.match(r'^(cctv|央视)[-_ ]?(\d{1,2})\s*(\+|plus)?', t)
    if m:
        return 'cctv' + m.group(2) + ('+' if m.group(3) else '')
    if re.match(r'^(cctv|央视)[-_ ]?4k', t):
        return 'cctv4k'
    if re.match(r'^(cctv|央视)[-_ ]?8k', t):
        return 'cctv8k'
    s = re.sub(r'[^a-z0-9一-鿿]', '', t)
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
            name = re.sub(r'\s*\([^()]*\)$', '', name).strip()
        elif line and not line.startswith('#'):
            if name:
                out.append((name, line))
    return out


EXTRA_SOURCES = {
    'CCTV1': ['http://74.91.26.218:82/live/cctv1hd.m3u8'],
    # [对照实验] 电视已知可播的 cztv 流走网关——判定网关传输层 vs ysp 内容
    '浙江卫视': ['http://192.168.50.219:8123/h/ali-m-l.cztv.com/channels/lantian/channel07/1080p.m3u8'],
}

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




CCTV_NUM = re.compile(r'cctv[-_ ]?(\d+)(\+?)')
PREF_WS = ['湖南', '浙江', '江苏', '东方', '北京', '广东', '深圳', '山东', '天津', '安徽', '江西', '湖北', '四川', '河南', '辽宁', '黑龙江']

def sort_key(n):
    up = n.upper()
    if 'CCTV' in up or '央视' in n:
        m = CCTV_NUM.search(n.lower())
        if m:
            return (0, int(m.group(1)), 1 if m.group(2) else 0, n)
        return (0, 99, 0, n)
    if '卫视' in n:
        for i, w in enumerate(PREF_WS):
            if w in n:
                return (1, i, 0, n)
        return (1, 50, 0, n)
    return (2, 0, 0, n)




YSP_GW = "http://192.168.50.219:8123"   # mb0 上常驻的官方流清洗网关（剥QQHLS私有标签，老Tizen可播）

def gw_ysp(u):
    """ysp 官方流改走局域网网关（Safari A/B 实验证实：私有标签导致老播放器首帧卡死，清洗后可播）"""
    m = re.match(r"https?://([a-z0-9.-]*(?:ysp\.cctv\.cn|cztv\.com))/([^?\s]+)", u)
    return YSP_GW + "/h/" + m.group(1) + "/" + m.group(2) if m else u


def group_of(name):
    up = name.upper()
    if 'CCTV' in up or '央视' in name:
        return '央视频道'
    if '卫视' in name:
        return '卫视频道'
    return '其他频道'

# ---- 合入保底源 ----
for name, urls in EXTRA_SOURCES.items():
    key = next((k for k in merged if norm(k) == norm(name)), name)
    merged.setdefault(key, [])
    for u in urls:
        if u not in merged[key]:
            merged[key].insert(0, u)

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

def codec_ok(url):
    """探测首个分片：h264+aac 且非隔行为电视网页播放器友好"""
    import subprocess
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        t = urllib.request.urlopen(req, timeout=6).read(30000).decode('utf-8', 'replace')
        seg = next((l.strip() for l in t.splitlines() if l.strip() and not l.startswith('#')), None)
        if not seg:
            return None
        from urllib.parse import urljoin
        seg = urljoin(url, seg)
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name',
                            '-of', 'csv=p=0', seg], capture_output=True, text=True, timeout=10)
        c = r.stdout
        if not ('aac' in c and 'h264' in c):
            return False
        # 隔行检测（1080i 老电视网页解码器放不出画面）
        r2 = subprocess.run(['ffmpeg', '-v', 'info', '-i', seg, '-frames:v:0', '10',
                             '-vf', 'idet', '-an', '-f', 'null', '-'],
                            capture_output=True, text=True, timeout=25)
        m = re.search(r'TFF:\s*(\d+) BFF:\s*(\d+) Progressive:\s*(\d+)', r2.stderr)
        if m and (int(m.group(1)) + int(m.group(2))) > 4:
            return False   # 隔行流
        return True
    except Exception:
        return None

# 对主要频道（央视/卫视）的 live 源做编码探测，aac 优先
MAIN_PREFIX = ('CCTV', '央视')
codec_rank = {}
main_urls = []
for name, urls in merged.items():
    if name.upper().startswith(MAIN_PREFIX[0]) or '央视' in name:
        main_urls.extend(u for u in urls if verdicts.get(u) == 'live')
print(f'codec probing {len(main_urls)} main live urls...')
with concurrent.futures.ThreadPoolExecutor(20) as ex:
    for u, ok in zip(main_urls, ex.map(codec_ok, main_urls)):
        if ok is True:
            codec_rank[u] = 'aac'
        elif ok is False:
            codec_rank[u] = 'noaac'
from collections import Counter as _C
print('codec:', _C(codec_rank.values()))

RANK = {'aac': 0, 'live': 1, 'unknown': 2, 'noaac': 3, 'vod': 4, 'dead': 9}


def sort_key(u):
    if re.match(r'https?://[a-z0-9.-]*ysp\.cctv\.cn', u):
        return (RANK['aac'], 0)     # 网关源无条件顶级（官方CDN+清洗网关+A/B实证可播；CI 地域够不着不该降级它）
    if 'gitv.tv' in u:
        return (RANK['noaac'], 1)   # 已知隔行源黑名单（1080i，老Tizen画面冻+马赛克）
    r = RANK.get(codec_rank.get(u) or verdicts.get(u, 'unknown'), 2)
    return (r, 1)


for name in merged:
    merged[name].sort(key=sort_key)

lines = ['#EXTM3U']
total = 0
for g in ('央视频道', '卫视频道', '其他频道'):
    chans = [(n, u) for n, u in merged.items() if u]
    for n, u in sorted(chans, key=lambda x: sort_key(x[0])):
        if group_of(n) != g:
            continue
        EXTRA_SET = set(u2 for lst in EXTRA_SOURCES.values() for u2 in lst)
        kept = [x for x in u if verdicts.get(x) != 'dead' or x in EXTRA_SET][:5]
        if not kept:
            continue
        total += 1
        lines.append(f'#EXTINF:-1 group-title="{g}",{n}')
        for url in kept:
            lines.append(gw_ysp(url))
with open('iptv.m3u', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print(f'wrote iptv.m3u: {total} channels / {sum(len(v) for v in merged.values())} urls (validated, dead dropped)')
