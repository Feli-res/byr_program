from pathlib import Path
from PIL import Image, ImageChops
import importlib.util
import json
import os

root = Path(__file__).resolve().parent.parent
work = root / '.requirements_work' / 'no-codex-comments-20261020'
paths = sorted((work / 'native-pages').glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
assert paths and [int(p.stem.split('-')[-1]) for p in paths] == list(range(1, len(paths) + 1))
images = [Image.open(p).convert('RGB') for p in paths]
pdf = work / 'native-layout.pdf'
images[0].save(pdf, 'PDF', resolution=168, save_all=True, append_images=images[1:])
poppler = r'C:\Users\xxz\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin'
os.environ['PATH'] = poppler + os.pathsep + os.environ.get('PATH', '')
skill = Path('C:/Users/xxz/.codex/plugins/cache/openai-primary-runtime/documents/26.1015.12040/skills/documents')
spec = importlib.util.spec_from_file_location('render_docx', skill / 'render_docx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.convert_to_pdf = lambda *args, **kwargs: (str(pdf), 'Native Word rendering fallback; bundled LibreOffice unavailable on Windows.')
result = module.rasterize(str(work / 'updated-requirements.docx'), str(work / 'verified-render'), 150, True, False)
assert len(result) == len(paths)
comparison = {}
previous = root / '.requirements_work' / 'requirements-cleanup' / 'native-pages'
for path, image in zip(paths, images):
    old_path = previous / path.name
    if old_path.exists():
        old = Image.open(old_path).convert('RGB')
        comparison[path.stem] = old.size == image.size and ImageChops.difference(old, image).getbbox() is None
report = {'page_count': len(paths), 'compared_to_previously_reviewed_pages': comparison}
(work / 'render-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps(report, ensure_ascii=False))
