import sys,json,asyncio,re,xml.etree.ElementTree as ET
sys.path.insert(0, r'C:/_git/xcel/src')
from ieee20305_client.client import IEEE20305Client, IEEE20305ClientConfig
md=json.load(open(r'C:/_git/xcel/.secrets/ieee20305/xcel-compat/metadata.json','r',encoding='utf-8'))
cfg=IEEE20305ClientConfig(endpoint='https://10.0.2.71:8081', client_cert=md.get('client_cert') or md.get('cert'), client_key=md.get('client_key') or md.get('key'), ca_cert=md.get('ca_cert') or md.get('ca') or md.get('cert'), mode='real', agent_version='auto')
c=IEEE20305Client(cfg)
async def main():
 dcap=await c._request_text('/dcap')
 upl=c._find_link_href(dcap,'UsagePointListLink')
 print('LINK UsagePointListLink',upl)
 upl_xml=await c._request_text(upl)
 hrefs=sorted(set(re.findall(r'href="([^"]+)"',upl_xml)))
 print('UPL_HREFS',hrefs)
 for p in ['/upt/1','/upt/1/mr']:
  x=await c._request_text(p)
  hs=sorted(set(re.findall(r'href="([^"]+)"',x)))
  print('PATH',p,'HREFS',hs)
  if p.endswith('/mr'):
   root=ET.fromstring(x)
   for mr in [e for e in root.iter() if e.tag.split('}',1)[-1]=='MeterReading']:
    mhref=mr.attrib.get('href','')
    rl=''
    rtl=''
    for ch in list(mr):
      n=ch.tag.split('}',1)[-1]
      if n=='ReadingListLink': rl=ch.attrib.get('href','')
      if n=='ReadingTypeLink': rtl=ch.attrib.get('href','')
    print('MR',mhref,'RT',rtl,'R',rl)
 for path in ['/upt/1/rs','/upt/1/rt','/upt/1/r']:
  try:
   await c._request_text(path)
   print('PATH',path,'OK')
  except Exception as e:
   print('PATH',path,'ERR',type(e).__name__)
asyncio.run(main())
