#raspi.py
from picamera2 import Picamera2
import cv2
import time
import numpy as np
import serial
from dataclasses import dataclass

"""
    How to run: run with sudo
"""
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

@dataclass
class PhysicalGameState:
    num_players: int
    num_agents: int
    initial_stake: float
    button_pos: int
    small_blind: float
    big_blind: float

def get_serial_info(port='/dev/ttyACM0', baudrate=9600):
    ser = serial.Serial(port, baudrate, timeout=None)

    num_players = int(ser.readline().decode().strip())
    num_agents = int(ser.readline().decode().strip())
    initial_stake = float(ser.readline().decode().strip())
    button_pos = int(ser.readline().decode().strip())
    small_blind = float(ser.readline().decode().strip())
    big_blind = float(ser.readline().decode().strip())

    ser.close()

    return PhysicalGameState(
        num_players=num_players,
        num_agents=num_agents,
        initial_stake=initial_stake,
        button_pos=button_pos,
        small_blind=small_blind,
        big_blind=big_blind,
    )


if __name__ == '__main__':
    capture_photo(0, "test12.jpg")
    