from board import GP10, GP11, GP12, GP13, GP21, GP20, GP19, GP18
from board import GP17, GP8, GP16, GP15, GP14, GP9
from board import GP22, GP25
from digitalio import DigitalInOut, Direction, DriveMode, Pull
import pwmio

import usb_hid
import usb_cdc

# for this stuff, you have to download it and stick the unzipped adafruit_hid folder under lib/ on the CircuitPython drive
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode as KC

# for some reason adafruit_hid couldn't be bothered to include these keycodes
# instead see https://gist.github.com/ekaitz-zarraga/2b25b94b711684ba4e969e5a5723969b
KX_VOLUP=0xed
KX_VOLDN=0xee

from time import sleep

# TODO style is all over the place; the excuse today is that i'm not normally a python person really
# TODO there are some weird decisions because it was all kind of improvised, but it does seem to work, and at least i'm writing comments now


########################################################################
#
#  define the physical layout
#

# "fake" keycodes to represent layer-switching keys
# bigger than the single byte that actual keycodes are, which is convenient to avoid handling them like normal keys
LYR_L = 1000
LYR_R = 1001
LYR_NAV = 1002
LYR_EXTRA = 1003

# there are eight rows of six keys, instead of four rows of twelve, in order to reduce pin count.
# the left rows are laid out with the columns "going backwards" (i.e. mirrored vs the right rows)
# it made sense at the time but it does make things mildly confusing here.

ROW_PINS = [[GP10,GP11,GP12,GP13], [GP21,GP20,GP19,GP18]]  # left rows, then right rows, top is [0]
COL_PINS = [GP17,GP8,GP16,GP15,GP14,GP9]  # centre is [0], edge is [5]

def LSFT(v):
    return [KC.LEFT_SHIFT, v]

# currently unused, and actually i did this by mistake
# however i left it in because it could be used in the future to emulate a dvorak layout kind of poorly on someone else's computer, maybe?
KCS_DVORAK_EMU = [
    [KC.TAB, KC.QUOTE, KC.COMMA, KC.PERIOD, KC.P, KC.Y,   KC.F, KC.G, KC.C, KC.R, KC.L, KC.FORWARD_SLASH],
    [KC.BACKSPACE, KC.A, KC.O, KC.E, KC.U, KC.I,   KC.D, KC.H, KC.T, KC.N, KC.S, KC.MINUS],
    [KC.ESCAPE, KC.SEMICOLON, KC.Q, KC.J, KC.K, KC.X,   KC.B, KC.M, KC.W, KC.V, KC.Z, LYR_NAV],
    [KC.LEFT_SHIFT, LYR_EXTRA, KC.LEFT_GUI, KC.LEFT_ALT, KC.LEFT_CONTROL, LYR_L,   LYR_R, KC.SPACE, KC.RIGHT_GUI, KC.RIGHT_CONTROL, KC.RIGHT_ALT, KC.RIGHT_SHIFT],
]

# normal layer, the default set of software keys that our hardware keys correspond to
KCS_NORMAL = [
    [KC.TAB, KC.Q, KC.W, KC.E, KC.R, KC.T,   KC.Y, KC.U, KC.I, KC.O, KC.P, KC.LEFT_BRACKET],
    [KC.BACKSPACE, KC.A, KC.S, KC.D, KC.F, KC.G,   KC.H, KC.J, KC.K, KC.L, KC.SEMICOLON, KC.QUOTE],
    [KC.ESCAPE, KC.Z, KC.X, KC.C, KC.V, KC.B,   KC.N, KC.M, KC.COMMA, KC.PERIOD, KC.FORWARD_SLASH, LYR_NAV],
    [KC.LEFT_SHIFT, LYR_EXTRA, KC.LEFT_GUI, KC.LEFT_ALT, KC.LEFT_CONTROL, LYR_L,   LYR_R, KC.SPACE, KC.RIGHT_GUI, KC.RIGHT_CONTROL, KC.RIGHT_ALT, KC.RIGHT_SHIFT],
]

