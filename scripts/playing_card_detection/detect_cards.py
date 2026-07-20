# Base code provided by Dipankar Medhi article https://dipankarmedh1.medium.com/real-time-object-detection-with-yolo-and-webcam-enhancing-your-computer-vision-skills-861b97c78993
# Note press Q to stop the demo

# Important: The model and most of this script was taken from https://github.com/TeogopK/Playing-Cards-Object-Detection. 
# Thank you so much for your work.

import math
import sys
import onnxruntime as ort
from pokers import Card

DEFAULT_MODEL = "synthetic"
SHOW_CONFIDENCE = False
SHOW_SCREEN = False

configuration_dict = {
    "synthetic": {
        "model_path": "/Users/Jesse/Documents/csShi/goated-poker-ai-physical-implementation/scripts/playing_card_detection/yolov8m_synthetic.pt",
        "class_names": [
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
        ],
    },
}

def detect_cards(count: int)-> list[Card] | None:
    """
    Detects physical cards with a webcam and a YOLO ML model.
    
    Args:
        count: How many cards to capture
    Returns:
        List of parsed card dicts
    """

    print("Loading application...")

    config = configuration_dict["synthetic"]

    print("PATH NAME DEBUG: ", config["model_path"])
    # Load the model and class names
    model = YOLO(config["model_path"])

    # Start webcam
    cap = cv2.VideoCapture(0)
    cap.set(3, 640)
    cap.set(4, 480)

    window_title = "Playing Cards Detection - Model: 'synthetic'"

    prev_cards = []
    num_checks_passed = 0
    while True:
        success, img = cap.read()
        if not success:
            continue
        
        # Detect cards
        detected_cards = []
        results = model(img, stream=True, verbose=False)

        # Coordinates
        for r in results:
            boxes = r.boxes

            # TODO: Minor Bug: if full card in screen it will see both Ranks and 
            # append both boxes to 'detected_cards'. Current fix is to cover one rank.
            for box in boxes:
                # Bounding box
                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)  # Convert to int values

                # Put box in cam
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
                
                # Class name
                classNames = config["class_names"]
                cls = int(box.cls[0])
                class_name = classNames[cls]
                detected_cards.append(class_name)
                
                # Put details on image
                if SHOW_SCREEN:
                    img = show_details(img, x1, y1, box, class_name)

            
        if len(detected_cards) == count:
            # Sort so order is stable
            detected_cards.sort()

            if detected_cards == prev_cards:
                num_checks_passed += 1
            else:
                prev_cards = detected_cards.copy()
                num_checks_passed = 1

            print(f"Detected: {detected_cards}" f" ({num_checks_passed}/3)")

            if num_checks_passed >= 3:
                cap.release()
                cv2.destroyAllWindows()

                return [Card.from_string(card)for card in detected_cards]
        else:
            num_checks_passed = 0

        if SHOW_SCREEN:
            cv2.imshow(window_title, img)
            if cv2.waitKey(1) == ord("q"):
                break
            if cv2.waitKey(1) == ord("s"):
                SHOW_CONFIDENCE = not SHOW_CONFIDENCE
        
        
        
    cap.release()
    cv2.destroyAllWindows()
    
    return None

def show_details(img, x1, y1, box, class_name):
    """
    Puts the details on the given image.
    
    Returns: 
        New image with the details on it
    """
    # Confidence
    confidence = math.ceil((box.conf[0] * 100)) / 100
    print("Confidence --->", confidence)

    # Object details
    org = [x1, y1]
    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 1
    color = (255, 0, 0)
    thickness = 2
    display_text = class_name if not SHOW_CONFIDENCE else f"{class_name} {confidence}"
    cv2.putText(img, display_text, org, font, fontScale, color, thickness)
    
    return img
    