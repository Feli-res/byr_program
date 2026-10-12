from pathlib import Path
from zipfile import ZipFile
from copy import deepcopy
from lxml import etree as E
import hashlib, json

root=Path(__file__).resolve().parent.parent
ref=root/'软件工程需求分析-教学用表.docx'
out=root/'北邮校园综合交互论坛_需求分析文档.docx'
work=root/'.requirements_work'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'
def text(p): return ''.join(p.itertext()) if False else ''.join(p.xpath('.//w:t/text()',namespaces=NS))
with ZipFile(ref) as z:
    original={i.filename:z.read(i.filename) for i in z.infolist()}
    infos=z.infolist()
doc=E.fromstring(original['word/document.xml'])
body=doc.find('w:body',NS)
paras=body.findall('w:p',NS)
patterns={'H1':deepcopy(paras[17]), 'H2':deepcopy(paras[20]), 'H3':deepcopy(paras[32]), 'P':deepcopy(paras[19])}
def set_text(p,s):
    rp=p.find('w:r/w:rPr',NS)
    for child in list(p):
        if child.tag != W+'pPr': p.remove(child)
    r=E.SubElement(p,W+'r')
    if rp is not None: r.append(deepcopy(rp))
    t=E.SubElement(r,W+'t');t.text=s;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    return r
set_text(paras[5],'题目：北邮校园综合交互论坛')
# The longer project title uses the same source cover type and centered placement.
pp=paras[5].find('w:pPr',NS)
ind=pp.find('w:ind',NS)
if ind is not None: pp.remove(ind)
jc=E.SubElement(pp,W+'jc');jc.set(W+'val','center')
set_text(paras[16],'2026 年 10 月')
for p in paras[17:]: body.remove(p)
sect=body.find('w:sectPr',NS)
rows=[]
for line in (work/'requirements.txt').read_text('utf-8').splitlines():
    kind,s=line.split('|',1); p=deepcopy(patterns[kind]);set_text(p,s)
    pp=p.find('w:pPr',NS)
    if pp is None: pp=E.Element(W+'pPr');p.insert(0,pp)
    if kind.startswith('H'):
        keep=E.SubElement(pp,W+'keepNext');keep.set(W+'val','1')
        level=E.SubElement(pp,W+'outlineLvl');level.set(W+'val',{'H1':'0','H2':'1','H3':'2'}[kind])
        color=E.SubElement(p.find('w:r',NS).find('w:rPr',NS) if p.find('w:r/w:rPr',NS) is not None else E.SubElement(p.find('w:r',NS),W+'rPr'),W+'color');color.set(W+'val','000000')
    else:
        widow=E.SubElement(pp,W+'widowControl');widow.set(W+'val','1')
    if kind=='H1' and s.startswith('1、'):
        br=E.SubElement(pp,W+'pageBreakBefore');br.set(W+'val','1')
    body.insert(body.index(sect),p);rows.append((kind,s))
original['word/document.xml']=E.tostring(doc,xml_declaration=True,encoding='UTF-8',standalone=True)
with ZipFile(out,'w') as z:
    for info in infos:z.writestr(info,original[info.filename])
with ZipFile(ref) as a,ZipFile(out) as b:
    changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
    assert changed==['word/document.xml'],changed
alltext='\n'.join(s for _,s in rows)
for forbidden in ['github','hnu-doc','jhserver','gygy','Old_docs','湖南大学','游戏邮件']:
    assert forbidden.lower() not in alltext.lower(),forbidden
expected=['1.1','1.2','1.3','2.1','2.2','2.3','2.4','2.4.1','2.4.2','2.4.3','2.4.4','2.5','2.6','2.7','3.1','3.2','3.3','3.4']
for heading in expected:assert any(k.startswith('H') and s.startswith(heading+'、') for k,s in rows),heading
print(json.dumps({'output':str(out),'paragraphs':len(rows),'characters':len(alltext),'changed_parts':changed,'reference_sha256':hashlib.sha256(ref.read_bytes()).hexdigest()},ensure_ascii=False))
