# -*- coding: utf-8 -*-
"""Dump the content of a .docx (paragraphs, styles, tables, inline images)."""
import sys
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def iter_block_items(parent):
    from docx.oxml.ns import qn
    body = parent.element.body
    for child in body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, parent)
        elif child.tag == qn('w:tbl'):
            yield Table(child, parent)


def main(path: str) -> None:
    doc = Document(path)
    print(f"=== FILE: {path} ===")
    print(f"paragraphs={len(doc.paragraphs)} tables={len(doc.tables)} "
          f"sections={len(doc.sections)} inline_shapes={len(doc.inline_shapes)}")
    core = doc.core_properties
    print(f"title={core.title!r} author={core.author!r} created={core.created}")
    print("=" * 70)
    i = 0
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text
            style = block.style.name if block.style is not None else ""
            if text.strip() or style.lower().startswith(("heading", "title", "list")):
                has_img = "graphicData" in block._p.xml
                marker = " [IMG]" if has_img else ""
                print(f"[P{i}][{style}]{marker} {text}")
            i += 1
        else:
            print(f"[TABLE rows={len(block.rows)} cols={len(block.columns)}]")
            for r in block.rows:
                cells = []
                for c in r.cells:
                    cells.append(c.text.replace("\n", " / ").strip())
                print("  | " + " | ".join(cells))
            print("[/TABLE]")


if __name__ == "__main__":
    main(sys.argv[1])
