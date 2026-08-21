import asyncio
import base64
import os
import shutil
import pytest
from tools.document import binary_document_to_markdown, document_path_to_markdown


class TestBinaryDocumentToMarkdown:
    # Define fixture paths
    FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
    DOCX_FIXTURE = os.path.join(FIXTURES_DIR, "mcp_docs.docx")
    PDF_FIXTURE = os.path.join(FIXTURES_DIR, "mcp_docs.pdf")

    def test_fixture_files_exist(self):
        """Verify test fixtures exist."""
        assert os.path.exists(self.DOCX_FIXTURE), (
            f"DOCX fixture not found at {self.DOCX_FIXTURE}"
        )
        assert os.path.exists(self.PDF_FIXTURE), (
            f"PDF fixture not found at {self.PDF_FIXTURE}"
        )

    def test_binary_document_to_markdown_with_docx(self):
        """Test converting a DOCX document to markdown."""
        # Read binary content from the fixture
        with open(self.DOCX_FIXTURE, "rb") as f:
            docx_data = f.read()

        # Call function
        result = binary_document_to_markdown(docx_data, "docx")

        # Basic assertions to check the conversion was successful
        assert isinstance(result, str)
        assert len(result) > 0
        # Check for typical markdown formatting - this will depend on your actual test file
        assert "#" in result or "-" in result or "*" in result

    def test_binary_document_to_markdown_with_pdf(self):
        """Test converting a PDF document to markdown."""
        # Read binary content from the fixture
        with open(self.PDF_FIXTURE, "rb") as f:
            pdf_data = f.read()

        # Call function
        result = binary_document_to_markdown(pdf_data, "pdf")

        # Basic assertions to check the conversion was successful
        assert isinstance(result, str)
        assert len(result) > 0
        # Check for typical markdown formatting - this will depend on your actual test file
        assert "#" in result or "-" in result or "*" in result


class TestBinaryDocumentToMarkdownBase64:
    """Binary data can only cross the protocol boundary base64-encoded."""

    FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
    DOCX_FIXTURE = os.path.join(FIXTURES_DIR, "mcp_docs.docx")
    PDF_FIXTURE = os.path.join(FIXTURES_DIR, "mcp_docs.pdf")

    def test_base64_string_matches_raw_bytes(self):
        """A base64 string and the bytes it encodes must convert identically."""
        with open(self.PDF_FIXTURE, "rb") as f:
            pdf_data = f.read()
        encoded = base64.b64encode(pdf_data).decode()

        assert binary_document_to_markdown(encoded, "pdf") == (
            binary_document_to_markdown(pdf_data, "pdf")
        )

    def test_base64_string_for_docx(self):
        """DOCX structure survives the base64 round trip."""
        with open(self.DOCX_FIXTURE, "rb") as f:
            docx_data = f.read()

        result = binary_document_to_markdown(
            base64.b64encode(docx_data).decode(), "docx"
        )

        assert "# Overview" in result

    def test_base64_with_whitespace(self):
        """Encoders wrap long base64 at fixed widths; newlines must be ignored."""
        with open(self.PDF_FIXTURE, "rb") as f:
            pdf_data = f.read()
        encoded = base64.b64encode(pdf_data).decode()
        wrapped = "\n".join(
            encoded[i : i + 76] for i in range(0, len(encoded), 76)
        )

        assert "Model Context Protocol" in binary_document_to_markdown(wrapped, "pdf")

    def test_invalid_base64_raises(self):
        """The original bug: undecodable text must raise, not convert.

        Previously this returned the input string back as "markdown" because
        pydantic UTF-8-encoded it and MarkItDown sniffed it as plain text.
        """
        with pytest.raises(ValueError, match="not valid base64"):
            binary_document_to_markdown("this is not base64!!", "pdf")

    def test_empty_string_raises(self):
        """An empty payload decodes to no bytes and must raise."""
        with pytest.raises(ValueError, match="empty"):
            binary_document_to_markdown("", "pdf")

    def test_base64_through_mcp_layer(self):
        """End-to-end through call_tool, the path a model actually takes.

        This is the test that catches the encoding bug; the direct-call tests
        pass real bytes and never exercise pydantic's coercion.
        """
        import main

        with open(self.PDF_FIXTURE, "rb") as f:
            pdf_data = f.read()

        result = asyncio.run(
            main.mcp.call_tool(
                "binary_document_to_markdown",
                {
                    "binary_data": base64.b64encode(pdf_data).decode(),
                    "file_type": "pdf",
                },
            )
        )

        text = str(result)
        assert "Model Context Protocol" in text
        assert "JVBERi" not in text, "base64 leaked through undecoded"


