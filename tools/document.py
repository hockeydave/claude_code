import base64
import binascii
from markitdown import MarkItDown, StreamInfo
from io import BytesIO
from pathlib import Path
from pydantic import Field

SUPPORTED_EXTENSIONS = ("pdf", "docx")


def binary_document_to_markdown(
    binary_data: str | bytes = Field(
        description=(
            "The document's contents. Pass a base64-encoded string, which is "
            "the only way to send binary data over the protocol. Raw bytes are "
            "also accepted when calling from Python directly."
        )
    ),
    file_type: str = Field(
        description=(
            "The document's format, given as its file extension with or "
            "without a leading dot, for example 'pdf', '.pdf', or 'docx'."
        )
    ),
) -> str:
    """Convert an in-memory document to markdown-formatted text.

    Takes a document that is already in memory and returns its text as
    markdown, using file_type as a hint for the source format. Structure is
    preserved as far as the source format allows: DOCX yields headings, bullet
    lists, and tables, while PDF yields largely flat prose.

    A string argument is decoded as base64 before conversion, since binary data
    cannot be sent over the protocol any other way. Whitespace and newlines
    within the encoded string are ignored. Raw bytes are passed through
    unchanged, so calling from Python with real bytes also works.

    The format is inferred from the decoded bytes themselves, so file_type is
    only a hint. Contents that disagree with file_type are converted according
    to what they actually are rather than rejected.

    When to use:
    - When a document is already in memory rather than on disk
    - When the document has no path, such as a download or an attachment

    When not to use:
    - When the document exists as a file on disk; use
      document_path_to_markdown, which reads and validates the path for you

    Raises:
        ValueError: binary_data is a string that is not valid base64, or the
            document is empty.

    Examples:
    >>> binary_document_to_markdown(base64.b64encode(docx_bytes), "docx")
    '# Overview\\n\\nThe Model Context Protocol allows applications to ...'
    >>> binary_document_to_markdown("not valid base64!", "pdf")
    Traceback (most recent call last):
    ValueError: binary_data is not valid base64: Invalid base64-encoded string
    """
    if isinstance(binary_data, str):
        try:
            binary_data = base64.b64decode(
                "".join(binary_data.split()), validate=True
            )
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"binary_data is not valid base64: {exc}") from exc

    if not binary_data:
        raise ValueError("binary_data is empty; there is no document to convert")

    md = MarkItDown()
    file_obj = BytesIO(binary_data)
    stream_info = StreamInfo(extension=file_type)
    result = md.convert(file_obj, stream_info=stream_info)
    return result.text_content


def document_path_to_markdown(
    file_path: str = Field(
        description=(
            "Path to the PDF or DOCX file to convert. May be absolute or "
            "relative to the current working directory. The extension must be "
            ".pdf or .docx (case-insensitive)."
        )
    ),
) -> str:
    """Read a PDF or DOCX file from disk and convert its contents to markdown.

    Resolves the path, infers the document format from the file extension, and
    returns the document's text as markdown. Structure is preserved as far as
    the source format allows: DOCX conversion yields headings, bullet lists, and
    tables, while PDF conversion yields largely flat prose because a PDF records
    visual layout rather than semantic structure.

    When to use:
    - When you have a path to a PDF or DOCX file and need its text
    - When you need document contents in a form you can quote or summarize

    When not to use:
    - When the document is already in memory as bytes; use
      binary_document_to_markdown instead
    - For any other format. Only PDF and DOCX are accepted, and a file with a
      different extension is rejected rather than attempted.

    Raises:
        FileNotFoundError: The path does not exist.
        IsADirectoryError: The path is a directory rather than a file.
        ValueError: The file has no extension, has an unsupported extension, or
            is empty.

    Examples:
    >>> document_path_to_markdown("docs/mcp_docs.docx")
    '# Overview\\n\\nThe Model Context Protocol allows applications to ...'
    >>> document_path_to_markdown("docs/notes.txt")
    Traceback (most recent call last):
    ValueError: Unsupported file extension '.txt'. Expected .pdf or .docx.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"No such file: {file_path}")
    if path.is_dir():
        raise IsADirectoryError(f"Expected a file but found a directory: {file_path}")

    extension = path.suffix.lower().lstrip(".")
    if not extension:
        raise ValueError(
            f"Cannot determine the document format because the path has no file "
            f"extension: {file_path}. Expected .pdf or .docx."
        )
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '.{extension}'. Expected .pdf or .docx."
        )

    binary_data = path.read_bytes()
    if not binary_data:
        raise ValueError(f"File is empty: {file_path}")

    return binary_document_to_markdown(binary_data, extension)
