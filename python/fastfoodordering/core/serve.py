import argparse
from fastapi import FastAPI
import uvicorn

app = FastAPI()



def main():
    uvicorn.run(
        app=app,
        host=args.host,
        port=args.port,
    )
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-h", "--host", type=str, default="0.0.0.0")
    parser.add_argument("-h", "--port", type=str, default=8080)
    args = parser.parse_args()
    main(args)
