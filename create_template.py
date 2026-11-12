"""Generate a minimal A4 scientific-paper reference.docx for Pandoc."""
from pathlib import Path
import subprocess
import shutil
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
out = ROOT / 'templates' / 'reference.docx'
out.parent.mkdir(exist_ok=True)
pandoc = shutil.which('pandoc')
if not pandoc:
    raise SystemExit('请先安装 Pandoc，才能生成完整的 reference.docx')
# Use Pandoc's own reference document as the base! Creating one from a blank
# python-docx document drops the custom 'Table' and 'Compact' styles required
# by the writer, which can break tables badly in LibreOffice/Word.
source = subprocess.check_output([pandoc, '--print-default-data-file', 'reference.docx'])
out.write_bytes(source)
doc = Document(out)
sec=doc.sections[0]
sec.page_width,sec.page_height=Cm(21),Cm(29.7)
sec.left_margin=sec.right_margin=Cm(2.5)
sec.top_margin=sec.bottom_margin=Cm(2.3)

def base_style(name,font_cn,font_latin,size,bold=False,after=0,before=0):
    st=doc.styles[name.replace("Heading ","Heading") if name.startswith("Heading ") else name]
    st.font.name=font_latin
    st.font.size=Pt(size)
    st.font.bold=bold
    st.font.color.rgb=RGBColor(28,38,54)
    rpr=st.element.get_or_add_rPr()
    rf=rpr.rFonts
    if rf is None:
        rf=OxmlElement('w:rFonts');rpr.insert(0,rf)
    rf.set(qn('w:eastAsia'), font_cn)
    st.paragraph_format.space_after=Pt(after)
    st.paragraph_format.space_before=Pt(before)
    return st
normal=base_style('Normal','宋体','Times New Roman',11,after=7)
normal.paragraph_format.line_spacing=1.35
base_style('Title','微软雅黑','Arial',18,bold=True,after=15,before=5)
base_style('Heading 1','微软雅黑','Arial',16,bold=True,after=10,before=15)
base_style('Heading 2','微软雅黑','Arial',13,bold=True,after=8,before=12)
base_style('Heading 3','微软雅黑','Arial',11.5,bold=True,after=6,before=10)
base_style('Caption','宋体','Times New Roman',10,after=7,before=7)
for sty in ['Compact']:
    if sty in doc.styles:
        base_style(sty,'宋体','Times New Roman',10)
doc.save(out)
print('Created',out)
