from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from xml.etree import ElementTree as E
import hashlib
import json
import os
import re
import sys
import tempfile

target = Path(sys.argv[1]).resolve()
minutes = int(sys.argv[2])
assert minutes >= 0
original = target.read_bytes()
original_hash = hashlib.sha256(original).hexdigest()
with ZipFile(target) as source:
    entries = source.infolist()
    contents = {item.filename: source.read(item.filename) for item in entries}
    archive_comment = source.comment

part = 'docProps/app.xml'
namespace = 'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'
root = E.fromstring(contents[part])
node = root.find('{' + namespace + '}TotalTime')
assert node is not None, 'Expected existing TotalTime property.'
previous = node.text
pattern = rb'(<(?:[A-Za-z_][\w.-]*:)?TotalTime\b[^>]*>)\s*\d+\s*(</(?:[A-Za-z_][\w.-]*:)?TotalTime>)'
updated, count = re.subn(pattern, lambda m: m.group(1) + str(minutes).encode('ascii') + m.group(2), contents[part])
assert count == 1
node.text = str(minutes)
assert E.tostring(root) == E.tostring(E.fromstring(updated)), 'Unexpected property changes.'

work = target.parent.parent / '.requirements_work' / ('total-edit-time-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
work.mkdir(parents=True, exist_ok=False)
(work / 'before.docx').write_bytes(original)
fd, temp_name = tempfile.mkstemp(prefix='.edit-time-', suffix='.docx', dir=target.parent)
os.close(fd)
temporary = Path(temp_name)
try:
    with ZipFile(temporary, 'w') as result:
        result.comment = archive_comment
        for info in entries:
            result.writestr(info, updated if info.filename == part else contents[info.filename])
    with ZipFile(temporary) as result:
        assert result.testzip() is None
        assert result.namelist() == list(contents)
        assert all(result.read(name) == data for name, data in contents.items() if name != part)
        assert result.read(part) == updated
    assert hashlib.sha256(target.read_bytes()).hexdigest() == original_hash, 'Source changed during edit.'
    os.replace(temporary, target)
    with ZipFile(target) as result:
        actual = E.fromstring(result.read(part)).find('{' + namespace + '}TotalTime')
        assert actual.text == str(minutes)
        assert all(result.read(name) == data for name, data in contents.items() if name != part)
    report = {'previous_minutes': int(previous), 'total_minutes': minutes, 'only_changed_part': part,
              'other_parts_byte_identical': True, 'source_sha256': original_hash,
              'result_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (work / 'verification.json').write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps(report))
finally:
    if temporary.exists():
        temporary.unlink()
