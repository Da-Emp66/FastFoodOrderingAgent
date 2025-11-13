import os

from distutils.util import strtobool

from pydantic import BaseModel
from util.utils import FilterConfig, get_som_labeled_img, get_caption_model_processor, get_yolo_model, check_ocr_box
from PIL import Image
import io
import base64
from typing import Dict, Optional

class ParseRequestConfiguration(BaseModel):
    filter: FilterConfig = FilterConfig()

class Omniparser(object):
    def __init__(self, config: Dict):
        self.config = config
        self.som_model = get_yolo_model(model_path=config['som_model_path'])
        self.caption_model_processor = get_caption_model_processor(
            model_name=config['caption_model_name'],
            model_name_or_path=config['caption_model_path'],
            device=config['device'],
        )
        print('Omniparser initialized!!!')

    def parse(self, image_base64: str, additional_configuration: Optional[ParseRequestConfiguration] = None):
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        print('image size:', image.size)
        box_overlay_ratio = max(image.size) * float(os.getenv("ANNOTATION_SCALE_FACTOR", "2")) / 3200
        draw_bbox_config = {
            'text_scale': 0.8 * box_overlay_ratio,
            'text_thickness': max(int(2 * box_overlay_ratio), 1),
            'text_padding': max(int(3 * box_overlay_ratio), 1),
            'thickness': max(int(3 * box_overlay_ratio), 1),
        }
        (text, ocr_bbox), _ = check_ocr_box(
            image,
            display_img=False,
            output_bb_format='xyxy',
            easyocr_args={'text_threshold': 0.8},
            use_paddleocr=False,
        )
        dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
            image,
            self.som_model,
            BOX_TRESHOLD=self.config['BOX_TRESHOLD'],
            output_coord_in_ratio=True,
            ocr_bbox=ocr_bbox,
            draw_bbox_config=draw_bbox_config,
            caption_model_processor=self.caption_model_processor,
            ocr_text=text,
            use_local_semantics=bool(strtobool(os.getenv("USE_LOCAL_SEMANTICS", "true").lower())),
            iou_threshold=0.7,
            scale_img=False,
            batch_size=128,
            filter_config=None if additional_configuration is None else additional_configuration.filter,
        )
        return dino_labled_img, parsed_content_list
