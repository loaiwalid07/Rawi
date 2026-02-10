from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pytesseract
from PIL import Image
import pyttsx3
import io
import os
import uuid
from typing import Optional

app = FastAPI(title="OCR TTS API")

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

@app.post("/ocr")
async def extract_text(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        text = pytesseract.image_to_string(image)
        
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
            "audio_url": f"http://localhost:8000/audio/{filename}",
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
    return {"message": "OCR TTS API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)