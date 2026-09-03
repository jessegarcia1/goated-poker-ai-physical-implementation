from gpiozero import Button
from time import sleep

# Button is input device
CHECK_CALL = Button(13, pull_up=True)
RAISE = Button(20, pull_up=True)
FOLD = Button(12, pull_up=True)

pending_action = None

def return_check_call():
    global pending_action
    pending_action = "check"

def return_raise():
    global pending_action
    pending_action = "raise"

def return_fold():
    global pending_action
    pending_action = "fold"

CHECK_CALL.when_pressed = return_check_call
RAISE.when_pressed = return_raise
FOLD.when_pressed = return_fold

def wait_for_player_action():
    global pending_action
    pending_action = None  # clear stale value
    
    print("Waiting for player action...")
    while pending_action is None:
        sleep(0.05)
    action = pending_action
    pending_action = None  
    print("Chosen action: ", action)
    return action

def test_buttons():
    while True:
        if CHECK_CALL.is_pressed:
            print("check")
        elif RAISE.is_pressed:
            print("raise")
        elif FOLD.is_pressed:
            print("fold")
        else:
            print("None")
        sleep(0.05)
        
if __name__ == '__main__':
    try:
        # action = wait_for_button_press()
        # print(f"Action selected: {action}")
        test_buttons()
        pass

    except KeyboardInterrupt:
        # So gpiozero can perform automatic cleanup
        print("Ending program")
    finally:
        for device in (CHECK_CALL, RAISE, FOLD):
            try:
                device.close()
            except Exception as exc:
                print(f"Warning: failed to close {device}: {exc}")