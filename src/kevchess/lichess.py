import json
import os
import time

import berserk
import requests
from chess import STARTING_FEN, Board, Move
from mcts import Mcts
from node import Node

token = os.environ["LICHESS_BOT_TOKEN"]


def upgrade_to_bot(token: str):
    """
    Upgrade an account to a bot account
    """
    print(
        requests.post(
            "https://lichess.org/api/bot/account/upgrade",
            headers={"Authorization": f"Bearer {token}"},
        ).text
    )


def get_move(old_node: Node, new_node: Node) -> str:
    """
    Get the UCI of a move given an old and new state
    """
    old_board = Board(fen=old_node.fen)
    for move in old_board.legal_moves:
        temp_board = Board(fen=old_node.fen)
        temp_board.push(move)
        if temp_board.fen() == new_node.fen:
            return move.uci()
    else:
        raise RuntimeError(
            "Trying to make illegal move! " f"{old_node.fen} -> {new_node.fen}"
        )


class Game:
    def __init__(self, client: berserk.Client, game_id, player_id, explore_weight=1.0):
        self.client = client

        self.game_id = game_id
        self.player_id = player_id
        self.explore_weight = explore_weight

        self.stream = client.bots.stream_game_state(game_id)

        game_info = next(self.stream)
        self.initial_fen = game_info["initialFen"]
        if self.initial_fen == "startpos":
            self.initial_fen = STARTING_FEN

        print("Initial FEN: ", self.initial_fen)

        self.tree = Mcts(explore_weight=self.explore_weight)
        self.node = Node(fen=self.initial_fen)
        self.turn_speed_seconds = 10  # TODO

        self.my_turn = game_info["white"]["id"] == self.player_id
        if self.my_turn:
            self.make_move()

        # self.turn_speed = self.initial_state["clock"]["increment"]

    def run(self):
        for event in self.stream:
            print("Got event: ", event)
            if event["type"] == "gameState":
                self.handle_state_change(event)
            elif event["type"] == "chatLine":
                self.handle_chat_line(event)

    def make_move(self):
        start = time.time()
        print("Thinking...")
        think_count = 0
        while time.time() - start < self.turn_speed_seconds:
            self.tree.rollout(self.node)
            think_count += 1
        print(f"Thought of {think_count} moves")

        new_node = self.tree.choose(self.node)
        print(f"Move score: : {self.tree.rewards[new_node]}/{self.tree.visit_count[new_node]}")

        # Make the selected move
        move_str = get_move(self.node, new_node)
        print("Making move", move_str)
        self.client.bots.make_move(self.game_id, move_str)

        self.node = new_node

    def handle_state_change(self, event):
        board = Board(fen=self.initial_fen)
        for move in event["moves"].split():
            board.push(Move.from_uci(move))
        self.node = Node(fen=board.fen())
        self.my_turn = not self.my_turn

        print(f"My turn? {self.my_turn}")

        if self.my_turn:
            self.make_move()

    def handle_chat_line(self, event):
        print(event)


def accept_challenge(event) -> bool:
    return event["challenge"]["challenger"]["id"] == "k2bd"


if __name__ == "__main__":
    session = berserk.TokenSession(token)
    client = berserk.Client(session)

    my_profile = client.account.get()
    my_id = my_profile["id"]

    is_polite = True
    for event in client.bots.stream_incoming_events():
        print(json.dumps(event, indent=2))
        if event["type"] == "challenge":
            if accept_challenge(event):
                client.bots.accept_challenge(event["challenge"]["id"])
            elif is_polite:
                client.bots.decline_challenge(event["challenge"]["id"])
        elif event["type"] == "gameStart":
            game = Game(client, event["game"]["id"], player_id=my_id)
            game.run()
