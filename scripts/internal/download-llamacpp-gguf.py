import argparse
import inspect
import os
from pathlib import Path

def download_llamacpp_gguf(config):
    from llama_cpp import Llama # type: ignore
    from llama_cpp import llama_chat_format as lcf # type: ignore
    for name, obj in inspect.getmembers(lcf, inspect.isclass):
        if "ChatHandler" in name:
            globals()[name] = obj
    
    chat_handler = None

    if config.VISION_HANDLER_PATH is not None:
        if config.VISION_HANDLER_PATH.endswith(".gguf"):
            chat_handler = eval(config.VISION_HANDLER_TYPE)(config.VISION_HANDLER_PATH, **config.VISION_ARGS)
        else:
            chat_handler = eval(config.VISION_HANDLER_TYPE).from_pretrained(config.VISION_HANDLER_PATH, **config.VISION_ARGS)

    model_args = config.MODEL_ARGS
    if chat_handler is not None:
        model_args.update({"chat_handler": chat_handler})
    if config.MODEL_PATH.endswith(".gguf"):
        model = Llama(model_path=config.MODEL_PATH, **model_args)
    else:
        model = Llama.from_pretrained(repo_id=config.MODEL_PATH, **model_args)

def main(args):
    import yaml
    from box import Box # type: ignore
    config = Box(yaml.safe_load(open(args.configuration)))
    download_llamacpp_gguf(config)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--configuration", type=str, default=os.path.join(str(Path(__file__).parent.parent.parent), "configuration.yaml"))
    args = parser.parse_args()
    main(args)
