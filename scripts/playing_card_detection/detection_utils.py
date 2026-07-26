from ultralytics import YOLO
from pokers import Card
from collections import Counter

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

    def run_detection():
        results = model(image, verbose=False)[0]

        detected_cards = []
        for box in results.boxes:
            cls = int(box.cls[0])
            detected_cards.append(CLASS_NAMES[cls])

        return [Card.from_string(card) for card in detected_cards]

    max_tries = 3
    card_list = []
    for attempt in range(max_tries):
        card_list = run_detection()

        if len(card_list) != count:
            continue

        confirm_list = run_detection()

        # Detected cards must equal each other (order does not matter w/ Counter)
        if len(confirm_list) == count and Counter(card_list) == Counter(confirm_list):
            return card_list

    print("card_list FAILED to match count: ", card_list)
    return None