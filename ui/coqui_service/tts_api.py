from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from TTS.api import TTS
import tempfile

app = FastAPI(title="FastFoodOrderingAgent Coqui-TTS")

# ✅ Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict this to ["http://localhost:3001"] later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Jenny model once at startup
tts = TTS(model_name="tts_models/en/jenny/jenny")

@app.post("/tts")
async def synthesize(data: dict = Body(...)):
    text = data.get("text", "")
    if not text:
        return {"error": "No text provided"}

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tts.tts_to_file(text=text, file_path=tmp.name)
    return FileResponse(tmp.name, media_type="audio/wav")
