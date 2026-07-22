from picamera2 import Picamera2, Preview
import cv2
import time
import numpy as np

def capture_photo(camera_num: int, file_name: str=None):
    """
    Captures an image with the camera of the chosen number. 
    Writes the image to a file if name is specified. Remember the file extension (.jpg)
    
    Args:
        camera_num: Number of the camera to take the photo, 0 indexing
        file_name: Name of the image file to save
    Returns:
        Image of photo in np array
    """
    picam2 = Picamera2(camera_num=camera_num)
    camera_config = picam2.create_still_configuration()
    picam2.configure(camera_config)

    picam2.start()
    time.sleep(2)
    frame = picam2.capture_array()
    bgr = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUYV) # opencv used to save and color correct image
    cv2.imwrite(filename=file_name, img=bgr) 
    
    return np.array(bgr)
    
capture_photo(1, "two.jpg")