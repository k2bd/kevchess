from __future__ import annotations

from chess import Board, Outcome
from dataclasses import dataclass
from typing import FrozenSet, Optional
import random
from functools import lru_cache


@lru_cache()
def children(fen: str) -> FrozenSet[Node]:
    """
    Get children of a given game state
    """
    board = Board(fen=fen)
    next_moves = []
    for move in board.legal_moves:
        new_board = Board(fen=fen)
        new_board.push(move)
        next_moves.append(Node(fen=new_board.fen()))
    return frozenset(next_moves)


@lru_cache()
def game_over(fen: str) -> bool:
    """
    Determine if the game is over and why
    """
    return Board(fen=fen).is_game_over()


@lru_cache()
def game_reward(fen: str) -> float:
    """
    Determine the reward of a finished game
    """
    # TODO: determine if a draw would be claimed
    board = Board(fen=fen)
    outcome: Outcome = board.outcome(claim_draw=False)
    if outcome.winner is None:
        # Draw
        return 0.5

    return 1.0 if outcome.winner == board.turn else 0.0


@dataclass(eq=True, frozen=True)
class Node:
    fen: str

    def find_children(self, random_seed=1) -> FrozenSet[Node]:
        """
        Get all valid moves
        """
        return children(self.fen)

    def find_random_child(self, seed: Optional[int] = None) -> Node:
        """
        Get a random move
        """
        random.seed(seed)
        selection, = random.sample(self.find_children(), 1)
        return selection

    def is_terminal(self) -> bool:
        """
        Return whether the game is over at this point
        """
        return game_over(self.fen)

    def reward(self) -> float:
        """
        Get the flaot reward of a terminal game state.

        Returns 1.0 if the turn player wins, 0.0 if the turn player loses,
        or somewhere in the middle otherwise.
        """
        return game_reward(self.fen)
