from ultralytics import YOLO
from pokers import Card
import cv2
import numpy as np

MODEL_PATH = "scripts/playing_card_detection/yolov8m_synthetic.pt"
CLASS_NAMES = [
    "CT", "DT", "HT", "ST",
    "C2", "D2", "H2", "S2",
    "C3", "D3", "H3", "S3",
    "C4", "D4", "H4", "S4",
    "C5", "D5", "H5", "S5",
    "C6", "D6", "H6", "S6",
    "C7", "D7", "H7", "S7",
    "C8", "D8", "H8", "S8",
    "C9", "D9", "H9", "S9",
    "CA", "DA", "HA", "SA",
    "CJ", "DJ", "HJ", "SJ",
    "CK", "DK", "HK", "SK",
    "CQ", "DQ", "HQ", "SQ",
]

def detect_cards(image, count) -> list[Card] | None:
    """
    Detects playing cards in a single image.

    Args:
        image: numpy array 
        count: number of cards to be detected in the image
    Returns:
        List of detected Card objects, confirmed by a second consistent
        detection pass, or None if this couldn't be achieved after 3 attempts.
    """
    model = YOLO(MODEL_PATH)
    results = model(image, conf=0.05, verbose=False)[0]
    detected_cards_str = []
    
    for box in results.boxes:
        cls = int(box.cls[0])
        detected_cards_str.append(CLASS_NAMES[cls])
        
    print("LENGTH CARD LIST: ", len(detected_cards_str))
        
    if len(detected_cards_str) == count:
        return detected_cards_str

    print("card_list FAILED to match count. Card List: ", detected_cards_str)
    return None

if __name__ == "__main__":
    card_list = detect_cards(np.array(cv2.imread("/Users/Jesse/Documents/csShi/goated-poker-ai-physical-implementation/test12345.jpg")), 2)
    
    print(card_list[0].suit)
    print(card_list[0].rank)
    print(card_list[1].suit)
    print(card_list[1].rank)
