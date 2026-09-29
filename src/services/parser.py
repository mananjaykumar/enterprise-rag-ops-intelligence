import hashlib
from pathlib import Path
from typing import Any

from docx import Document as DocxDocument
from pydantic import BaseModel
from pypdf import PdfReader


class ParsedBlock(BaseModel):
    """Structured representation of a document section or table."""

    content: str
    content_hash: str
    page_number: int | None = None
    section_heading: str | None = None
    heading_hierarchy: list[str] = []
    chunk_type: str = "text"  # 'text', 'table', 'list'
    table_metadata: dict[str, Any] = {}
    char_start_idx: int | None = None
    char_end_idx: int | None = None


class DocumentParser:
    """Multi-format parser extracting structural Markdown AST from enterprise files."""

    @staticmethod
    def compute_sha256(content: str | bytes) -> str:
        """Computes SHA-256 hash for deduplication and chunk lineage."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def parse_file(self, file_path: str | Path, mime_type: str) -> list[ParsedBlock]:
        """Dispatches parsing based on file extension and MIME type."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext in [".txt", ".md"]:
            return self._parse_text_or_markdown(path)
        elif ext == ".pdf":
            return self._parse_pdf(path)
        elif ext in [".docx", ".doc"]:
            return self._parse_docx(path)
        else:
            # Fallback plain text read
            return self._parse_text_or_markdown(path)

    def _parse_text_or_markdown(self, path: Path) -> list[ParsedBlock]:
        """Parses plain text or Markdown preserving heading hierarchies."""
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        blocks: list[ParsedBlock] = []
        current_headings: list[str] = []
        current_buffer: list[str] = []
        char_offset = 0

        for line in lines:
            stripped = line.strip()

            # Detect Markdown Headings
            if stripped.startswith("#"):
                # Flush previous paragraph buffer
                if current_buffer:
                    content = "\n".join(current_buffer).strip()
                    if content:
                        blocks.append(
                            ParsedBlock(
                                content=content,
                                content_hash=self.compute_sha256(content),
                                section_heading=current_headings[-1] if current_headings else None,
                                heading_hierarchy=list(current_headings),
                                chunk_type="text",
                                char_start_idx=char_offset,
                                char_end_idx=char_offset + len(content),
                            )
                        )
                        char_offset += len(content) + 1
                    current_buffer = []

                # Calculate heading level: '# ' -> level 1, '## ' -> level 2
                level = len(stripped) - len(stripped.lstrip("#"))
                heading_title = stripped.lstrip("#").strip()

                # Adjust hierarchy depth
                current_headings = current_headings[: level - 1]
                current_headings.append(heading_title)
            elif stripped:
                current_buffer.append(stripped)

        # Flush trailing content
        if current_buffer:
            content = "\n".join(current_buffer).strip()
            if content:
                blocks.append(
                    ParsedBlock(
                        content=content,
                        content_hash=self.compute_sha256(content),
                        section_heading=current_headings[-1] if current_headings else None,
                        heading_hierarchy=list(current_headings),
                        chunk_type="text",
                        char_start_idx=char_offset,
                        char_end_idx=char_offset + len(content),
                    )
                )

        return blocks

    def _parse_pdf(self, path: Path) -> list[ParsedBlock]:
        """Extracts text page-by-page from PDF documents."""
        reader = PdfReader(str(path))
        blocks: list[ParsedBlock] = []
        char_offset = 0

        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]

            for para in paragraphs:
                blocks.append(
                    ParsedBlock(
                        content=para,
                        content_hash=self.compute_sha256(para),
                        page_number=page_idx + 1,
                        chunk_type="text",
                        char_start_idx=char_offset,
                        char_end_idx=char_offset + len(para),
                    )
                )
                char_offset += len(para) + 2

        return blocks

    def _parse_docx(self, path: Path) -> list[ParsedBlock]:
        """Parses DOCX documents extracting headings, paragraphs, and Markdown tables."""
        doc = DocxDocument(str(path))
        blocks: list[ParsedBlock] = []
        current_headings: list[str] = []
        char_offset = 0

        # Iterate through block elements (paragraphs and tables)
        for element in doc.element.body:
            tag = element.tag

            # 1. Paragraph element
            if tag.endswith("p"):
                text = element.text.strip()
                if not text:
                    continue

                # Check if paragraph has heading style
                style_name = ""
                p_elem = element
                # Check style attribute if present
                for child in p_elem:
                    if child.tag.endswith("pPr"):
                        for p_child in child:
                            if p_child.tag.endswith("pStyle"):
                                style_name = p_child.attrib.get(
                                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val",
                                    "",
                                )

                if "Heading" in style_name:
                    current_headings = [text]
                else:
                    blocks.append(
                        ParsedBlock(
                            content=text,
                            content_hash=self.compute_sha256(text),
                            section_heading=current_headings[-1] if current_headings else None,
                            heading_hierarchy=list(current_headings),
                            chunk_type="text",
                            char_start_idx=char_offset,
                            char_end_idx=char_offset + len(text),
                        )
                    )
                    char_offset += len(text) + 1

            # 2. Table element -> Convert to Markdown Table!
            elif tag.endswith("tbl"):
                # Locate the docx Table object matching this element
                for table in doc.tables:
                    if table._tbl == element:
                        md_table = self._convert_docx_table_to_markdown(table)
                        if md_table:
                            blocks.append(
                                ParsedBlock(
                                    content=md_table,
                                    content_hash=self.compute_sha256(md_table),
                                    section_heading=current_headings[-1]
                                    if current_headings
                                    else None,
                                    heading_hierarchy=list(current_headings),
                                    chunk_type="table",
                                    table_metadata={
                                        "rows": len(table.rows),
                                        "cols": len(table.columns),
                                    },
                                    char_start_idx=char_offset,
                                    char_end_idx=char_offset + len(md_table),
                                )
                            )
                            char_offset += len(md_table) + 1
                        break

        return blocks

    @staticmethod
    def _convert_docx_table_to_markdown(table: Any) -> str:
        """Converts a python-docx Table object into a structured Markdown table."""
        if not table.rows:
            return ""

        rows_data: list[list[str]] = []
        for row in table.rows:
            row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            rows_data.append(row_cells)

        if not rows_data:
            return ""

        # Format as Markdown
        header = "| " + " | ".join(rows_data[0]) + " |"
        separator = "| " + " | ".join(["---"] * len(rows_data[0])) + " |"
        body = ["| " + " | ".join(r) + " |" for r in rows_data[1:]]

        return "\n".join([header, separator] + body)
