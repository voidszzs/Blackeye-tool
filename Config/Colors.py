# Colors used across the suite
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
REVERSE = "\033[7m"

BLACK = "\033[30m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"

# aliases
red = RED
white = WHITE
green = GREEN
yellow = YELLOW
blue = BLUE
cyan = CYAN
magenta = MAGENTA
reset = RESET
bold = BOLD

MAIN = RED
ACCENT = WHITE
INFO_COLOR = CYAN
OK_COLOR = GREEN
WARN_COLOR = YELLOW
ERR_COLOR = RED

try:
    import colorama
    colorama.init(autoreset=False)
except Exception:
    pass


def colorize(text, color):
    return f"{color}{text}{RESET}"

def MainColor(t): return f"{RED}{t}{RESET}"
def OkColor(t): return f"{GREEN}{t}{RESET}"
def WarnColor(t): return f"{YELLOW}{t}{RESET}"
def ErrColor(t): return f"{RED}{t}{RESET}"
def InfoColor(t): return f"{CYAN}{t}{RESET}"
