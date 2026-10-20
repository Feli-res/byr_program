from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
work = Path(__file__).resolve().parent / 't01-20261020'
paths = sorted((work/'native-pages').glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
assert paths
pages = [Image.open(p).convert('RGB') for p in paths]
pdf = work/'native-layout.pdf'
pages[0].save(pdf,'PDF',resolution=168,save_all=True,append_images=pages[1:])
os.environ['PATH'] = r'C:\Users\xxz\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin' + os.pathsep + os.environ.get('PATH','')
skill = Path(r'C:\Users\xxz\.codex\plugins\cache\openai-primary-runtime\documents\26.1015.12040\skills\documents')
spec=importlib.util.spec_from_file_location('render_docx',skill/'render_docx.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.convert_to_pdf=lambda *args,**kwargs:(str(pdf),'Native Word read-only page rendering; canonical renderer reported LibreOffice unavailable.')
results=module.rasterize(str(work/'updated-requirements.docx'),str(work/'verified-render'),150,True,False)
assert len(results)==len(paths)
width=360
height=max(int(p.height/p.width*width) for p in pages)
sheet=Image.new('RGB',(width*3,(height+28)*((len(pages)+2)//3)),'white')
draw=ImageDraw.Draw(sheet)
for i,p in enumerate(pages):
    x,y=(i%3)*width,(i//3)*(height+28)
    draw.text((x+10,y+5),f'Page {i+1}',fill='black')
    sheet.paste(ImageOps.contain(p,(width,height)),(x,y+28))
sheet.save(work/'contact-sheet.png')
mapping=json.loads((work/'native-page-text.json').read_text('utf-8-sig'))
for p in mapping:
    t=p['text'].strip().replace('\r',' / ').replace('\x0c','')
    print(p['page'],len(t),t[:65], '...',t[-65:])
print('Rendered',len(paths),'pages', [p.size for p in pages])
