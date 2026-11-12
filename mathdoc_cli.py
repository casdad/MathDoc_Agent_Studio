"""MathDoc command line entry point, usable as a local Agent Skill."""
import argparse
import json
from pathlib import Path
from server import parse_markdown, docx_bytes, count_docx_equations, require_pandoc


def main():
    parser=argparse.ArgumentParser(description='MathDoc: Markdown + LaTeX -> editable Word OMML')
    sub=parser.add_subparsers(dest='command',required=True)
    convert=sub.add_parser('convert',help='Convert Markdown to Word')
    convert.add_argument('input',type=Path)
    convert.add_argument('-o','--output',type=Path,required=True)
    audit=sub.add_parser('audit',help='Count OMML equations in DOCX')
    audit.add_argument('input',type=Path)
    args=parser.parse_args()
    if args.command=='convert':
        require_pandoc()
        txt=args.input.read_text(encoding='utf-8-sig')
        ast,math,warnings=parse_markdown(txt)
        doc,warnings2=docx_bytes(ast)
        num=count_docx_equations(doc)
        if num!=len(math):
            raise SystemExit(f'OMML 数量不匹配：源 {len(math)}，目标 {num}。已终止输出。')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(doc)
        print(json.dumps({'file':str(args.output),'input_equations':len(math),
                          'output_omml':num,'warnings':(warnings+warnings2).strip()},ensure_ascii=False))
    else:
        doc=args.input.read_bytes()
        print(json.dumps({'file':str(args.input),'omml_equations':count_docx_equations(doc)},ensure_ascii=False))

if __name__=='__main__':main()
