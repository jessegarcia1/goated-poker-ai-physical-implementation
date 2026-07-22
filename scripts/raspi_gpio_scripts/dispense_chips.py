from gpiozero import LED
from time import sleep

# LED is always an output device
ENABLE = LED(17)
DIRECTION = LED(27)
STEP = LED(22)

ENABLE.off()

STEP_DELAY = 0.002
STEPS_PER_CHIP = 85

def LEFT():
    DIRECTION.on()
def RIGHT():
    DIRECTION.off()

def move(steps):
    for _ in range(steps):
        STEP.on()
        sleep(STEP_DELAY)
        STEP.off()
        sleep(STEP_DELAY)

def dispense_one_chip(direction: bool):
    func1 = LEFT
    func2 = RIGHT
    if direction == False: # True moves LEFT, False moves RIGHT
        func1 = RIGHT
        func2 = LEFT
        
    func1()
    move(STEPS_PER_CHIP)      # dispense one chip
    func2()
    sleep(.05)
    move(STEPS_PER_CHIP)      # return to reset position
    sleep(.05)
        
def dispense(num_dispensed: int):
    try:
        
        direction = True
        
        for _ in range(num_dispensed):
            dispense_one_chip(direction)
            direction = not direction

    
    except KeyboardInterrupt:
        ENABLE.on()
        STEP.off()

    finally:
        ENABLE.on()
        STEP.off()

def little_steps(direction: str, count: int):
    if direction == "L":
        sleep(.05)
        LEFT()
        sleep(.05)
    
        for _ in range(count):
            STEP.on()
            sleep(.002)
            STEP.off()
            sleep(.002)
      
    elif direction == "R":
        for _ in range(count):
            STEP.on()
            sleep(.002)
            STEP.off()
            sleep(.002)
        
    ENABLE.on()  
    STEP.off()
        
#little_steps("R", 100)
dispense(10)