import hashlib,json,pathlib,sqlite3
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'site'/'data'
def prepare():
 index_path=DATA/'index.json'
 index=json.loads(index_path.read_text(encoding='utf-8'))
 counts={m:sum(1 for s in index['stocks'].values() if s.get('m')==m) for m in ('tw','us')}
 if not all(counts.values()) or index['total_records']<=0:raise ValueError('Both TW and US must contain stocks and records')
 dates={}
 for market,filename,table in [('tw','zf_trend.db','daily_price'),('us','zf_trend_us.db','us_daily_price')]:
  conn=sqlite3.connect('file:'+str(ROOT/'data'/filename)+'?mode=ro',uri=True)
  try:
   if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Corrupt '+market+' database')
   dates[market]=conn.execute('SELECT MAX(date) FROM '+table).fetchone()[0]
   if not dates[market]:raise ValueError('Missing '+market+' prices')
  finally:conn.close()
 index['market_dates']=dates
 index_path.write_text(json.dumps(index,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 files={};blobs={}
 for file in sorted(DATA.rglob('*.json')):
  body=file.read_bytes();sha=hashlib.sha256(body).hexdigest()
  files['/data/'+file.relative_to(DATA).as_posix()]={'sha':sha,'size':len(body)};blobs[sha]=file
 if any('/data/months/'+month+'.json' not in files for month in index['months']):raise ValueError('Missing month export')
 return files,blobs,counts,dates
if __name__=='__main__':
 files,blobs,counts,dates=prepare()
 print(json.dumps({'counts':counts,'dates':dates}))
