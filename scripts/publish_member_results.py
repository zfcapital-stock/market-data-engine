"""官網結果轉接器：只讀既有匯出結果，不重新計算選股或改資料庫。"""
import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    index = json.loads((source / 'index.json').read_text(encoding='utf-8'))
    stocks = index['stocks']
    if not all(any(s.get('m') == m for s in stocks.values()) for m in ('tw', 'us')):
        raise ValueError('台股、美股股票主檔均不可為空')
    by_date = defaultdict(list)
    months = {}
    for month in index['months']:
        if len(month) != 7 or not month[:4].isdigit() or month[4] != '-' or not month[5:].isdigit():
            raise ValueError('月份格式錯誤')
        rows = json.loads((source / 'months' / (month + '.json')).read_text(encoding='utf-8'))
        # 公司匯出另含消失追蹤；原版介面只呈現實際入選結果。
        rows = [{k: v for k, v in r.items() if k in ('id', 'd', 't', 's', 'h', 'r', 'g')}
                for r in rows if r.get('lc') not in ('missing', 'expired')]
        for row in rows:
            if row['id'] not in stocks or row['t'] not in ('vcp', 'sx', 'vol'):
                raise ValueError('未知股票或結果類型')
            by_date[row['d']].append(row)
        months[month] = rows
    if not by_date:
        raise ValueError('沒有結果；拒絕覆蓋既有版本')
    # 完整重現原版的同類型比較：使用全部篩選日，不改成新版聯集生命週期。
    history = deque(maxlen=20)
    known = []
    for day in sorted(by_date):
        prior = {kind: set() for kind in ('vcp', 'sx')}
        for previous in history:
            for kind in prior:
                prior[kind].update(previous[kind])
        if len(history) == 20:
            known.append(day)
        today = {kind: set() for kind in prior}
        for row in by_date[day]:
            kind = row['t']
            row['display_new'] = kind in prior and row['id'] not in prior[kind]
            if kind in today:
                today[kind].add(row['id'])
        history.append(today)
    # 不把新版生命週期參數、原始行情或計算中間值送到官網。
    index = {k: v for k, v in index.items() if k in (
        'stocks', 'months', 'mr', 'generated_at', 'total_records', 'total_stocks',
        'first_date', 'last_date', 'market_dates')}
    index['display_known_dates'] = known
    index['total_records'] = sum(map(len, months.values()))
    destination.mkdir(parents=True, exist_ok=True)
    files = {}
    def save(name, value):
        body = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        files[name] = {'sha256': hashlib.sha256(body).hexdigest(), 'size': len(body)}
    save('index.json', index)
    for month, rows in months.items():
        save('months/' + month + '.json', rows)
    return files



"""既有每日匯出完成後發布；只讀結果、不寫入資料庫。金鑰只從環境變數取得。"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit



class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把發布金鑰帶到重新導向的其他主機。
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()
    origin = os.environ['ZF_WORDPRESS_ORIGIN'].rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or parsed.path:
        raise ValueError('發布目的地必須是 HTTPS 網站根網址')
    key = os.environ['ZF_WORDPRESS_PUBLISH_KEY']
    if not 32 <= len(key) <= 256:
        raise ValueError('發布金鑰長度不正確')
    opener = urllib.request.build_opener(NoRedirect)
    def send(path, body):
        for attempt in range(4):
            request = urllib.request.Request(origin + '/wp-json/zf-results/v1/' + path,
                data=body, headers={'Content-Type': 'application/json', 'X-ZF-Publish-Key': key}, method='POST')
            try:
                with opener.open(request, timeout=90) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code not in (409, 429, 500, 502, 503, 504) or attempt == 3:
                    raise RuntimeError('官網發布失敗，HTTP ' + str(error.code)) from None
            except (TimeoutError, urllib.error.URLError):
                if attempt == 3:
                    raise RuntimeError('官網連線失敗，未完成發布') from None
            time.sleep(3 * (attempt + 1))
    with tempfile.TemporaryDirectory() as directory:
        files = prepare(args.data_dir, directory)
        expected = json.loads((Path(directory) / 'index.json').read_text(encoding='utf-8'))['market_dates']
        source_index = json.loads((args.data_dir / 'index.json').read_text(encoding='utf-8'))
        for market, day in expected.items():
            month_file = 'months/' + day[:7] + '.json'
            original = json.loads((args.data_dir / month_file).read_text(encoding='utf-8'))
            prepared = json.loads((Path(directory) / month_file).read_text(encoding='utf-8'))
            source_rows = [r for r in original if r['d'] == day and source_index['stocks'][r['id']]['m'] == market]
            prepared_rows = [r for r in prepared if r['d'] == day and source_index['stocks'][r['id']]['m'] == market]
            source_selected = {r['id'] for r in source_rows if r.get('lc') not in ('missing', 'expired')}
            output_selected = {r['id'] for r in prepared_rows}
            if source_selected != output_selected:
                raise RuntimeError('官網轉接前後入選股票不一致，拒絕發布')
            print(json.dumps({'market': market, 'date': day, 'source_selected_count': len(source_selected),
                'published_selected_count': len(output_selected), 'source_selected_symbols': sorted(source_selected),
                'excluded_tracking_rows': [{'id': r['id'], 'type': r['t'], 'status': r.get('lc')} for r in source_rows
                                           if r.get('lc') in ('missing', 'expired')]}, ensure_ascii=False), flush=True)
        for name, metadata in files.items():
            send('object/' + metadata['sha256'], (Path(directory) / name).read_bytes())
        result = send('commit', json.dumps({'files': files}).encode())
        if result.get('dates') != expected or not result.get('id'):
            raise RuntimeError('發布回傳版本不符')
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
