from gpiozero import LED, Button
from time import sleep

STEP_DELAY = 0.00009
STEPS_PER_CHIP = 680

# pin numbers per agent: (enable, direction, pulse)
AGENT_PINS = {
    1: (2, 3, 4),
    2: (10, 9, 11),
}
LIMIT_SWITCH_PIN = 15

# pot motor always uses these pins
POT_PINS = (17, 27, 22)


def LEFT(direction):
    direction.on()


def RIGHT(direction):
    direction.off()


def move(step, steps, step_delay=STEP_DELAY):
    for _ in range(steps):
        step.on()
        sleep(step_delay)
        step.off()
        sleep(step_delay)


def dispense_one_chip(direction: bool, direction_led, step):
    func1 = LEFT
    func2 = RIGHT
    if direction == False:  # True moves LEFT, False moves RIGHT
        func1 = RIGHT
        func2 = LEFT

    func1(direction_led)
    move(step, STEPS_PER_CHIP)      # dispense one chip
    func2(direction_led)
    sleep(STEP_DELAY)
    move(step, STEPS_PER_CHIP)      # return to reset position
    sleep(STEP_DELAY)


def dispense(num_dispensed: int, agent_num: int):
    if agent_num not in AGENT_PINS:
        raise ValueError("agent_num must be 1 or 2")

    enable_pin, direction_pin, step_pin = AGENT_PINS[agent_num]
    enable = LED(enable_pin)
    direction_led = LED(direction_pin)
    step = LED(step_pin)

    try:
        enable.off()
        direction = True

        for _ in range(num_dispensed):
            print(_)
            dispense_one_chip(direction, enable, direction_led, step)
            direction = not direction

    except KeyboardInterrupt:
        pass

    finally:
        enable.on()
        step.off()
        enable.close()
        direction_led.close()
        step.close()


def little_steps(direction: str, step, direction_led, count: int):
    if direction == "L":
        sleep(.05)
        LEFT(direction_led)
        sleep(.05)

        for _ in range(count):
            step.on()
            sleep(STEP_DELAY)
            step.off()
            sleep(STEP_DELAY)

    elif direction == "R":
        for _ in range(count):
            step.on()
            sleep(STEP_DELAY)
            step.off()
            sleep(STEP_DELAY)


def homing_sequence(agent_num:int):
    if agent_num not in AGENT_PINS:
        raise ValueError("agent_num must be 1 or 2")

    enable_pin, direction_pin, step_pin = AGENT_PINS[agent_num]
    enable = LED(enable_pin)
    direction = LED(direction_pin)
    step = LED(step_pin)
    limit_switch = Button(LIMIT_SWITCH_PIN, pull_up=True, bounce_time=0.05)

    try:
        HOMING_STEP_DELAY = 0.0005
        print("Homing: moving LEFT to find first limit...")
        LEFT(direction)

        while not limit_switch.is_pressed:
            move(step, 1, step_delay=HOMING_STEP_DELAY)

        print("Left limit found.")

        RIGHT(direction)

        # move 300 steps away after finding limit to not double count a switch bounce
        move(step, 300, step_delay=HOMING_STEP_DELAY)
        
        total_steps = 300
        print("Moving RIGHT to find second limit...")

        while not limit_switch.is_pressed:
            move(step, 1, step_delay=HOMING_STEP_DELAY)
            total_steps += 1

        print(f"Right limit found. Total travel: {total_steps} steps")

        # Move to the middle
        half_steps = total_steps // 2
        print(f"Moving to middle ({half_steps} steps left)...")
        LEFT(direction)
        move(step, half_steps)

        step.off()
        enable.on()
        print("Homing complete.")

        return total_steps

    finally:
        enable.close()
        direction.close()
        step.close()
        limit_switch.close()


def move_pot(high:bool):
    """
    Moves the pot up and down. 
    If high is True, move the pot to the high position.
    If high is False, move the pot to the low position.
    """
    enable = LED(POT_PINS[0])
    direction = LED(POT_PINS[1])
    step = LED(POT_PINS[2])
    limit_switch = Button(LIMIT_SWITCH_PIN, pull_up=True, bounce_time=0.05)

    try:
        POT_STEP_DELAY = 0.00006
        if high:
            
            print("Moving pot Right (Up)...")
            RIGHT(direction)

            move(step, 6000, POT_STEP_DELAY)

        if not high:
            print("Moving pot Left (Down)...")
            LEFT(direction)

            move(step, 6000, POT_STEP_DELAY)
        #move(step, 15000, POT_STEP_DELAY)

    finally:
        enable.close()
        direction.close()
        step.close()
        limit_switch.close()


def test_buttons():
    limit_switch = Button(LIMIT_SWITCH_PIN, pull_up=True, bounce_time=0.05)

    try:
        while True:
            if limit_switch.is_pressed:
                print("closed")
            else:
                print("open")
            sleep(0.1)

    finally:
        limit_switch.close()

if __name__ == '__main__':
    try:
        # dispense(15, 1)
        homing_sequence(agent_num=1)
        # move_pot(high=True)
        pass

    except KeyboardInterrupt:
        # So gpiozero can perform automatic cleanup
        print("Ending program")