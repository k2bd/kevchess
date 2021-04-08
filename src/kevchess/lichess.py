import os
import berserk
import json
import asyncio
import requests
from mcts import Mcts
from node import Node
from chess import Board, Move, STARTING_FEN
import aiohttp

token = os.environ["LICHESS_BOT_TOKEN"]


def upgrade_to_bot(token: str):
    """
    Upgrade an account to a bot account
    """
    print(requests.post(
        "https://lichess.org/api/bot/account/upgrade",
        headers={"Authorization": f"Bearer {token}"}
    ).text)


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
            "Trying to make illegal move! "
            f"{old_node.fen} -> {new_node.fen}"
        )


class Game:
    def __init__(self, game_id, player_id, explore_weight=1.0):
        self.game_id = game_id
        self.player_id = player_id
        self.explore_weight = explore_weight

        self.playing = False

    def start(self, loop=None):
        loop = loop or asyncio.get_event_loop()

        self.session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {token}"})

        self.learn_task = loop.create_task(self.learn())
        self.events_task = loop.create_task(self.handle_events())
        self.make_moves_task = loop.create_task(self.make_moves())

        print("Game started")

        loop.run_forever()  # For now, block and run through the whole game

    def stop(self):
        self.learn_task.cancel()
        self.events_task.cancel()
        self.make_moves_task.cancel()

    async def learn(self):
        while True:
            if self.playing:
                print("Learning!")
                self.tree.rollout(self.node)
            await asyncio.sleep(0)

    async def handle_events(self):
        async with self.session.get(f'https://lichess.org/api/bot/game/stream/{self.game_id}') as r:
            async for raw_event in r.content:
                event = json.loads(raw_event)
                print("Got event: ", event)
                if event['type'] == "gameFull":
                    self.handle_game_info()
                elif event['type'] == 'gameState':
                    self.handle_state_change(event)
                elif event['type'] == 'chatLine':
                    self.handle_chat_line(event)
                else:
                    raise RuntimeError(f"Invalid event: {event}")
                await asyncio.sleep(0)

    async def make_moves(self) -> None:
        while True:
            if self.playing:
                new_node = self.tree.choose(self.node)

                # Make the selected move
                move_str = get_move(self.node, new_node)
                print("Making move", move_str)
                self.session.post(
                    f"https://lichess.org/api/bot/game/{self.game_id}/move/{move_str}"
                )

                self.node = new_node
                self.my_turn = not self.my_turn
            await asyncio.sleep(0)

    def handle_game_info(self, event):
        self.initial_fen = event["initialFen"]
        if self.initial_fen == "startpos":
            self.initial_fen = STARTING_FEN

        print("Initial FEN: ", self.initial_fen)

        self.tree = Mcts(explore_weight=self.explore_weight)
        self.node = Node(fen=self.initial_fen)

        self.my_turn = event["white"]["id"] == self.player_id

        self.turn_speed = 10
        #self.turn_speed = self.initial_state["clock"]["increment"]

        self.playing = True

    def handle_state_change(self, game_state):
        board = Board(fen=self.initial_fen)
        for move in game_state["moves"].split():
            board.push(Move.from_uci(move))
        self.node = Node(fen=board.fen())

        print("My turn?", self.my_turn)

        if self.my_turn:
            self.make_move()
        else:
            self.my_turn = not self.my_turn

    def handle_chat_line(self, chat_line):
        print(chat_line)


def accept_challenge(event) -> bool:
    return event["challenge"]['challenger']["id"] == "k2bd"


if __name__ == "__main__":
    session = berserk.TokenSession(token)
    client = berserk.Client(session)

    my_profile = client.account.get()
    my_id = my_profile["id"]

    is_polite = True
    for event in client.bots.stream_incoming_events():
        print(json.dumps(event, indent=2))
        if event['type'] == 'challenge':
            if accept_challenge(event):
                client.bots.accept_challenge(event["challenge"]['id'])
            elif is_polite:
                client.bots.decline_challenge(event["challenge"]['id'])
        elif event['type'] == 'gameStart':
            game = Game(event["game"]['id'], player_id=my_id)
            game.start()
