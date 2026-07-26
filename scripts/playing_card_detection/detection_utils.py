from ultralytics import YOLO
from pokers import Card

def detect_cards(image) -> list[Card]:
    """
    Detects playing cards in a single image.

    Args:
        image: numpy array 
    Returns:
        List of detected Card objects
    """
    
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

    model = YOLO(MODEL_PATH)
    results = model(image, verbose=False)[0]

    detected_cards = []
    for box in results.boxes:
        cls = int(box.cls[0])
        detected_cards.append(CLASS_NAMES[cls])

    return [Card.from_string(card) for card in detected_cards]