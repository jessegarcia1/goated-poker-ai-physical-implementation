from gpiozero import LED, Button
from time import sleep

# LED is always an output device
ENABLE = LED(17)
DIRECTION = LED(27)
STEP = LED(22)

LIMIT_SWITCH = Button(26, pull_up=True, bounce_time=0.05)

ENABLE.off()

STEP_DELAY = 0.00009
STEPS_PER_CHIP = 680

def LEFT():
    DIRECTION.on()
def RIGHT():
    DIRECTION.off()

def move(steps, step_delay=STEP_DELAY):    
    for _ in range(steps):
        STEP.on()
        sleep(step_delay)
        STEP.off()
        sleep(step_delay)

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
            print(_)
            dispense_one_chip(direction)
            direction = not direction

    
    except KeyboardInterrupt:
        pass

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
    
def homing_sequence():
    HOMING_STEP_DELAY = 0.001
    print("Homing: moving LEFT to find first limit...")
    LEFT()

    while not LIMIT_SWITCH.is_pressed:
        move(1, step_delay=HOMING_STEP_DELAY)

    print("Left limit found.")

    RIGHT()
    
    total_steps = 0
    # move until off the limit switch
    while LIMIT_SWITCH.is_pressed:
        move(1, step_delay=HOMING_STEP_DELAY)
        total_steps += 1

    print("Moving RIGHT to find second limit...")
    
    while not LIMIT_SWITCH.is_pressed:
        move(1, step_delay=HOMING_STEP_DELAY)
        total_steps += 1

    print(f"Right limit found. Total travel: {total_steps} steps")

    # Move to the middle
    half_steps = total_steps // 2
    print(f"Moving to middle ({half_steps} steps left)...")
    LEFT()
    move(half_steps)

    STEP.off()
    ENABLE.on()            
    print("Homing complete.")

    return total_steps
        
try:
    #little_steps("R", 100)
    #dispense(15)
    homing_sequence()
    
    # while True:
    #     if LIMIT_SWITCH.is_pressed:
    #         print("closed")
    #     else:
    #         print("open")
    #     sleep(0.1)

except KeyboardInterrupt:
    # So gpiozero can perfo
    # rm automatic cleanup
    print("Ending program")
    