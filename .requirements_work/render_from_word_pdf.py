from pathlib import Path
import sys, importlib.util
skill=Path('C:/Users/xxz/.codex/plugins/cache/openai-primary-runtime/documents/26.1011.11113/skills/documents')
spec=importlib.util.spec_from_file_location('render_docx',skill/'render_docx.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
pdf=Path(sys.argv[2]).resolve()
def native_export_pdf(*args,**kwargs):return str(pdf),'PDF exported with native Word; bundled LibreOffice unavailable in Windows runtime.'
mod.convert_to_pdf=native_export_pdf
pages=mod.rasterize(sys.argv[1],sys.argv[3],150,True,False)
print('pages',len(pages))