# other layers, accessed through the layer shifter keys
KCS_SYMBOLS = [
    [KC.GRAVE_ACCENT, LSFT(KC.EIGHT), KC.NINE, KC.EIGHT, KC.SEVEN, LSFT(KC.RIGHT_BRACKET),   LSFT(KC.FOUR), KC.MINUS, KC.EQUALS, LSFT(KC.SIX), LSFT(KC.SEVEN), LSFT(KC.ONE)],
    [KC.BACKSPACE, KC.BACKSLASH, KC.SIX, KC.FIVE, KC.FOUR, LSFT(KC.FIVE),   KC.RIGHT_BRACKET, LSFT(KC.NINE), LSFT(KC.ZERO), LSFT(KC.THREE), KC.LEFT_BRACKET, KC.RETURN],
    [LSFT(KC.TWO), KC.ZERO, KC.THREE, KC.TWO, KC.ONE, KC.QUOTE,   None, LSFT(KC.MINUS), LSFT(KC.EQUALS), LSFT(KC.GRAVE_ACCENT), LSFT(KC.BACKSLASH), LYR_NAV],
    [KC.LEFT_SHIFT, LYR_EXTRA, KC.LEFT_GUI, KC.LEFT_ALT, KC.LEFT_CONTROL, LYR_L,   LYR_R, KC.SPACE, KC.RIGHT_GUI, KC.RIGHT_CONTROL, KC.RIGHT_ALT, KC.RIGHT_SHIFT],
]
KCS_NAVIGATION = [
    [KC.F15, KC.F12, KC.F9, KC.F8, KC.F7, None,   KC.DELETE, LSFT(KC.Q), KC.Q, KC.GRAVE_ACCENT, KC.TAB, None],
    [KC.F14, KC.F11, KC.F6, KC.F5, KC.F4, None,   None, KC.LEFT_ARROW, KC.DOWN_ARROW, KC.UP_ARROW, KC.RIGHT_ARROW, KC.RETURN],
    [KC.F13, KC.F10, KC.F3, KC.F2, KC.F1, None,   None, KC.HOME, KC.PAGE_DOWN, KC.PAGE_UP, KC.END, LYR_NAV],
    [KC.LEFT_SHIFT, LYR_EXTRA, KC.LEFT_GUI, KC.LEFT_ALT, KC.LEFT_CONTROL, LYR_L,   LYR_R, KC.SPACE, KC.RIGHT_GUI, KC.RIGHT_CONTROL, KC.RIGHT_ALT, KC.RIGHT_SHIFT],
]
KCS_EXTRA = [
    [None, None, None, None, None, None,   None, None, None, None, None, None],
    [None, None, None, None, None, None,   None, None, KX_VOLDN, KX_VOLUP, None, None],
    [None, None, None, None, None, None,   None, None, None, None, None, LYR_NAV],
    [None, LYR_EXTRA, None, None, None, LYR_L,   LYR_R, None, None, None, None, None],
]

# TODO the layer shifters themselves have to be in every layer, in order for them to release properly i think? but it's quite annoying


########################################################################
#
#  define the hardware interface
#

HID_KB_DEVICE = None
while not HID_KB_DEVICE:
    try:
        HID_KB_DEVICE = Keyboard(usb_hid.Device.KEYBOARD)
    except:
        sleep(0.5)

def make_led(pin):
    led = pwmio.PWMOut(pin, frequency=5000, duty_cycle=0)
    return led

def make_row(pin):
    row = DigitalInOut(pin)
    row.direction = Direction.OUTPUT
    row.drive_mode = DriveMode.OPEN_DRAIN
    row.value = True
        # i.e. default: high impedance, don't pull down
        # set value = False to pull down, which will show up as value = False on pressed keys' column pins
    return row

def make_col(pin):
    col = DigitalInOut(pin)
    col.direction = Direction.INPUT
    col.pull = Pull.UP
    return col

led_green = make_led(GP25)
led_front = make_led(GP22)

rows = [[make_row(pin) for pin in side] for side in ROW_PINS]
cols = [make_col(pin) for pin in COL_PINS]


########################################################################
#
#  be a keyboard
#

pressed_keys = {}
    # keeps track of pressed keys
    # could just be a set... except there are layers
    # therefore, have to keep track of what software keycodes they corresponded to when they were pressed, to handle key release ~properly
    # TODO this isn't actually good enough -- multiple keys can all be trying to press e.g. "shift" at once, so modifiers quite possibly need a "reference count" in order to not get released whilst another key is also trying to press them

current_layer_codes = KCS_NORMAL
    # keeps track of current layer (changed by LYR_ keys, layer shifters, outside the scan function)
    # this changes the lookup of what keys to press in software, corresponding to each physical key

def scan(hid=True):
    global pressed_keys, current_layer_codes

    for row_idx in range(4):
        x_idx = 0
            # keep track of the actual physical column position, while walking the columns in the mirrored order they are actually laid out in hardware

        for side_idx, side_pins in enumerate(rows):
            row_pin = side_pins[row_idx]
            row_pin.value = 0

            # this is what handles the mirroredness
            for col_idx, col_pin in enumerate(reversed(cols) if side_idx == 0 else cols):
                keycode = row_idx*12 + x_idx
                    # look up "physical" keycode to use as the dict key to track the physical key being pressed

                if keycode != None:
                    pressed = pressed_keys.get(keycode)

                    if col_pin.value == 0:
                        if pressed:
                            pressed['debounce_count'] = 2
                        else:
                            send_keycode = current_layer_codes[row_idx][x_idx]
                            pressed_keys[keycode] = {'sent_keycode': send_keycode, 'debounce_count': 2}
                            if send_keycode != None:
                                # this listification handles the case where a key presses e.g. shift + another key
                                # (if it's just a single key, wrap it in a list so it doesn't need a different implementation)
                                for k in (send_keycode if isinstance(send_keycode, list) else [send_keycode]):
                                    if k > 0 and k <= 255:
                                        if hid:
                                            HID_KB_DEVICE.press(k)
                                    # else: it's a "special" layer shifter key
                                        # so sticking it in `pressed` is enough for it to get picked up outside this function

                    if col_pin.value == 1 and pressed:
                        pressed['debounce_count'] -= 1
                        if pressed['debounce_count'] == 0:
                            sent_keycode = pressed['sent_keycode']
                            if sent_keycode != None:
                                for k in (sent_keycode if isinstance(sent_keycode, list) else [sent_keycode]):
                                    if k > 0 and k <= 255:
                                        HID_KB_DEVICE.release(k)
                            del pressed_keys[keycode]

                x_idx += 1
            #} for col_idx
            row_pin.value = 1
        #} for side_idx
    #} for row_idx

