from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from PIL import Image
import hashlib
import json
import os
import shutil

root = Path(__file__).resolve().parent.parent
work = root / '.requirements_work' / 'fras-update'
target = root / 'demand' / '北邮校园综合交互论坛_需求分析文档.docx'
draft = work / 'updated-requirements.docx'
evidence = json.loads((work / 'structural-verification.json').read_text('utf-8'))
assert hashlib.sha256(target.read_bytes()).hexdigest() == evidence['source_sha256'], 'Source changed during editing; preserve user changes.'
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with ZipFile(draft) as archive:
    document = E.fromstring(archive.read('word/document.xml'))
    assert len(document.xpath('//w:tbl/w:tr[w:trPr/w:tblHeader]', namespaces=ns)) == 2
    comments = E.fromstring(archive.read('word/comments.xml'))
    comment_ids = set(comments.xpath('w:comment/@w:id', namespaces=ns))
    for tag in ['commentRangeStart', 'commentRangeEnd', 'commentReference']:
        ids = document.xpath('//w:' + tag + '/@w:id', namespaces=ns)
        assert len(ids) == 8 and set(ids) == comment_ids
    rels = E.fromstring(archive.read('word/_rels/document.xml.rels'))
    links = [item for item in rels if item.get('Type', '').endswith('/hyperlink')]
    assert len(links) == 10 and all('892e0b14d2a784c833597ecb9fc91f2a41b996d2' in item.get('Target', '') for item in links)
    full_text = '\n'.join(document.xpath('//w:t/text()', namespaces=ns))
    assert '不接入校园 CAS' in full_text and '5.7、源码依据与检查版本' in full_text
renders = list((work / 'verified-final-render').glob('page-*.png'))
assert len(renders) == 13

date_image = Image.open(work / 'native-final-pages' / 'cover-date.png').convert('RGBA')
background = Image.new('RGBA', date_image.size, 'white')
background.alpha_composite(date_image)
background.convert('RGB').save(work / 'cover-date-white.png')

temporary = target.with_name('.fras-verified-requirements.docx')
shutil.copyfile(draft, temporary)
os.replace(temporary, target)
assert target.read_bytes() == draft.read_bytes()
evidence.update({'final_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'word_pages': 13, 'visual_review': 'All thirteen final native Word page images reviewed; tables and source-page pagination checked.'})
(work / 'final-verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps({'updated': str(target), 'pages': 13, 'source_links': 10, 'comments': 8, 'backup_preserved': True}, ensure_ascii=False))
