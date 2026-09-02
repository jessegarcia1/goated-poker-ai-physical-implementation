from gpiozero import LED, Button
from time import sleep

STEP_DELAY = 0.0000008
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


def dispense_one_chip(direction: str, direction_pin, step_pin):
    if direction not in ("L", "R"):
        raise ValueError("direction must be 'L' or 'R'")

    opposite_direction = "R" if direction == "L" else "L"

    (LEFT if direction == "L" else RIGHT)(direction_pin)
    move(step_pin, STEPS_PER_CHIP)      # dispense one chip

    (LEFT if opposite_direction == "L" else RIGHT)(direction_pin)
    sleep(STEP_DELAY)
    move(step_pin, STEPS_PER_CHIP)      # return to reset position
    sleep(STEP_DELAY)


def dispense(num_dispensed: int, agent_num: int):
    if agent_num not in AGENT_PINS:
        raise ValueError("agent_num must be 1 or 2")

    enable_pin_num, direction_pin_num, step_pin_num = AGENT_PINS[agent_num]
    enable_pin = LED(enable_pin_num)
    direction_pin = LED(direction_pin_num)
    step_pin = LED(step_pin_num)

    try:
        enable_pin.off()
        direction = "L"

        for _ in range(num_dispensed):
            print(_)
            dispense_one_chip(direction, direction_pin, step_pin)
            direction = "R" if direction == "L" else "L"

    except KeyboardInterrupt:
        pass

    finally:
        enable_pin.on()
        step_pin.off()
        enable_pin.close()
        direction_pin.close()
        step_pin.close()


def little_steps(direction: str, step_pin, direction_pin, count: int):
    if direction == "L":
        sleep(.05)
        LEFT(direction_pin)
        sleep(.05)

        for _ in range(count):
            step_pin.on()
            sleep(STEP_DELAY)
            step_pin.off()
            sleep(STEP_DELAY)

    elif direction == "R":
        for _ in range(count):
            step_pin.on()
            sleep(STEP_DELAY)
            step_pin.off()
            sleep(STEP_DELAY)


def homing_sequence(agent_num:int):
    if agent_num not in AGENT_PINS:
        raise ValueError("agent_num must be 1 or 2")

    enable_pin_num, direction_pin_num, step_pin_num = AGENT_PINS[agent_num]
    enable_pin = LED(enable_pin_num)
    direction_pin = LED(direction_pin_num)
    step_pin = LED(step_pin_num)
    limit_switch = Button(LIMIT_SWITCH_PIN, pull_up=True, bounce_time=0.05)

    try:
        HOMING_STEP_DELAY = 0.0005
        print("Homing: moving LEFT to find first limit...")
        LEFT(direction_pin)

        while not limit_switch.is_pressed:
            move(step_pin, 1, step_delay=HOMING_STEP_DELAY)

        print("Left limit found.")

        RIGHT(direction_pin)

        # move 300 steps away after finding limit to not double count a switch bounce
        move(step_pin, 300, step_delay=HOMING_STEP_DELAY)
        
        total_steps = 300
        print("Moving RIGHT to find second limit...")

        while not limit_switch.is_pressed:
            move(step_pin, 1, step_delay=HOMING_STEP_DELAY)
            total_steps += 1

        print(f"Right limit found. Total travel: {total_steps} steps")

        # Move to the middle
        half_steps = total_steps // 2
        print(f"Moving to middle ({half_steps} steps left)...")
        LEFT(direction_pin)
        move(step_pin, half_steps)

        step_pin.off()
        enable_pin.on()
        print("Homing complete.")

        return total_steps

    finally:
        enable_pin.close()
        direction_pin.close()
        step_pin.close()
        limit_switch.close()


def move_pot(high:bool):
    """
    Moves the pot up and down. 
    If high is True, move the pot to the high position.
    If high is False, move the pot to the low position.
    """
    enable_pin_num, direction_pin_num, step_pin_num = POT_PINS
    enable_pin = LED(enable_pin_num)
    direction_pin = LED(direction_pin_num)
    step_pin = LED(step_pin_num)
    limit_switch = Button(LIMIT_SWITCH_PIN, pull_up=True, bounce_time=0.05)

    try:
        POT_STEP_DELAY = 0.00006
        if high:
            
            print("Moving pot Right (Up)...")
            RIGHT(direction_pin)

            move(step_pin, 6000, POT_STEP_DELAY)

        if not high:
            print("Moving pot Left (Down)...")
            LEFT(direction_pin)

            move(step_pin, 6000, POT_STEP_DELAY)
        #move(step_pin, 15000, POT_STEP_DELAY)

    finally:
        enable_pin.close()
        direction_pin.close()
        step_pin.close()
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
        #homing_sequence(agent_num=1)
        # move_pot(high=True)
        dispense(num_dispensed=3, agent_num=1)
        pass

    except KeyboardInterrupt:
        # So gpiozero can perform automatic cleanup
        print("Ending program")