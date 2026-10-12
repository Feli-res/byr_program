from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import importlib.util
import json
import os

poppler = r'C:\Users\xxz\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin'
os.environ['PATH'] = poppler + os.pathsep + os.environ.get('PATH', '')

work = Path(__file__).resolve().parent / 'fras-update'
paths = sorted((work / 'native-final-pages').glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
assert paths and [int(p.stem.split('-')[-1]) for p in paths] == list(range(1, len(paths) + 1))
pages = [Image.open(path).convert('RGB') for path in paths]
pdf = work / 'native-final-layout.pdf'
pages[0].save(pdf, 'PDF', resolution=168, save_all=True, append_images=pages[1:])

skill = Path('C:/Users/xxz/.codex/plugins/cache/openai-primary-runtime/documents/26.1011.11113/skills/documents')
spec = importlib.util.spec_from_file_location('render_docx', skill / 'render_docx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def native_convert(*args, **kwargs):
    return str(pdf), 'Native Word page rendering used because bundled LibreOffice is unavailable on Windows.'
module.convert_to_pdf = native_convert
output = work / 'verified-final-render'
result = module.rasterize(str(work / 'updated-requirements.docx'), str(output), 150, True, False)
print(json.dumps({'native_page_count': len(pages), 'rasterized_page_count': len(result), 'native_sizes': [p.size for p in pages]}, ensure_ascii=False))

thumb_width = 310
thumb_height = int(pages[0].height / pages[0].width * thumb_width)
sheet = Image.new('RGB', (thumb_width * 4, (thumb_height + 26) * 4), 'white')
draw = ImageDraw.Draw(sheet)
for i, page in enumerate(pages):
    x, y = (i % 4) * thumb_width, (i // 4) * (thumb_height + 26)
    draw.text((x + 8, y + 6), f'Page {i+1}', fill='black')
    sheet.paste(ImageOps.contain(page, (thumb_width, thumb_height)), (x, y + 26))
sheet.save(work / 'final-contact-sheet.png')
