from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from PIL import Image
import numpy as np
import pyttsx3
import io
import os
import uuid
from typing import Optional
import easyocr
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

app = FastAPI(title="OCR TTS API")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
AUDIO_DIR = "audio"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

_OCR_READER = None

def get_ocr_reader():
    global _OCR_READER
    if _OCR_READER is None:
        # Default to CPU for broader compatibility.
        _OCR_READER = easyocr.Reader(['ar'], gpu=True)
    return _OCR_READER

@app.post("/ocr")
async def extract_text(file: UploadFile = File(...)):
    try:            
        image = Image.open(file.file).convert("RGB")
        image_array = np.array(image)
        reader = get_ocr_reader()
        result = reader.readtext(image_array, detail=0)
        text = ' '.join(result)
        return {
            "success": True,
            "text": text,
            "language": "eng"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/tts")
async def text_to_speech(text: str = Form(...), voice_id: Optional[int] = Form(0), rate: Optional[int] = Form(150), volume: Optional[float] = Form(1.0)):
    try:
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        
        engine = pyttsx3.init()
        engine.setProperty('rate', rate)
        engine.setProperty('volume', volume)
        
        voices_list = engine.getProperty('voices')
        if voices_list is not None and len(voices_list) > 0 and voice_id < len(voices_list):
            engine.setProperty('voice', voices_list[voice_id].id)
        
        engine.save_to_file(text, filepath)
        engine.runAndWait()
        
        return {
            "success": True,
            "audio_url": f"/audio/{filename}",
            "filename": filename
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/voices")
async def get_voices():
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        return {
            "success": True,
            "voices": [{"id": i, "name": voice.name, "languages": voice.languages if hasattr(voice, 'languages') else []} for i, voice in enumerate(voices)] if voices else []
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    try:
        filepath = os.path.join(AUDIO_DIR, filename)
        return FileResponse(filepath, media_type="audio/mpeg")
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def root():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "OCR TTS API is running"}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if FRONTEND_DIST.exists():
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return {"detail": "Not Found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
