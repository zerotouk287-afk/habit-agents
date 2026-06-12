#!/usr/bin/env python3
# ~/habit-agents/server/server.py
# 습관 트래킹 로컬 서버: 바탕화면 캐릭터의 입력을 받아 로컬 기록 + 노션 동기화 + 현황 제공
import json, os, datetime, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.expanduser('~/habit-agents')
PORT = 8787
REMINDER_TIME = '21:00'   # 매일 이 시각에 아직 안 한 습관 알림 (HH:MM, 끄려면 '')
REPORT_PARENT_PAGE = ''  # 주간 리포트를 받을 노션 페이지 ID (README 참고, 비워두면 리포트 생략)
_last_report_attempt = 0

def goals():
    return json.load(open(f'{BASE}/data/goals.json'))

def token():
    try:
        return open(f'{BASE}/.notion_token').read().strip()
    except FileNotFoundError:
        return None

def log_path(d):
    return f'{BASE}/data/logs/{d.strftime("%Y-%m")}.jsonl'

def read_recent_logs():
    """이번 달 + 지난 달 로그"""
    t = datetime.date.today()
    months = [t.replace(day=1)]
    months.append((months[0] - datetime.timedelta(days=1)).replace(day=1))
    out = []
    for m in months:
        p = log_path(m)
        if os.path.exists(p):
            for line in open(p, encoding='utf-8'):
                line = line.strip()
                if line:
                    try: out.append(json.loads(line))
                    except json.JSONDecodeError: pass
    return out

def read_all_logs():
    out = []
    d = f'{BASE}/data/logs'
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.jsonl'):
                for line in open(os.path.join(d, fn), encoding='utf-8'):
                    line = line.strip()
                    if line:
                        try: out.append(json.loads(line))
                        except json.JSONDecodeError: pass
    return out

def week_days():
    t = datetime.date.today()
    mon = t - datetime.timedelta(days=t.weekday())
    return [mon + datetime.timedelta(days=i) for i in range(7)]

