from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import json

root = Path(__file__).resolve().parent.parent
target = root / 'demand' / '北邮校园综合交互论坛_需求分析文档.docx'
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with ZipFile(target) as z:
    doc = E.fromstring(z.read('word/document.xml'))
    body = doc.find('w:body', ns)
    for i, p in enumerate(body.findall('w:p', ns)):
        text = ''.join(p.xpath('.//w:t/text()', namespaces=ns))
        if text.strip():
            print(str(i) + ': ' + text)
    print('SECTIONS', [E.tostring(s, encoding='unicode') for s in body.findall('w:sectPr', ns)])
    for p in body.findall('w:p', ns):
        text = ''.join(p.xpath('.//w:t/text()', namespaces=ns))
        if text.startswith(('1、任务', '1.1、', '4、尚', '（1）校园')):
            print('FORMAT', text, E.tostring(p, encoding='unicode')[:2200])
    print('COMMENTS', 'word/comments.xml' in z.namelist())
