# Imports
from pathlib import Path
import time
from typing import List, Tuple, Union
import cv2
import requests
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

DEVICE = "cuda"

class GroundingDINO:
    def __init__(self, path: str = "IDEA-Research/grounding-dino-tiny", device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        print(f"Using {device}")
        self.grounding_dino_processor = AutoProcessor.from_pretrained(path)
        self.grounding_dino_model = AutoModelForZeroShotObjectDetection.from_pretrained(path).to(device)

    def grounding_dino_inference(
        self,
        image: cv2.typing.MatLike,
        text: Union[str, List[str]],
    ):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(image)
        inputs = self.grounding_dino_processor(
            images=image,
            text=text,
            return_tensors="pt",
        ).to(self.grounding_dino_model.device)
        with torch.no_grad(): outputs = self.grounding_dino_model(**inputs)
        results = self.grounding_dino_processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=0.4,
            text_threshold=0.3,
            target_sizes=[image.size[::-1]],
        )
        # Retrieve the first image result
        result = results[0]
        for box, score, labels in zip(result["boxes"], result["scores"], result["labels"]):
            box = [round(x, 2) for x in box.tolist()]
            print(f"Detected {labels} with confidence {round(score.item(), 3)} at location {box}")
        return list(zip(result["boxes"].tolist(), result["labels"], result["scores"].tolist()))

    def draw_bounding_boxes_cv2(
        self,
        image: cv2.typing.MatLike,
        predictions: List[ # Per Prediction
            Tuple[
                List[float], # Box
                str, # Label
                float, # Score
            ]
        ],
        thickness: float = 2,
    ):
        # Draw boxes
        for box, label, score in predictions:
            image = cv2.rectangle(image, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 255, 0), thickness)
            image = cv2.putText(image, f"{label}: {score:.2f}", (int(box[0]), int(box[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        return image

if __name__ == "__main__":
    gdino = GroundingDINO()
    # Parsing
    image = str(Path(__file__).parent.parent.parent / "fastfoodordering" / "examples" / "assets" / "test_BK_image_for_coords.png")
    # image = str(Path(__file__).parent / "examples" / "assets" / "test_BK_image_for_location.jpg")
    image = cv2.imread(image)
    start = time.time()
    predictions = gdino.grounding_dino_inference(image, text=["web page button", "web page text"])
    end = time.time()
    print(f"Determined {len(predictions)} bboxes in {end - start} seconds")
    cv2.imshow("Grounding DINO Web Page", gdino.draw_bounding_boxes_cv2(image, predictions))
    cv2.waitKey(1)
    time.sleep(5)
