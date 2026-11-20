"""Local demo server; not suitable for public deployment without authentication."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import explore

ROOT=Path(__file__).parent
DB=Path(os.environ.get('HOLLOW_DB',str(explore.DB_PATH)))

def execute(method,path,data=None,params=None):
    data=data or {};params=params or {}
    with explore.connect(DB) as con:
        if method=='GET':
            if path=='/api/map':return explore.map_data(con)
            if path=='/api/missions':return explore.missions(con)
            if path=='/api/summary':return explore.summary(con)
            if path=='/api/applications':return explore.applications(con,int(params['resident_id'])) if 'resident_id' in params else explore.applications(con)
            if path=='/api/reports':return explore.reports(con)
            if path=='/api/resident':return explore.resident(con,int(params.get('id',1)))
            if path=='/api/equipment':return explore.equipment(float(params.get('hours',2)),float(params.get('hazard',20)))
            if path=='/api/eligibility':return explore.eligibility(con,int(params['resident_id']),int(params['mission_id']))
        if method=='POST':
            if path=='/api/apply':return explore.apply(con,int(data['resident_id']),int(data['mission_id']))
            if path=='/api/decide':return explore.decide(con,int(data['application_id']),data['decision'])
            if path=='/api/start':return explore.start(con,int(data['application_id']))
            if path=='/api/report':return explore.submit_report(con,int(data['application_id']),data['findings'],data['resource_found'])
            if path=='/api/verify':return explore.verify_report(con,int(data['report_id']),data['approved'])
        raise ValueError('Unknown endpoint')

class Handler(BaseHTTPRequestHandler):
    def respond(self,status,body,ctype='application/json'):
        raw=(json.dumps(body).encode() if ctype=='application/json' else body)
        self.send_response(status)
        self.send_header('Content-Type',ctype+'; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        u=urlparse(self.path)
        if u.path=='/':
            return self.respond(200,(ROOT/'static'/'index.html').read_bytes(),'text/html')
        if u.path=='/app.js':
            return self.respond(200,(ROOT/'static'/'app.js').read_bytes(),'text/javascript')
        try:self.respond(200,execute('GET',u.path,params={k:v[0] for k,v in parse_qs(u.query).items()}))
        except (ValueError,KeyError,TypeError) as e:self.respond(400,{'error':str(e)})
    def do_POST(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size>20000: return self.respond(413,{'error':'Request too large'})
            data=json.loads(self.rfile.read(size))
            self.respond(200,execute('POST',urlparse(self.path).path,data))
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:self.respond(400,{'error':str(e)})

if __name__=='__main__':
    with explore.bootstrap(DB) as c: print('Demo residents ready:',c.execute('SELECT COUNT(*) FROM residents').fetchone()[0])
    print('HOLLOW-EXPLORE running at http://127.0.0.1:8765')
    print('LOCAL DEMO ONLY: coordinator endpoints are not authenticated.')
    ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
