"""Store browser-selected resumes without trusting client filesystem paths."""
import io
import uuid
import zipfile

from fastapi import HTTPException, Request

from core.config import get_data_dir

MAX_RESUME_BYTES = 10 * 1024 * 1024


async def upload_resume(request: Request):
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_RESUME_BYTES:
            raise HTTPException(413, "Resume must be 10 MB or smaller.")
        content.extend(chunk)
    if content.startswith(b"%PDF-"):
        suffix = ".pdf"
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                if not {"[Content_Types].xml", "word/document.xml"} <= names:
                    raise zipfile.BadZipFile
                if sum(part.file_size for part in archive.infolist()) > 60 * 1024 * 1024:
                    raise HTTPException(413, "The Word document is too large when expanded.")
            suffix = ".docx"
        except zipfile.BadZipFile:
            raise HTTPException(400, "Please select a PDF or Word (.docx) resume.") from None

    directory = get_data_dir() / "resumes"
    directory.mkdir(exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}{suffix}"
    try:
        with path.open("xb") as output:
            output.write(content)
    except OSError:
        path.unlink(missing_ok=True)
        raise HTTPException(500, "Could not save the resume. Please try again.") from None
    return {"resume_path": str(path)}
