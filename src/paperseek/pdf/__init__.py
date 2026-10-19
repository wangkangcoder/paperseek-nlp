"""PDF 处理层：文本抽取、页码保留、片段切分与本地论文库构建（FR-12 / FR-13）。

对外主要接口（契约冻结）::

    from paperseek.pdf.library import build_library_documents
    documents = build_library_documents(pdf_dir)   # list[Document]，每篇 PDF 切成若干 Chunk

    from paperseek.pdf.parser import extract_pdf_pages
    pages = extract_pdf_pages(pdf_path)            # list[Page]，Page(page_number, text)

内部实现（parser/chunker/library）由界面与 PDF 组负责。
"""
