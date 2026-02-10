# AI Text Reader

An OCR + TTS application that captures images, extracts text using OCR, and converts it to speech.

## Features

- 📷 Capture images from camera or upload files
- 🔍 Extract text from images using Tesseract OCR
- 🔊 Convert text to speech using pyttsx3
- 🎨 Modern AI-themed UI with gradient colors
- ⚡ FastAPI backend with React Vite frontend

## Prerequisites

### Backend
- Python 3.8+
- Tesseract OCR installed on your system

### Frontend
- Node.js 18+
- npm or yarn

## Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create and activate virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
source venv/bin/activate  # On macOS/Linux
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install Tesseract OCR:
   - **Windows**: Download from [GitHub Releases](https://github.com/UB-Mannheim/tesseract/wiki)
   - **macOS**: `brew install tesseract`
   - **Linux**: `sudo apt-get install tesseract-ocr`

5. Run the backend server:
```bash
python main.py
```

The backend will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Usage

1. Open the application in your browser at `http://localhost:5173`
2. Click "Start Camera" to access your camera or upload an image
3. Click "Capture" to take a photo or select an image file
4. Click "Process Image" to extract text and generate audio
5. Listen to the extracted text using the audio player

## API Endpoints

- `POST /ocr` - Upload image and extract text
- `POST /tts` - Convert text to audio file
- `GET /audio/{filename}` - Retrieve generated audio file

## Tech Stack

- **Backend**: FastAPI, Tesseract OCR, pyttsx3
- **Frontend**: React, Vite, Tailwind CSS