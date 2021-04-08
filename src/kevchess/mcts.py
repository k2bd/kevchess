import math
from collections import defaultdict
from typing import Dict, List, Set

from node import Node


class Mcts:
    """
    A basic implementation of MCTS
    Based on https://gist.github.com/qpwo/c538c6f73727e254fdc7fab81024f6e1
    """

    def __init__(self, explore_weight: int = 1.0):
        self.rewards: Dict[Node, int] = defaultdict(int)

        self.visit_count: Dict[Node, int] = defaultdict(int)

        self.children: Dict[Node, Set[Node]] = dict()

        self.explore_weight = explore_weight

    def score(self, node: Node) -> float:
        """ Get the score of a node """
        if self.visit_count[node] == 0:
            return float("-inf")
        return self.rewards[node] / self.visit_count[node]

    def choose(self, node: Node) -> Node:
        """Choose a new move in a game from a given node"""
        if node.is_terminal():
            print("Terminal node issue!")
            print("Node: ", node)
            print("Children: ", node.find_children())
            raise RuntimeError("Cannot move from a terminal node")

        if node not in self.children:
            return node.find_random_child()

        return max(self.children[node], key=self.score)

    def rollout(self, node: Node):
        """ Iteration of learning """
        path = self._select(node)
        leaf = path[-1]
        self._expand(leaf)
        reward = self._simulate(leaf)
        self._backpropagate(path, reward)

    def _select(self, node: Node) -> List[Node]:
        path = []
        while True:
            path.append(node)
            if node not in self.children or not self.children[node]:
                # Unexplored or terminal node
                return path
            unexplored = self.children[node] - self.children.keys()
            if unexplored:
                n = unexplored.pop()
                path.append(n)
                return path
            node = self._uct_select(node)  # Go one layer deeper

    def _expand(self, node: Node) -> None:
        if node in self.children:
            return
        self.children[node] = node.find_children()

    def _simulate(self, node: Node) -> float:
        invert_reward = True
        while True:
            if node.is_terminal():
                reward = node.reward()
                return 1 - reward if invert_reward else reward
            node = node.find_random_child()
            invert_reward = not invert_reward

    def _backpropagate(self, path: List[Node], reward: float) -> None:
        for node in path[::-1]:
            self.rewards[node] += reward
            self.visit_count[node] += 1
            reward = 1 - reward  # 1 is a win for me, 0 is a win for opponent, etc

    def _uct(self, log_visit: float, node: Node) -> float:
        """ Upper confidence bound """
        return self.rewards[node] / self.visit_count[
            node
        ] + self.explore_weight * math.sqrt(log_visit / self.visit_count[node])

    def _uct_select(self, node: Node) -> Node:
        """ Select a child of a node with an exploration/exploitation balance """
        if not all(n in self.children for n in self.children[node]):
            raise RuntimeError("UCT select on unexpanded node")

        log_visit = math.log(self.visit_count[node])
        return max(self.children[node], key=lambda n: self._uct(log_visit, n))