def keyboard():
    global pressed_keys, current_layer_codes
    pressed_keys = {34:{'sent_keycode':[], 'debounce_count':1}}
    current_layer_codes = KCS_NORMAL
    
    navLock = False
        # an idea (needs work) to lock the navigation layer on in place of the "normal" layer

    while True:
        led_green.duty_cycle=600
            # naive attempt to make it obvious if scanning gets stuck.
            # actually does work, because a crash under CircuitPython blanks out the LED!
        scan(hid=True)
        led_green.duty_cycle=0

        z = 36 + 1 in pressed_keys  # LYR_EXTRA
        x = 24 + 11 in pressed_keys  # LYR_NAV
        r = 36 + 6 in pressed_keys  # LYR_R
        l = 36 + 5 in pressed_keys  # LYR_L
        if z:
            led_front.duty_cycle = 65535
            current_layer_codes = KCS_EXTRA
            if x:
                navLock = True
                break
        elif x or l and r:
            led_front.duty_cycle = 3000
            current_layer_codes = KCS_NAVIGATION
            navLock = False
        elif l or r:
            led_front.duty_cycle = 5000
            current_layer_codes = KCS_SYMBOLS
            navLock = False
        else:
            led_front.duty_cycle = 3000 if navLock else 1000 if pressed_keys else 0
            current_layer_codes = KCS_NAVIGATION if navLock else KCS_NORMAL

        sleep(0.00005)
            # :shrug emoji:
            
        if current_layer_codes == KCS_EXTRA and pressed_keys.get(25):  # Z
            break

def steno():
    current_layer_codes = KCS_NORMAL
    scans = 0
    cycle = 600
    
    packet = bytearray(6)
    packet[0] = 128
    
    chord_started = False
    
    while True:
        scan(hid=False)
        scans += 1
        if scans == 10:
            scans = 0
            cycle = 600 if cycle == 0 else 0
            led_front.duty_cycle = cycle
        
        if not pressed_keys:
            if chord_started:
                usb_cdc.data.write(packet)
                packet = bytearray(6)
                packet[0] = 128
                usb_cdc.data.write(packet)
                chord_started = False
        else:
            chord_started = True

        if pressed_keys.get(5):
            packet[2] = packet[2] | 8  # *1
        if pressed_keys.get(17):
            packet[2] = packet[2] | 4  # *2
        if pressed_keys.get(6):
            packet[3] = packet[3] | 32 # *3
        if pressed_keys.get(18):
            packet[3] = packet[3] | 16 # *4
            
        if pressed_keys.get(1):
            packet[1] = packet[1] | 64 # s
        if pressed_keys.get(2):
            packet[1] = packet[1] | 16 # t
        if pressed_keys.get(3):
            packet[1] = packet[1] | 4  # p
        if pressed_keys.get(4):
            packet[1] = packet[1] | 1  # h
        
        if pressed_keys.get(13):
            packet[1] = packet[1] | 32 # s
        if pressed_keys.get(14):
            packet[1] = packet[1] | 8  # k
        if pressed_keys.get(15):
            packet[1] = packet[1] | 2  # w
        if pressed_keys.get(16):
            packet[2] = packet[2] | 64 # r

        if pressed_keys.get(39):
            packet[2] = packet[2] | 32 # a
        if pressed_keys.get(40):
            packet[2] = packet[2] | 16 # o

        if pressed_keys.get(7):
            packet[3] = packet[3] | 2  # f
        if pressed_keys.get(8):
            packet[4] = packet[4] | 64 # p
        if pressed_keys.get(9):
            packet[4] = packet[4] | 16 # l
        if pressed_keys.get(10):
            packet[4] = packet[4] | 4  # t
        if pressed_keys.get(11):
            packet[4] = packet[4] | 1  # d
        
        if pressed_keys.get(19):
            packet[3] = packet[3] | 1  # r
        if pressed_keys.get(20):
            packet[4] = packet[4] | 32 # b
        if pressed_keys.get(21):
            packet[4] = packet[4] | 8  # g
        if pressed_keys.get(22):
            packet[4] = packet[4] | 2  # s
        if pressed_keys.get(23):
            packet[5] = packet[5] | 1  # z

        if pressed_keys.get(43):
            packet[3] = packet[3] | 8  # e
        if pressed_keys.get(44):
            packet[3] = packet[3] | 4  # u

        sleep(0.01)
            
        #print(pressed_keys)
        if pressed_keys.get(34):  # forward slash
            break
            
while True:
    keyboard()
    steno()
