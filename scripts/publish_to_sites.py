"""Publish original exporter JSON atomically to the password-protected company site.

Authentication uses GitHub Actions OIDC, scoped to this repo's main publishing
workflow. No website password or long-lived publishing secret is needed.
"""
import hashlib,json,os,pathlib,sqlite3,time,urllib.request,urllib.parse,urllib.error,base64
SITE=os.environ['ZF_PUBLISH_SITE'].rstrip('/')
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'site'/'data'
_token=None
_expiry=0
def oidc():
 global _token,_expiry
 if _token and time.time()<_expiry:return _token
 req=urllib.request.Request(os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']+'&audience='+urllib.parse.quote(SITE,safe=''),headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
 with urllib.request.urlopen(req,timeout=30) as r:_token=json.load(r)['value']
 # Log only non-secret identity claims, never the JWT or signature.
 part=_token.split('.')[1];claims=json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))
 print('Publisher identity:',{k:claims.get(k) for k in ('iss','aud','repository_id','repository_owner_id','ref','workflow_ref','sub','run_number')},flush=True)
 _expiry=time.time()+120
 return _token
def request(path,method='GET',payload=None):
 body=payload if isinstance(payload,bytes) else (json.dumps(payload,separators=(',',':')).encode() if payload is not None else None)
 for attempt in range(5):
  req=urllib.request.Request(SITE+path,data=body,method=method,headers={'X-ZF-Publisher-Token':oidc(),'Content-Type':'application/octet-stream' if isinstance(payload,bytes) else 'application/json','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'})
  try:
   with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
  except urllib.error.HTTPError as e:
   if e.code not in (429,500,502,503,504):raise RuntimeError('Publish request failed HTTP '+str(e.code)+': '+e.read(300).decode(errors='replace')) from None
   if attempt==4:raise RuntimeError('Publish retry limit reached') from None
  except (TimeoutError,urllib.error.URLError):
   if attempt==4:raise
  time.sleep(5*(attempt+1))
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
def main():
 files,blobs,counts,dates=prepare()
 print('Validated both markets:',counts,dates,flush=True)
 staged=request('/_publish/manifest','POST',{'files':files})
 for number,sha in enumerate(staged['missing'],1):
  request('/_publish/object/'+sha,'PUT',blobs[sha].read_bytes());print('Uploaded',number,'/',len(staged['missing']),flush=True)
 committed=request('/_publish/commit','POST',{})
 actual=request('/_publish/status')
 if actual['id']!=committed['id'] or actual['marketDates']!=dates:raise RuntimeError('Live readback did not match commit')
 print('Live website updated:',actual,flush=True)
if __name__=='__main__':main()
