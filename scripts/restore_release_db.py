"""Fail closed: never start an empty database after a download failure."""
import argparse,gzip,pathlib,sqlite3,subprocess,tempfile,time,os
def main():
 p=argparse.ArgumentParser();p.add_argument('market',choices=['tw','us']);args=p.parse_args()
 tag,name,dest,table=('db-backup','zf_trend_full.db.gz','zf_trend.db','daily_price') if args.market=='tw' else ('us-db-backup','zf_trend_us.db.gz','zf_trend_us.db','us_daily_price')
 out=pathlib.Path('data')/dest;out.parent.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory() as temp:
  folder=pathlib.Path(temp)
  for attempt in range(1,6):
   try:
    subprocess.run(['gh','release','download',tag,'--repo',os.environ['GITHUB_REPOSITORY'],'--pattern',name,'--dir',temp,'--clobber'],check=True)
    restored=folder/'restored.db'
    with gzip.open(folder/name,'rb') as src,restored.open('wb') as dst:
     import shutil
     shutil.copyfileobj(src,dst)
    conn=sqlite3.connect('file:'+str(restored)+'?mode=ro',uri=True)
    try:
     if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok' or conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]<=0:raise ValueError('Invalid or empty database')
    finally:conn.close()
    os.replace(restored,out);print('Restored',args.market,'on attempt',attempt);return
   except Exception as error:
    print('Restore attempt',attempt,'failed:',type(error).__name__,flush=True)
    if attempt<5:time.sleep(20)
  raise SystemExit('Database restore failed; existing website and backup are preserved')
if __name__=='__main__':main()