def iso_week(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"

def day_minutes(logs, hid):
    out = {}
    for e in logs:
        if e.get('habit') != hid: continue
        d = str(e.get('ts',''))[:10]
        if d: out[d] = out.get(d,0) + int(e.get('minutes',0) or 0)
    return out

def streaks(day_set):
    if not day_set: return 0, 0
    t = datetime.date.today()
    cur = 0
    start = t if t.isoformat() in day_set else t - datetime.timedelta(days=1)
    d = start
    while d.isoformat() in day_set:
        cur += 1; d -= datetime.timedelta(days=1)
    best = run = 0
    prev = None
    for ds in sorted(day_set):
        d = datetime.date.fromisoformat(ds)
        run = run + 1 if prev and (d - prev).days == 1 else 1
        best = max(best, run); prev = d
    return cur, best

def build_status():
    G = goals()
    alllogs = read_all_logs()
    wd = week_days()
    wdset = {x.isoformat() for x in wd}
    t = datetime.date.today()
    today = t.isoformat()
    yesterday = (t - datetime.timedelta(days=1)).isoformat()
    last_mon = wd[0] - datetime.timedelta(days=7)
    lastset = {(last_mon + datetime.timedelta(days=i)).isoformat() for i in range(7)}
    # 잔디: 시작일(goals의 started 중 가장 이른 날)부터 이번 주까지, 최대 5주
    try:
        start_date = min(datetime.date.fromisoformat(g.get('started')) for g in G.values() if g.get('started'))
    except (ValueError, TypeError):
        start_date = t
    start_mon = start_date - datetime.timedelta(days=start_date.weekday())
    weeks = min(5, (wd[0] - start_mon).days // 7 + 1)
    heat_start = wd[0] - datetime.timedelta(days=7*(weeks-1))
    heat_days = [(heat_start + datetime.timedelta(days=i)) for i in range(weeks*7)]
    day_n = (t - start_date).days + 1
    res = {}
    for hid, g in G.items():
        dm = day_minutes(alllogs, hid)
        tags = {}
        for e in alllogs:
            if e.get('habit') != hid: continue
            tg = (e.get('tag') or '').strip()
            if not tg: continue
            m = int(e.get('minutes',0) or 0); d = str(e.get('ts',''))[:10]
            v = tags.setdefault(tg, {'week':0,'total':0,'last':''})
            v['total'] += m
            if d in wdset: v['week'] += m
            if e.get('ts','') > v['last']: v['last'] = e.get('ts','')
        week_min = sum(m for d,m in dm.items() if d in wdset)
        last_week_min = sum(m for d,m in dm.items() if d in lastset)
        total_min = sum(dm.values())
        cur, best = streaks(set(dm.keys()))
        heat = []
        for d in heat_days:
            ds = d.isoformat()
            if d < start_date: m = -2          # 시작 전: 숨김
            elif d > t:        m = -1          # 미래: 잠긴 칸
            else:              m = dm.get(ds, 0)
            heat.append({'d': ds, 'm': m})
        recent = []
        seen = set()
        for e in reversed(alllogs):
            if e.get('habit') != hid: continue
            note = (e.get('note') or '').strip()
            if not note or note in seen: continue
            seen.add(note)
            recent.append({'note': note, 'tag': (e.get('tag') or '').strip()})
            if len(recent) >= 5: break
        votes = sum(1 for e in alllogs if e.get('habit') == hid)
        res[hid] = {
            'recent': recent,
            'votes': votes,
            'yesterday_done': yesterday in dm,
            'day_n': day_n,
            'label': g.get('label',''), 'emoji': g.get('emoji',''),
            'week_days': [x.isoformat() in dm for x in wd],
            'today_done': today in dm,
            'week_minutes': week_min,
            'last_week_minutes': last_week_min,
            'weekly_target': int(g.get('weekly_target_minutes',0) or 0),
            'total_minutes': total_min,
            'total_target': int(g.get('total_target_minutes',0) or 0),
            'streak_current': cur, 'streak_best': best,
            'heat': heat,
            'tags': [{'name':k,'week_minutes':v['week'],'total_minutes':v['total']}
                     for k,v in sorted(tags.items(), key=lambda kv: kv[1]['last'], reverse=True)][:8],
        }
    return res

def notion_create(habit, note, minutes, date_iso, tag=''):
    tk = token()
    if not tk:
        return False, 'no-token', None
    g = goals().get(habit, {})
    ds = str(g.get('notion_data_source','')).replace('collection://','')
    if not ds:
        return False, 'no-db-id', None
    title = note or f"{g.get('label','')} 세션"
    if tag:
        title = f"[{tag}] {title}" if not note else f"[{tag}] {note}"
    props = {
        '이름': {'title': [{'text': {'content': title}}]},
        '날짜': {'date': {'start': date_iso}},
        '분': {'number': minutes},
    }
    if tag:
        props['태그'] = {'select': {'name': tag}}
    props['주차'] = {'rich_text': [{'text': {'content': iso_week(datetime.date.fromisoformat(date_iso))}}]}
    propsets = [props]
    if '태그' in props: propsets.append({k:v for k,v in props.items() if k!='태그'})
    propsets.append({k:v for k,v in props.items() if k!='주차'})
    propsets.append({k:v for k,v in props.items() if k not in ('태그','주차')})
    attempts = []
    for ps in propsets:
        attempts.append(({'type':'data_source_id','data_source_id': ds}, '2025-09-03', ps))
        attempts.append(({'type':'database_id','database_id': ds}, '2022-06-28', ps))
    last_err = ''
    for parent, ver, props in attempts:
        try:
            req = urllib.request.Request('https://api.notion.com/v1/pages',
                data=json.dumps({'parent': parent, 'properties': props}).encode(),
                headers={'Authorization': f'Bearer {tk}', 'Notion-Version': ver,
                         'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=12) as r:
                resp = json.load(r)
            return True, 'ok', resp.get('url')
        except urllib.error.HTTPError as e:
            try: last_err = e.read().decode()[:300]
            except Exception: last_err = str(e)
        except Exception as e:
            last_err = str(e)
    return False, last_err, None

def append_log(habit, minutes, note, synced, url, tag=''):
    now = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    entry = {'ts': now, 'habit': habit, 'minutes': minutes, 'note': note,
             'links': [url] if url else [], 'synced': synced}
    if tag: entry['tag'] = tag
    os.makedirs(f'{BASE}/data/logs', exist_ok=True)
    with open(log_path(datetime.date.today()), 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

def report_state_path():
    return f'{BASE}/data/.last_report'

def generate_weekly_report():
    """지난주(월~일) 리포트 페이지를 노션 부모 페이지에 생성"""
    if not REPORT_PARENT_PAGE: return True, 'no-parent-configured'
    tk = token()
    if not tk: return False, 'no-token'
    t = datetime.date.today()
    this_mon = t - datetime.timedelta(days=t.weekday())
    last_mon = this_mon - datetime.timedelta(days=7)
    last_sun = this_mon - datetime.timedelta(days=1)
    wk = iso_week(last_mon)
    lastset = {(last_mon + datetime.timedelta(days=i)).isoformat() for i in range(7)}
    G = goals(); logs = read_all_logs()
    lines = []; total_all = 0; goals_met = 0; active = 0
    for hid, g in G.items():
        dm = {}; tagm = {}
        for e in logs:
            if e.get('habit') != hid: continue
            d = str(e.get('ts',''))[:10]
            if d not in lastset: continue
            m = int(e.get('minutes',0) or 0)
            dm[d] = dm.get(d,0)+m
            tg = (e.get('tag') or '').strip()
            if tg: tagm[tg] = tagm.get(tg,0)+m
        wkmin = sum(dm.values()); total_all += wkmin
        tgt = int(g.get('weekly_target_minutes',0) or 0)
        pct = round(wkmin/tgt*100) if tgt else 0
        met = tgt and wkmin >= tgt
        if met: goals_met += 1
        if wkmin: active += 1
        h = lambda m: f"{m/60:.1f}".rstrip('0').rstrip('.')
        line = f"{g.get('emoji','')} {g.get('label','')} — {h(wkmin)}h / {h(tgt)}h ({pct}%){' ✅' if met else ''} · {len(dm)}일 기록"
        if tagm:
            top = sorted(tagm.items(), key=lambda kv:-kv[1])[:4]
            line += " · " + ", ".join(f"{k} {h(v)}h" for k,v in top)
        lines.append(line)
    if total_all == 0:
        return True, 'empty-week'   # 기록 없는 주는 리포트 생략
    month = last_mon.month
    wom = (last_mon.day - 1)//7 + 1
    title = f"📊 {last_mon.year}년 {month}월 {wom}주차 습관 리포트 ({wk})"
    h = lambda m: f"{m/60:.1f}".rstrip('0').rstrip('.')
    summary = f"주간 총 {h(total_all)}h · 목표 달성 {goals_met}/{len(G)}개 · 활동 {active}/{len(G)}개 영역"
    children = [
        {"object":"block","type":"heading_2","heading_2":{"rich_text":[{"text":{"content":f"{last_mon.strftime('%m/%d')} ~ {last_sun.strftime('%m/%d')}"}}]}},
        {"object":"block","type":"paragraph","paragraph":{"rich_text":[{"text":{"content":summary},"annotations":{"bold":True}}]}},
    ] + [
        {"object":"block","type":"paragraph","paragraph":{"rich_text":[{"text":{"content":l}}]}} for l in lines
    ]
    payload = {
        "parent": {"type":"page_id","page_id": REPORT_PARENT_PAGE},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": children,
    }
    req = urllib.request.Request('https://api.notion.com/v1/pages',
        data=json.dumps(payload).encode(),
        headers={'Authorization': f'Bearer {tk}', 'Notion-Version': '2022-06-28',
                 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15):
        pass
    return True, 'created'

def maybe_weekly_report():
    """이번 주 들어 처음 status 조회 시 지난주 리포트 생성 (성공 시 1회)"""
    global _last_report_attempt
    import time as _t
    t = datetime.date.today()
    this_wk = iso_week(t)
    try:
        done = open(report_state_path()).read().strip()
    except FileNotFoundError:
        done = ''
    if done == this_wk: return
    if not done:
        # 최초 실행: 과거 주 리포트 소급 생성 없이 이번 주를 기준점으로
        open(report_state_path(),'w').write(this_wk); return
    if _t.time() - _last_report_attempt < 6*3600: return
    _last_report_attempt = _t.time()
    try:
        ok, msg = generate_weekly_report()
        if ok:
            open(report_state_path(),'w').write(this_wk)
    except Exception:
        pass

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {})

    def do_GET(self):
        if self.path.startswith('/status'):
            try:
                maybe_weekly_report()
                self._send(200, build_status())
            except Exception as e: self._send(500, {'error': str(e)})
        elif self.path == '/' or self.path.startswith('/dashboard'):
            try:
                body = open(f'{BASE}/dashboard/index.html', encoding='utf-8').read().encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._send(404, {'error': 'dashboard/index.html not found'})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        if not self.path.startswith('/log'):
            return self._send(404, {'error': 'not found'})
        try:
            n = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(n) or b'{}')
            habit = data.get('habit')
            minutes = int(data.get('minutes', 0) or 0)
            note = (data.get('note') or '').strip()
            if habit not in goals() or minutes <= 0 or minutes > 960:
                return self._send(400, {'error': 'bad habit/minutes'})
            tag = (data.get('tag') or '').strip()[:30]
            ok, msg, url = notion_create(habit, note, minutes, datetime.date.today().isoformat(), tag)
            append_log(habit, minutes, note, ok, url, tag)
            self._send(200, {'saved': True, 'notion': ok, 'notion_msg': msg,
                             'status': build_status()})
        except Exception as e:
            self._send(500, {'error': str(e)})

    def log_message(self, *a):  # quiet
        pass

def reminder_loop():
    import time as _t, subprocess as _sp
    while True:
        try:
            if REMINDER_TIME:
                now = datetime.datetime.now()
                if now.strftime('%H:%M') == REMINDER_TIME:
                    state = f'{BASE}/data/.last_remind'
                    try: done = open(state).read().strip()
                    except FileNotFoundError: done = ''
                    today = datetime.date.today().isoformat()
                    if done != today:
                        st = build_status()
                        todo = [v for v in st.values() if not v['today_done']]
                        if todo and len(todo) < len(st) + 1:
                            names = ' '.join(f"{v['emoji']}{v['label']}" for v in todo[:4])
                            risky = [v for v in todo if v['streak_current'] >= 2]
                            tail = f" — 🔥{max(v['streak_current'] for v in risky)}일 스트릭이 위험해요!" if risky else " — 5분이라도 1표!"
                            msg = f"오늘 아직: {names}{tail}"
                            _sp.run(['osascript','-e',
                                f'display notification "{msg}" with title "🐶 강아지들이 기다려요" sound name "Glass"'],
                                timeout=10)
                        open(state,'w').write(today)
        except Exception:
            pass
        _t.sleep(45)

if __name__ == '__main__':
    import threading
    threading.Thread(target=reminder_loop, daemon=True).start()
    HTTPServer(('127.0.0.1', PORT), H).serve_forever()
