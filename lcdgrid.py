"""
LCD Grid System - A movable character on a 20x4 LCD.
The LLM controls the character by outputting actions.
"""

import random

class LCDGrid:
    """A 20x4 grid where a character can move around"""
    
    def __init__(self, cols=20, rows=4):
        self.cols = cols
        self.rows = rows
        # Character position (center)
        self.char_x = cols // 2
        self.char_y = rows // 2
        # Character appearance
        self.char = "@"
        self.mood = "neutral"  # neutral, happy, sad, excited, angry, sleepy
        # Trail of where we've been
        self.trail = []
        self.max_trail = 8
        # Objects on the grid
        self.objects = []  # list of (x, y, char, name)
        # Animation state
        self.animation = None
        self.anim_frame = 0
        
        # Mood faces
        self.mood_chars = {
            "neutral": "@",
            "happy": "^_^",
            "sad": "T_T",
            "excited": "O_O",
            "angry": ">_<",
            "sleepy": "-_-",
            "love": "<3",
            "coding": ">_",
        }
        
        # Direction vectors
        self.directions = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
            "up-left": (-1, -1),
            "up-right": (1, -1),
            "down-left": (-1, 1),
            "down-right": (1, 1),
        }
    
    def move(self, direction):
        """Move character in a direction"""
        if direction not in self.directions:
            return False
        
        dx, dy = self.directions[direction]
        new_x = self.char_x + dx
        new_y = self.char_y + dy
        
        # Bounce off walls
        if new_x < 0 or new_x >= self.cols:
            dx = -dx
            new_x = self.char_x + dx
        if new_y < 0 or new_y >= self.rows:
            dy = -dy
            new_y = self.char_y + dy
        
        # Save trail
        self.trail.append((self.char_x, self.char_y))
        if len(self.trail) > self.max_trail:
            self.trail.pop(0)
        
        self.char_x = new_x
        self.char_y = new_y
        return True
    
    def teleport(self, x, y):
        """Move character to specific position"""
        if 0 <= x < self.cols and 0 <= y < self.rows:
            self.trail.append((self.char_x, self.char_y))
            if len(self.trail) > self.max_trail:
                self.trail.pop(0)
            self.char_x = x
            self.char_y = y
            return True
        return False
    
    def set_mood(self, mood):
        """Change character mood"""
        if mood in self.mood_chars:
            self.mood = mood
            self.char = self.mood_chars[mood]
            return True
        return False
    
    def add_object(self, x, y, char, name):
        """Add an object to the grid"""
        self.objects.append((x, y, char, name))
    
    def clear_objects(self):
        """Clear all objects"""
        self.objects = []
    
    def set_animation(self, animation):
        """Set an animation to play"""
        self.animation = animation
        self.anim_frame = 0
    
    def render(self):
        """Render the grid to 4 lines of 20 chars"""
        # Create empty grid
        grid = [[' ' for _ in range(self.cols)] for _ in range(self.rows)]
        
        # Draw trail (dim)
        for i, (tx, ty) in enumerate(self.trail):
            if 0 <= tx < self.cols and 0 <= ty < self.rows:
                grid[ty][tx] = '.'
        
        # Draw objects
        for ox, oy, ochar, _ in self.objects:
            if 0 <= ox < self.cols and 0 <= oy < self.rows:
                grid[oy][ox] = ochar
        
        # Draw character
        char_display = self.char[:3]  # Max 3 chars for mood
        start_x = self.char_x - len(char_display) // 2
        for i, c in enumerate(char_display):
            x = start_x + i
            if 0 <= x < self.cols:
                grid[self.char_y][x] = c
        
        # Convert to strings
        lines = [''.join(row) for row in grid]
        return lines
    
    def get_state(self):
        """Get grid state for LLM context"""
        return {
            "char_x": self.char_x,
            "char_y": self.char_y,
            "mood": self.mood,
            "objects": [(x, y, c) for x, y, c, _ in self.objects],
            "trail_length": len(self.trail),
        }


# Available tools for the LLM
TOOLS = {
    "move": {
        "description": "Move the character in a direction",
        "params": {"dir": "up|down|left|right|up-left|up-right|down-left|down-right"},
    },
    "teleport": {
        "description": "Move character to specific position",
        "params": {"x": "0-19", "y": "0-3"},
    },
    "mood": {
        "description": "Change character mood/expression",
        "params": {"mood": "neutral|happy|sad|excited|angry|sleepy|love|coding"},
    },
    "say": {
        "description": "Display a message on the grid",
        "params": {"text": "message to display"},
    },
    "spawn": {
        "description": "Place an object on the grid",
        "params": {"x": "0-19", "y": "0-3", "char": "single character", "name": "object name"},
    },
    "clear": {
        "description": "Clear all objects from grid",
        "params": {},
    },
    "animate": {
        "description": "Play an animation",
        "params": {"type": "bounce|spin|wave|random_walk"},
    },
}


def get_tools_for_prompt():
    """Get tool definitions for the LLM prompt"""
    lines = []
    for name, tool in TOOLS.items():
        params = ", ".join(f"{k}={v}" for k, v in tool["params"].items())
        lines.append(f"- {name}({params}): {tool['description']}")
    return "\n".join(lines)
