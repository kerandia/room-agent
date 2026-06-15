"""
ASCII Art Dreams - LCD-optimized for 20x4 HD44780 displays.
Safe characters only: | - _ / . * o O x X ^ @ () [] {} > < !
No backslashes, no unicode, no fancy chars.
"""
import random

DREAMS = {
    # === EMOTIONS (0-19) ===
    0: {"cat": "happy", "art": "   ^_^    \n  /   /   \n  |   |   \n   ---    "},
    1: {"cat": "happy", "art": "  /o/     \n   |      \n  / /     \n  YAY!    "},
    2: {"cat": "happy", "art": "  .---.   \n / ^_^ /  \n |     |  \n '---'    "},
    3: {"cat": "happy", "art": "  /(^_^)/ \n   |   |  \n  /|   |/ \n    |_|   "},
    4: {"cat": "happy", "art": "   /o/    \n    |     \n   / /    \n  ^_^     "},
    5: {"cat": "sad", "art": "   .-.    \n  (   )   \n   '-'    \n   T_T    "},
    6: {"cat": "sad", "art": "   ;_;    \n    |     \n   / /    \n  (sigh)  "},
    7: {"cat": "sad", "art": "  .---.   \n / x_x /  \n |  T  |  \n /___/    "},
    8: {"cat": "sad", "art": "   .__.   \n  /    /  \n | -- |   \n  /__/    "},
    9: {"cat": "angry", "art": "  >_<     \n  | |     \n  / /     \n  GRR!    "},
    10: {"cat": "angry", "art": "  .---.   \n / >_< /  \n | RAGE | \n '---'    "},
    11: {"cat": "angry", "art": "  #_#     \n  | |     \n  / /     \n  MAD!    "},
    12: {"cat": "excited", "art": "  /o/     \n   |      \n  / /     \n  WOW!    "},
    13: {"cat": "excited", "art": "  * * *   \n * * * *  \n  * * *   \n  YAY!    "},
    14: {"cat": "excited", "art": "  .---.   \n / ^_^ /  \n | OMG! | \n '---'    "},
    15: {"cat": "confused", "art": "   ?      \n  ? ?     \n   ?      \n  (???)   "},
    16: {"cat": "confused", "art": "  .---.   \n / ? ? /  \n | hmmm | \n '---'    "},
    17: {"cat": "confused", "art": "  ~ ? ~   \n ~ ~ ~ ~  \n  ~ ? ~   \n  (lost)  "},
    18: {"cat": "love", "art": "  <3 <3   \n <3 <3 <3 \n  <3 <3   \n          "},
    19: {"cat": "love", "art": "  .---.   \n / <3 /   \n | love | \n '---'    "},

    # === WEATHER (20-39) ===
    20: {"cat": "sun", "art": "    / /   \n     O     \n    / /    \n          "},
    21: {"cat": "sun", "art": "     *    \n   * O *   \n     *     \n          "},
    22: {"cat": "sun", "art": "   /   /  \n    ---    \n   /   /   \n          "},
    23: {"cat": "rain", "art": "   .-.    \n  (   )   \n   '-'    \n   | |    "},
    24: {"cat": "rain", "art": "   ~~~    \n   / /    \n  / / /   \n          "},
    25: {"cat": "rain", "art": "  .---.   \n / o o /  \n |  .  |  \n  /___/   "},
    26: {"cat": "cloud", "art": "   .--.   \n .(    ). \n  '----'  \n          "},
    27: {"cat": "cloud", "art": "  .---.   \n (     )  \n  '---'   \n          "},
    28: {"cat": "cloud", "art": "   ___    \n  /   /   \n  /___/   \n          "},
    29: {"cat": "snow", "art": "  *   *   \n * * * *  \n  *   *   \n * * * *  "},
    30: {"cat": "snow", "art": "  .---.   \n / i i /  \n |  .  |  \n  /___/   "},
    31: {"cat": "snow", "art": "   * *    \n  * * *   \n   * *    \n          "},
    32: {"cat": "wind", "art": "  ~ ~ ~   \n ~ ~ ~ ~  \n  ~ ~ ~   \n          "},
    33: {"cat": "wind", "art": "  --->    \n  --->    \n  --->    \n          "},
    34: {"cat": "wind", "art": "  ~ ~ ~   \n ~ ~ ~ ~  \n  ~ ~ ~   \n          "},
    35: {"cat": "storm", "art": "  .---.   \n / Z Z /  \n |  !  |  \n  /___/   "},
    36: {"cat": "storm", "art": "  .---.   \n / !!! /  \n | !!! |  \n  /___/   "},
    37: {"cat": "storm", "art": "  .---.   \n / ??? /  \n | ??? |  \n  /___/   "},
    38: {"cat": "hot", "art": "  (   )   \n (  _  )  \n  ) - (   \n          "},
    39: {"cat": "hot", "art": "  ,,,     \n ,,,,     \n  heat!   \n          "},

    # === OBJECTS (40-59) ===
    40: {"cat": "coffee", "art": "    [_]   \n    | |   \n   '---'  \n          "},
    41: {"cat": "coffee", "art": "   {---}  \n   |   |  \n   '---'  \n          "},
    42: {"cat": "coffee", "art": "   .---.  \n   |   |  \n   '---'  \n          "},
    43: {"cat": "code", "art": "   >_>    \n  {   }   \n  [___]   \n          "},
    44: {"cat": "code", "art": "  </>     \n  { }     \n  [ ]     \n          "},
    45: {"cat": "code", "art": "  >_  >_  \n  { } { } \n  [_] [_] \n          "},
    46: {"cat": "code", "art": "  .---.   \n / </> /  \n | CODE|  \n  /___/   "},
    47: {"cat": "music", "art": "   o      \n  o o     \n   o  o   \n  o o o   "},
    48: {"cat": "music", "art": "  |~|~|   \n  |~|~|   \n  |~|~|   \n          "},
    49: {"cat": "music", "art": "  ooo     \n  ooo     \n  ooo     \n          "},
    50: {"cat": "heart", "art": "  .---.   \n / <3 /   \n | love|  \n  /___/   "},
    51: {"cat": "heart", "art": "  <3 <3   \n <3 <3 <3 \n  <3 <3   \n          "},
    52: {"cat": "star", "art": "    *     \n   * *    \n  * * *   \n   * *    "},
    53: {"cat": "star", "art": "    *     \n   * *    \n  * * *   \n   * *    "},
    54: {"cat": "moon", "art": "   .-.    \n  (   )   \n   '-'    \n          "},
    55: {"cat": "moon", "art": "   )      \n  ( )     \n   (      \n          "},
    56: {"cat": "planet", "art": "    .--.  \n   /    / \n  | () |  \n   /__/   "},
    57: {"cat": "planet", "art": "    ___   \n   /   /  \n   /___/  \n          "},
    58: {"cat": "rocket", "art": "    //    \n   /  /   \n  /    /  \n / || /  "},
    59: {"cat": "rocket", "art": "    ^     \n   /|/   \n  / | /  \n          "},

    # === NATURE (60-79) ===
    60: {"cat": "tree", "art": "    *     \n   ***    \n  *****   \n    |     "},
    61: {"cat": "tree", "art": "    *     \n   ***    \n  *****   \n  *****   "},
    62: {"cat": "flower", "art": "    *     \n   ***    \n    |     \n          "},
    63: {"cat": "flower", "art": "   (*)    \n  (***)   \n   (*)    \n          "},
    64: {"cat": "ocean", "art": "  ~ ~ ~   \n ~ ~ ~ ~  \n  ~ ~ ~   \n          "},
    65: {"cat": "ocean", "art": "  ~~~~~~  \n ~~~~~~~~ \n  ~~~~~~  \n          "},
    66: {"cat": "mountain", "art": "    //    \n   /  /   \n  /____/  \n          "},
    67: {"cat": "mountain", "art": "     //   \n    /  /  \n   /    / \n  /______/"},
    68: {"cat": "desert", "art": "   .--.   \n  /    /  \n  '----'  \n          "},
    69: {"cat": "desert", "art": "   .--.   \n  /    /  \n  '----'  \n          "},
    70: {"cat": "fire", "art": "    ,     \n   ,)     \n  ))      \n ((       "},
    71: {"cat": "fire", "art": "   )  )   \n  ( /( )  \n  )/ v(   \n          "},
    72: {"cat": "fire", "art": "    )     \n   ( )    \n  (   )   \n   ) (    "},
    73: {"cat": "water", "art": "    .     \n   /|/   \n  / | /  \n          "},
    74: {"cat": "water", "art": "   ~~~    \n  ~ ~ ~   \n   ~~~    \n          "},
    75: {"cat": "earth", "art": "    ___   \n   /   /  \n  | () |  \n   /___/  "},
    76: {"cat": "earth", "art": "    .--.  \n   /    / \n  | ()  | \n   /__/   "},
    77: {"cat": "leaf", "art": "    .     \n   /|     \n  / |     \n          "},
    78: {"cat": "leaf", "art": "    .     \n   /|/   \n  / | /  \n          "},
    79: {"cat": "mushroom", "art": "   .---.  \n  /     / \n  |     | \n   '---'  "},

    # === TECH (80-99) ===
    80: {"cat": "computer", "art": "  .---.   \n /     /  \n | [ ] |  \n '---'    "},
    81: {"cat": "computer", "art": "  .---.   \n / [ ] /  \n |     |  \n '---'    "},
    82: {"cat": "phone", "art": "  .---.   \n |     |  \n |  o  |  \n |     |  "},
    83: {"cat": "robot", "art": "  .---.   \n / o o /  \n |  -  |  \n  /___/   "},
    84: {"cat": "robot", "art": "  .---.   \n / ^ ^ /  \n |  w  |  \n  /___/   "},
    85: {"cat": "alien", "art": "  .---.   \n / * * /  \n |  ^  |  \n  /___/   "},
    86: {"cat": "alien", "art": "  .---.   \n / * * /  \n |  v  |  \n  /___/   "},
    87: {"cat": "ghost", "art": "  .---.   \n / o o /  \n |  .  |  \n '-----'  "},
    88: {"cat": "ghost", "art": "  .---.   \n / x x /  \n |  .  |  \n '-----'  "},
    89: {"cat": "skull", "art": "  .---.   \n / x x /  \n |  ^  |  \n '---'    "},
    90: {"cat": "cat", "art": "  /_/     \n ( o.o )  \n  > ^ <   \n          "},
    91: {"cat": "cat", "art": "  /_/     \n ( ^.^ )  \n  > ^ <   \n          "},
    92: {"cat": "dog", "art": "  /_/     \n ( o.o )  \n  > w <   \n          "},
    93: {"cat": "dog", "art": "  /_/     \n ( ^.^ )  \n  > w <   \n          "},
    94: {"cat": "bear", "art": "  .---.   \n / o o /  \n |  ^  |  \n  /___/   "},
    95: {"cat": "bird", "art": "    __    \n   /  /   \n  /    /  \n          "},
    96: {"cat": "bird", "art": "    __    \n   /^^/   \n  /    /  \n          "},
    97: {"cat": "fish", "art": "   <>     \n  <><>    \n   <>     \n          "},
    98: {"cat": "fish", "art": "   <>     \n  <><>    \n   <>     \n          "},
    99: {"cat": "butterfly", "art": "  //  //  \n  //  //  \n   || ||  \n          "},
}


def get_dream_by_id(dream_id):
    """Get LCD-optimized ASCII art by ID, normalized to 4 lines x 20 chars"""
    dream = DREAMS.get(dream_id % 100, DREAMS[0])
    art = dream["art"]
    
    # Normalize to exactly 4 lines, max 20 chars
    lines = art.split('\n')
    while len(lines) < 4:
        lines.append('')
    lines = lines[:4]
    
    # Truncate + right-pad each line
    normalized = []
    for line in lines:
        line = line[:20].ljust(20)
        normalized.append(line)
    
    return '\n'.join(normalized)


def get_dream_ids_by_category(category):
    """Get all dream IDs for a category"""
    return [did for did, d in DREAMS.items() if d["cat"] == category]


def get_all_categories():
    """Get all unique categories"""
    return list(set(d["cat"] for d in DREAMS.values()))


def get_random_dream():
    """Get a random dream"""
    return random.choice(list(DREAMS.values()))["art"]


def get_dream_list_for_prompt():
    """Get a compact list of all dreams for the LLM prompt"""
    lines = []
    for did in sorted(DREAMS.keys()):
        cat = DREAMS[did]["cat"]
        lines.append(f"{did}: {cat}")
    return "\n".join(lines)
