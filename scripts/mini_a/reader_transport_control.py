import sys,pathlib,json,base64,urllib.request,time
from PIL import Image,ImageDraw
out=pathlib.Path(sys.argv[1]);model='qwen3.8:27b';rows=[]
for name,color in [('red','red'),('blue','blue')]:
 p=out/('control-'+name+'.png');im=Image.new('RGB',(400,400),'white');d=ImageDraw.Draw(im);d.rectangle((70,70,330,330),fill=color);im.save(p)
 payload={'model':model,'stream':False,'think':False,'messages':[{'role':'user','content':'What color is the single large shape? Answer with one color word only.','images':[base64.b64encode(p.read_bytes()).decode()]}],'options':{'temperature':0,'num_predict':50}}
 req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 start=time.time()
 try:
  raw=urllib.request.urlopen(req,timeout=180).read();(out/('control-response-'+name+'.json')).write_bytes(raw);r=json.loads(raw);answer=r.get('message',{}).get('content','').strip().lower().strip('.');row={'expected':name,'answer':answer,'passed':answer==name,'seconds':round(time.time()-start,1)}
 except Exception as e:row={'expected':name,'passed':False,'error':str(e)}
 rows.append(row);print(json.dumps(row),flush=True)
(out/'transport-control.json').write_text(json.dumps({'model':model,'tests':rows,'scope':'synthetic color controls only; does not establish roof-label accuracy'},indent=2))
