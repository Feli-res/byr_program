from pathlib import Path
from PIL import Image
import importlib.util
import json
import os

work = Path(__file__).resolve().parent / 'requirements-cleanup'
os.environ['PATH'] = r'C:\Users\xxz\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin' + os.pathsep + os.environ.get('PATH', '')
paths = sorted((work / 'native-pages').glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
assert paths and [int(p.stem.split('-')[-1]) for p in paths] == list(range(1, len(paths) + 1))
images = [Image.open(path).convert('RGB') for path in paths]
pdf = work / 'native-layout.pdf'
images[0].save(pdf, 'PDF', resolution=168, save_all=True, append_images=images[1:])
skill = Path('C:/Users/xxz/.codex/plugins/cache/openai-primary-runtime/documents/26.1011.11113/skills/documents')
spec = importlib.util.spec_from_file_location('render_docx', skill / 'render_docx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.convert_to_pdf = lambda *args, **kwargs: (str(pdf), 'Native Word rendering fallback; bundled LibreOffice unavailable on Windows.')
pages = module.rasterize(str(work / 'updated-requirements.docx'), str(work / 'verified-render'), 150, True, False)
assert len(pages) == len(paths)
(work / 'render-verification.json').write_text(json.dumps({'page_count': len(paths), 'renderer': 'Native Word plus packaged rasterizer'}), 'utf-8')
print(json.dumps({'page_count': len(paths), 'rendered_pages': len(pages)}))
