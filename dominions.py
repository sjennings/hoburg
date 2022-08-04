# Library for dealing with Dominions 5 games.
# Adapted from Dominions 5 Slackbot: https://github.com/stvnksslr/dominions-bot

# TODO: support direct connections instead of just relying on snek.earth API
# Basic framework for this is here already, just needs some work.
# (and may not be necessary since, well, everyone uses snek.earth for hosting)

import json
import requests
from dataclasses import dataclass
from enum import Enum
from struct import pack, unpack
from socket import socket
from zlib import decompress


class Era(Enum):
    Early_Age = 0
    Middle_Age = 1
    Late_Age = 2


class NationType(Enum):
    Empty = 0
    Human = 1
    Bot = 2
    Independent = 3
    Closed = 253
    Defeated_this_turn = 254
    Defeated = 255
    eliminated_player = -1
    Defeated_Duplicate = -2


class TurnStatus(Enum):
    NotSubmitted = 0
    PartiallySubmitted = 1
    Submitted = 2


@dataclass
class GameStatus:
    name: str
    turn: str
    hours_remaining: str


@dataclass
class Game(object):
    server_id: int
    name: str
    turn: int
    players: list


PACKET_HEADER = "<ccLB"
PACKET_BYTES_PER_NATION = 3
PACKET_NUM_NATIONS = 250
PACKET_GENERAL_INFO = "<BBBBBB{0}sBBBBBBLB{1}BLLB"  # to use format later
PACKET_NATION_INFO_START = 15


def query(address, port):
    sck = socket()
    sck.settimeout(5.0)
    sck.connect((address, port))

    # request info
    pack_game_request = pack(
        "<ccssssccccccc",
        b"f",
        b"H",
        b"\a",
        b"\x00",
        b"\x00",
        b"\x00",
        b"=",
        b"\x1e",
        b"\x02",
        b"\x11",
        b"E",
        b"\x05",
        b"\x00",
    )
    sck.send(pack_game_request)
    result = sck.recv(512)

    # close connection
    sck.send(pack(PACKET_HEADER, b"f", b"H", 1, 11))
    sck.close()

    header = unpack(PACKET_HEADER, result[0:7])
    compressed = header[1] == b"J"

    if compressed:
        data = decompress(result[10:])
    else:
        data = result[10:]

    game_name_length = (
        len(data)
        - len(PACKET_GENERAL_INFO.format("", ""))
        - PACKET_BYTES_PER_NATION * PACKET_NUM_NATIONS
        - 6
    )

    data_array = unpack(
        PACKET_GENERAL_INFO.format(
            game_name_length, PACKET_BYTES_PER_NATION * PACKET_NUM_NATIONS
        ),
        data,
    )
    hours_remaining = round(data_array[13] / (1000 * 60 * 60), 2)

    return GameStatus(
        name=data_array[6].decode().rstrip("\x00"),
        turn=data_array[-3],
        hours_remaining=hours_remaining,
    )


def get_game_details(port):
    game_id = port[1:]
    game_status = get_game_status(game_id)
    player_status = get_player_status(game_id)

    return {"game_status": game_status, "player_status": player_status}


def fetch_game(server_address):
    game_id = server_address.replace("snek.earth:", "")

    game_detail = get_game_details(game_id)
    game_status = game_detail.get("game_status")
    player_status = game_detail.get("player_status")

    new_game = Game(
        server_id=game_id,
        name=game_status.name,
        turn=int(game_status.turn),
        players=player_status,
    )

    return new_game


def create_player_blocks(players):
    player_blocks = []

    for player in players.get("player_status"):
        nation_name = player.get("nation_name")
        turn_status = player.get("nation_turn_status")
        player_type = player.get("nation_controller")

        if player_type == "Bot":
            turn_status_emoji = ":robot_face:"
        elif (
            player_type == "eliminated_player"
            or player_type == "Defeated_Duplicate"
            or player_type == "Defeated_this_turn"
            or player_type == "Defeated"
        ):
            turn_status_emoji = ":skull:"
        elif turn_status == "NotSubmitted":
            turn_status_emoji = ":x:"
        elif turn_status == "PartiallySubmitted":
            turn_status_emoji = ":question:"
        else:
            turn_status_emoji = ":white_check_mark:"

        nation_section = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f" {turn_status_emoji} *{nation_name}*"},
        }

        player_blocks.append(nation_section)
    return player_blocks


def pull_game_details(game):
    game_name, turn, raw_player_blocks, remaining_time = fetch_game_details(game)

    formatted_msg = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Dominions Times"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": " :freak_lord: *Update* :freak_lord:",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{game_name} Turn: {turn}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Remaining Hours: {remaining_time}"},
        },
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Player List*"}},
    ]
    test_list = formatted_msg + raw_player_blocks

    return test_list


def fetch_game_details(game):
    # https://snek.earth/api/games/1626
    game_details = get_game_details(game)

    game_name = game_details.get("game_status").name
    turn = game_details.get("game_status").turn
    remaining_time = game_details.get("game_status").hours_remaining
    raw_player_blocks = create_player_blocks(game_details)
    return game_name, turn, raw_player_blocks, remaining_time


def get_game_status(game_id):
    game_status = json.loads(
        requests.get("https://dom5.snek.earth/api/games/{}".format(game_id)).content
    )
    game_name = game_status["name"]

    raw_game_info = query(address="snek.earth", port=int(f"3{game_id}"))
    return GameStatus(
        name=game_name,
        turn=raw_game_info.turn,
        hours_remaining=raw_game_info.hours_remaining,
    )


def get_player_status(game_id):
    player_status = json.loads(
        requests.get(
            "https://dom5.snek.earth/api/games/{}/status".format(game_id)
        ).content
    )

    player_list = []
    player_nations = player_status["nations"]
    for nation in player_nations:
        nation_id = nation["nationid"]
        nation_name = nation["name"]
        nation_epithet = nation["epithet"]
        nation_controller = NationType(int(nation["controller"])).name
        nation_turn_status = TurnStatus(int(nation["turnplayed"])).name

        nation_info = {
            "nation_name": nation_name,
            "nation_id": nation_id,
            "nation_epithet": nation_epithet,
            "nation_controller": nation_controller,
            "nation_turn_status": nation_turn_status,
        }

        player_list.append(nation_info)
    return player_list
