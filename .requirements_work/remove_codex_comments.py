from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import importlib.util
import json
import posixpath
import hashlib

root = Path(__file__).resolve().parent.parent
target = root / 'demand' / '北邮校园综合交互论坛_需求分析文档.docx'
work = root / '.requirements_work' / 'no-codex-comments-20261020'
work.mkdir(parents=True, exist_ok=True)
before = work / 'before.docx'
intermediate = work / 'stripped.docx'
draft = work / 'updated-requirements.docx'
before.write_bytes(target.read_bytes())
skill = Path('C:/Users/xxz/.codex/plugins/cache/openai-primary-runtime/documents/26.1015.12040/skills/documents')
spec = importlib.util.spec_from_file_location('comments_strip', skill / 'scripts' / 'comments_strip.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ns = {'w': module.W_NS}
with ZipFile(before) as archive:
    comments = E.fromstring(archive.read('word/comments.xml'))
    authors = [comment.get('{' + module.W_NS + '}author', '') for comment in comments]
    assert authors and all(author.casefold() == 'codex' for author in authors), 'Keep comments from other authors'
stats = module.strip_comments(str(before), str(intermediate))

with ZipFile(intermediate) as archive:
    infos = archive.infolist()
    parts = {info.filename: archive.read(info.filename) for info in infos}
removed_parts = {name for name in parts if posixpath.basename(name).lower().startswith('comments')}
for name in removed_parts:
    del parts[name]
for name in list(parts):
    if name.endswith('.rels'):
        tree = E.fromstring(parts[name])
        changed = False
        for relationship in list(tree):
            rel_type = relationship.get('Type', '').lower()
            rel_target = posixpath.basename(relationship.get('Target', '')).lower()
            if 'comments' in rel_type or rel_target.startswith('comments'):
                tree.remove(relationship)
                changed = True
        if changed:
            parts[name] = module._xml_bytes(tree)
ct = E.fromstring(parts['[Content_Types].xml'])
for override in list(ct):
    if posixpath.basename(override.get('PartName', '')).lower().startswith('comments'):
        ct.remove(override)
parts['[Content_Types].xml'] = module._xml_bytes(ct)
with ZipFile(draft, 'w') as archive:
    for info in infos:
        if info.filename in parts:
            archive.writestr(info, parts[info.filename])

with ZipFile(before) as source, ZipFile(draft) as result:
    assert not any('comments' in name.lower() for name in result.namelist())
    changed = []
    for name in result.namelist():
        if name.endswith(('.xml', '.rels')):
            tree = E.fromstring(result.read(name))
            assert not tree.xpath('//w:commentRangeStart|//w:commentRangeEnd|//w:commentReference', namespaces=ns)
            if name.startswith('word/') and not name.endswith('.rels'):
                old = E.fromstring(source.read(name))
                module._strip_comment_markup(old)
                assert E.tostring(old, method='c14n') == E.tostring(tree, method='c14n'), 'Non-comment XML changed: ' + name
        if source.read(name) != result.read(name):
            changed.append(name)
    for name in source.namelist():
        if not name.endswith(('.xml', '.rels')) and name in result.namelist():
            assert source.read(name) == result.read(name)
evidence = {
    'target': str(target), 'backup': str(before), 'draft': str(draft),
    'source_sha256': hashlib.sha256(before.read_bytes()).hexdigest(),
    'removed_comments': len(authors), 'remaining_comments': 0,
    'strip_stats': stats, 'extra_parts_removed': sorted(removed_parts),
    'changed_parts': changed,
    'body_styles_media_and_layout_xml_preserved': True,
}
(work / 'verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps(evidence, ensure_ascii=False))
