"""Add private collection routes to the existing Image Plane job-screen server."""
import json,re,sys
from pathlib import Path
BASE=Path.home()/'image-plane'
sys.path.insert(0,str(BASE))
import job_screen
old_get=job_screen.JobHandler.do_GET
ROOT=BASE/'incoming/worker/collection'
def get(self):
 path=self.path.split('?',1)[0]
 target=None;ctype='text/html; charset=utf-8'
 if path in ('/collection','/collection/'):target=ROOT/'view/index.html'
 elif re.fullmatch(r'/collection/job/(?:\d{3,4}-\d{2}|unresolved)',path):target=ROOT/'view'/(path.rsplit('/',1)[1]+'.html')
 elif re.fullmatch(r'/collection/thumb/[0-9a-f]{64}\.jpg',path):target=ROOT/'thumbs'/path.rsplit('/',1)[1];ctype='image/jpeg'
 elif path.startswith('/collection/'):
  self._send(404,'Not found','text/plain; charset=utf-8');return
 if target:
  if target.is_file():self._send(200,target.read_bytes(),ctype,extra={'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})
  else:self._send(503,'Collection batch is preparing this page.','text/plain; charset=utf-8')
  return
 return old_get(self)
job_screen.JobHandler.do_GET=get
if __name__=='__main__':job_screen.main()