class TestDocumentPathToMarkdown:
    # Define fixture paths
    FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
    DOCX_FIXTURE = os.path.join(FIXTURES_DIR, "mcp_docs.docx")
    PDF_FIXTURE = os.path.join(FIXTURES_DIR, "mcp_docs.pdf")

    def test_document_path_to_markdown_with_pdf(self):
        """Test converting a PDF at a given path to markdown."""
        result = document_path_to_markdown(self.PDF_FIXTURE)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_document_path_to_markdown_with_docx(self):
        """Test converting a DOCX at a given path to markdown."""
        result = document_path_to_markdown(self.DOCX_FIXTURE)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_pdf_result_matches_binary_conversion(self):
        """Reading a path must produce exactly what converting its bytes produces.

        This pins the tool as a thin wrapper over binary_document_to_markdown and
        catches a mis-inferred extension, which yields different text rather than
        an error.
        """
        with open(self.PDF_FIXTURE, "rb") as f:
            pdf_data = f.read()

        assert document_path_to_markdown(self.PDF_FIXTURE) == (
            binary_document_to_markdown(pdf_data, "pdf")
        )

    def test_docx_result_matches_binary_conversion(self):
        """Same equivalence check for DOCX."""
        with open(self.DOCX_FIXTURE, "rb") as f:
            docx_data = f.read()

        assert document_path_to_markdown(self.DOCX_FIXTURE) == (
            binary_document_to_markdown(docx_data, "docx")
        )

    def test_pdf_contains_fixture_text(self):
        """Assert on real fixture content, not just "some markdown character".

        The PDF converter emits plain prose with bullet characters and no ATX
        headings, so a heading check would be wrong here.
        """
        result = document_path_to_markdown(self.PDF_FIXTURE)

        assert "Model Context Protocol" in result
        assert "Key Features of this Python SDK" in result

    def test_docx_preserves_markdown_structure(self):
        """DOCX conversion carries real structure across; assert on it."""
        result = document_path_to_markdown(self.DOCX_FIXTURE)

        assert "# Overview" in result
        assert "## Key Features of this Python SDK" in result
        assert "* Build MCP clients that can connect to any MCP server" in result

    def test_relative_path(self, monkeypatch):
        """A path relative to the current working directory resolves."""
        monkeypatch.chdir(self.FIXTURES_DIR)

        result = document_path_to_markdown("mcp_docs.pdf")

        assert "Model Context Protocol" in result

    def test_uppercase_extension(self, tmp_path):
        """.PDF is the same format as .pdf.

        Fails with a ValueError if the extension is validated without
        lowercasing first.
        """
        target = tmp_path / "MCP_DOCS.PDF"
        shutil.copy(self.PDF_FIXTURE, target)

        assert "Model Context Protocol" in document_path_to_markdown(str(target))

    def test_multi_dot_filename(self, tmp_path):
        """Only the final suffix is the extension.

        Splitting on the first dot would infer "v2", fail validation, and raise.
        """
        target = tmp_path / "report.v2.final.pdf"
        shutil.copy(self.PDF_FIXTURE, target)

        assert "Model Context Protocol" in document_path_to_markdown(str(target))

    def test_extension_disagreeing_with_content(self, tmp_path):
        """Documents existing behavior: MarkItDown sniffs content, not extension.

        A real PDF named .docx converts as a PDF instead of raising, so the
        extension only gates which files the tool accepts.
        """
        with open(self.PDF_FIXTURE, "rb") as f:
            pdf_data = f.read()
        target = tmp_path / "actually_a_pdf.docx"
        target.write_bytes(pdf_data)

        assert document_path_to_markdown(str(target)) == (
            binary_document_to_markdown(pdf_data, "pdf")
        )

    def test_missing_file_raises(self, tmp_path):
        """A path that does not exist raises, naming the path."""
        missing = tmp_path / "does_not_exist.pdf"

        with pytest.raises(FileNotFoundError, match="does_not_exist.pdf"):
            document_path_to_markdown(str(missing))

    def test_directory_path_raises(self, tmp_path):
        """A directory is not a document."""
        with pytest.raises(IsADirectoryError):
            document_path_to_markdown(str(tmp_path))

    def test_unsupported_extension_raises(self, tmp_path):
        """The tool accepts PDF and DOCX only.

        Without this gate the call would fall through to MarkItDown, which
        happily converts plain text and many other formats.
        """
        target = tmp_path / "notes.txt"
        target.write_text("hello world")

        with pytest.raises(ValueError, match="txt"):
            document_path_to_markdown(str(target))

    def test_missing_extension_raises(self, tmp_path):
        """A file with no extension gives nothing to infer from."""
        target = tmp_path / "mcp_docs"
        shutil.copy(self.PDF_FIXTURE, target)

        with pytest.raises(ValueError):
            document_path_to_markdown(str(target))

    def test_empty_file_raises(self, tmp_path):
        """An empty file must raise rather than return "".

        A silent empty string is indistinguishable from a document that
        genuinely has no text.
        """
        target = tmp_path / "empty.pdf"
        target.write_bytes(b"")

        with pytest.raises(ValueError):
            document_path_to_markdown(str(target))

    def test_truncated_pdf_does_not_raise(self, tmp_path):
        """Documents a known limitation rather than asserting a fix.

        A truncated PDF is not detected: MarkItDown returns the raw file bytes
        decoded as text. Detecting this would need a content heuristic, so the
        tool passes it through and this test records that.
        """
        with open(self.PDF_FIXTURE, "rb") as f:
            truncated = f.read(200)
        target = tmp_path / "truncated.pdf"
        target.write_bytes(truncated)

        result = document_path_to_markdown(str(target))

        assert "%PDF" in result


class TestToolRegistration:
    """A function in tools/ is dead code until main.py registers it."""

    def registered_tool_names(self):
        import main

        return [tool.name for tool in asyncio.run(main.mcp.list_tools())]

    def test_document_path_to_markdown_is_registered(self):
        assert "document_path_to_markdown" in self.registered_tool_names()

    def test_binary_document_to_markdown_is_registered(self):
        assert "binary_document_to_markdown" in self.registered_tool_names()
