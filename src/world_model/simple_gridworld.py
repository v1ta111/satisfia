from . import MDPWorldModel

# based in large part on https://gymnasium.farama.org/tutorials/gymnasium_basics/environment_creation/

import numpy as np
import pygame

import gymnasium as gym
from gymnasium import spaces


class SimpleGridworld(MDPWorldModel):
    """A world model of a simple MDP-type Gridworld environment.
    
    A *state* here is a pair (num_state, str_state), where both entries contain the same data,
    once as a tuple of integers (which is convenient for reinforcement learning with PyTorch)
    and once as a string (which is more performant when used as a key for dictionaries).
    The data encoded in both versions of the state is following sequence of items,
    each one encoded as one or two integers (in num_state) and one or two characters (in str_state):

    - positions 1+2: the current position x,y of the agent
    - positions 3+4: the previous position x,y of the agent
    - positions 5...4+k: for each of k immovable objects with variable state, its state
    - positions 5+k..4+k+2*l: for each of l movable objects without a variable state, its position x,y 
    - positions 5+k+2*l...4+k+2*l+3*m: for each of m movable objects with a variable state, 
                                       its state and its position x,y

    A *coordinate* in a position is encoded in num_state as a number from 1...26 
    and in str_state as a letter from 'A'...'Z'. 
    An object's position can also be (-1,-1) or ('?','?') if the object is not present, 
    or (0,0) or ('@','@') if it is in the agent's inventory.
    This way the numerical representation always equals the ASCII code of the character representation minus 64.

    Objects are *ordered* by their initial position in the ascii-art grid representation in row-major order.

    The *grid* and the agent's and all objects' *initial positions* are given as an array of strings,
    each string representing one row of the grid, each character representing one cell of the grid,
    with the following character meanings: 
    
    - '#' (hash): wall
    - ' ' (blank): empty space
    - '@': agent's initial position
    - ... (TODO: take from gdoc, compare with pycolab asciiart conventions, 
          try to harmonize them, and add things that are missing)

    *Deltas* (rewards) can accrue from the following events:
    - Time passing. This is specified by time_delta or a list time_deltas of length max_episode_length.
    - The agent stepping onto a certain object. This is specified by a list object_deltas
      ordered by the objects' initial positions in the ascii-art grid representation in row-major order.
    - The agent entering a certain position. This is specified by 
        - another array of strings of the same size as the grid, 
          containing cell_codes with the following character meanings:
            - ' ' (space): no Delta
            - '<character>': Delta as specified by cell_code2delta['<character>']
        - a dictionary cell_code2delta listing the actual Delta values for each cell_code in that grid
    """

    max_episode_length = None
    """The maximum number of steps in an episode."""

    # TODO: adapt the following code to our needs:

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(self, render_mode=None, grid=[['A']]):
        self.window_size = 512  # The size of the PyGame window

        # Observations are dictionaries with the agent's and the target's location.
        # Each location is encoded as an element of {0, ..., `size`}^2, i.e. MultiDiscrete([size, size]).
        self.observation_space = spaces.Dict(
            {
                "agent": spaces.Box(0, size - 1, shape=(2,), dtype=int),
                "target": spaces.Box(0, size - 1, shape=(2,), dtype=int),
            }
        )

        # We have 4 actions, corresponding to "right", "up", "left", "down"
        self.action_space = spaces.Discrete(4)

        """
        The following dictionary maps abstract actions from `self.action_space` to
        the direction we will walk in if that action is taken.
        I.e. 0 corresponds to "right", 1 to "up" etc.
        """
        self._action_to_direction = {
            0: np.array([1, 0]),
            1: np.array([0, 1]),
            2: np.array([-1, 0]),
            3: np.array([0, -1]),
        }

        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

        """
        If human-rendering is used, `self.window` will be a reference
        to the window that we draw to. `self.clock` will be a clock that is used
        to ensure that the environment is rendered at the correct framerate in
        human-mode. They will remain `None` until human-mode is used for the
        first time.
        """
        self.window = None
        self.clock = None

    def _get_obs(self):
        return {"agent": self._agent_location, "target": self._target_location}
    
    def _get_info(self):
        return {
            "distance": np.linalg.norm(
                self._agent_location - self._target_location, ord=1
            )
        }

    def reset(self, seed=None, options=None):
        # We need the following line to seed self.np_random
        super().reset(seed=seed)

        # Choose the agent's location uniformly at random
        self._agent_location = self.np_random.integers(0, self.size, size=2, dtype=int)

        # We will sample the target's location randomly until it does not coincide with the agent's location
        self._target_location = self._agent_location
        while np.array_equal(self._target_location, self._agent_location):
            self._target_location = self.np_random.integers(
                0, self.size, size=2, dtype=int
            )

        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame()

        return observation, info
    
    def step(self, action):
        # Map the action (element of {0,1,2,3}) to the direction we walk in
        direction = self._action_to_direction[action]
        # We use `np.clip` to make sure we don't leave the grid
        self._agent_location = np.clip(
            self._agent_location + direction, 0, self.size - 1
        )
        # An episode is done iff the agent has reached the target
        terminated = np.array_equal(self._agent_location, self._target_location)
        reward = 1 if terminated else 0  # Binary sparse rewards
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame()

        return observation, reward, terminated, False, info
    
    def render(self):
        if self.render_mode == "rgb_array":
            return self._render_frame()

    def _render_frame(self):
        if self.window is None and self.render_mode == "human":
            pygame.init()
            pygame.display.init()
            self.window = pygame.display.set_mode(
                (self.window_size, self.window_size)
            )
        if self.clock is None and self.render_mode == "human":
            self.clock = pygame.time.Clock()

        canvas = pygame.Surface((self.window_size, self.window_size))
        canvas.fill((255, 255, 255))
        pix_square_size = (
            self.window_size / self.size
        )  # The size of a single grid square in pixels

        # First we draw the target
        pygame.draw.rect(
            canvas,
            (255, 0, 0),
            pygame.Rect(
                pix_square_size * self._target_location,
                (pix_square_size, pix_square_size),
            ),
        )
        # Now we draw the agent
        pygame.draw.circle(
            canvas,
            (0, 0, 255),
            (self._agent_location + 0.5) * pix_square_size,
            pix_square_size / 3,
        )

        # Finally, add some gridlines
        for x in range(self.size + 1):
            pygame.draw.line(
                canvas,
                0,
                (0, pix_square_size * x),
                (self.window_size, pix_square_size * x),
                width=3,
            )
            pygame.draw.line(
                canvas,
                0,
                (pix_square_size * x, 0),
                (pix_square_size * x, self.window_size),
                width=3,
            )

        if self.render_mode == "human":
            # The following line copies our drawings from `canvas` to the visible window
            self.window.blit(canvas, canvas.get_rect())
            pygame.event.pump()
            pygame.display.update()

            # We need to ensure that human-rendering occurs at the predefined framerate.
            # The following line will automatically add a delay to keep the framerate stable.
            self.clock.tick(self.metadata["render_fps"])
        else:  # rgb_array
            return np.transpose(
                np.array(pygame.surfarray.pixels3d(canvas)), axes=(1, 0, 2)
            )
        
    def close(self):
        if self.window is not None:
            pygame.display.quit()
            pygame.quit()