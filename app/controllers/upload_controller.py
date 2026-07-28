from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse


router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Process the uploaded file
    return JSONResponse(content={"message": "File uploaded successfully"})

@router.post("/view-upload")
async def view_upload(file: UploadFile = File(...)):
    return JSONResponse(content={"filename": file.filename, "content_type": file.content_type})
