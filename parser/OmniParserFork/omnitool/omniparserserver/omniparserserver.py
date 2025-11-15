'''
python -m omniparserserver --som_model_path ../../weights/icon_detect/model.pt --caption_model_name florence2 --caption_model_path ../../weights/icon_caption_florence --device cuda --BOX_TRESHOLD 0.05
'''

import sys
import os
import time
from pathlib import Path
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import argparse
import uvicorn
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)
from util.omniparser import Omniparser
import torch

def parse_arguments():
    parser = argparse.ArgumentParser(description='Omniparser API')
    parser.add_argument('--som_model_path', type=str, default=str(Path(__file__).parent.parent.parent / "weights" / "icon_detect" / "model.pt"), help='Path to the som model')
    parser.add_argument('--caption_model_name', type=str, default='florence2', help='Name of the caption model')
    parser.add_argument('--caption_model_path', type=str, default=str(Path(__file__).parent.parent.parent / "weights" / "icon_caption_florence"), help='Path to the caption model')
    parser.add_argument('--device', type=str, default=os.getenv("DEVICE", 'cuda' if torch.cuda.is_available() else 'cpu'), help='Device to run the model')
    parser.add_argument('--BOX_TRESHOLD', type=float, default=0.05, help='Threshold for box detection')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host for the API')
    parser.add_argument('--port', type=int, default=int(os.getenv("PARSER_PORT", 8055)), help='Port for the API')
    args = parser.parse_args()
    return args

args = parse_arguments()
config = vars(args)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # List of allowed origins
    allow_credentials=True, # Allow cookies and credentials
    allow_methods=["*"], # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allow all headers
)
omniparser = Omniparser(config)

class ParseRequest(BaseModel):
    base64_image: str

@app.post("/parse")
async def parse(parse_request: ParseRequest):
    print('start parsing...')
    start = time.time()
    dino_labled_img, parsed_content_list = omniparser.parse(parse_request.base64_image)
    latency = time.time() - start
    print('time:', latency)
    if dino_labled_img is not None:
        return {"som_image_base64": dino_labled_img, "parsed_content_list": parsed_content_list, 'latency': latency}
    else:
        return Response(content="An invalid image was passed. This was likely due to an all-black or all-white image.", status_code=400)

@app.get("/probe")
async def root():
    return {"message": "Omniparser API ready"}

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
    )
