from flask import Flask, Response, render_template, request
from flask_babel import Babel, gettext
from flask_caching import Cache
import uuid
import random
import collections
import json
import os
import copy

app = Flask(__name__)
babel = Babel(app) # Babelオブジェクトを作っておく


@babel.localeselector
def get_locale():
    # この場合はブラウザのAccept Languagesを見るようになっている。
    return request.accept_languages.best_match(['ja', 'ja_JP', 'en'])


'''
# TODO:
- To understand the victory or defeat
- Reuse of exists cards

カード枚数：35枚
14種類
　20     0
　15x2   1-2
　10x3   3-5
　5x4    6-9
　4x4    10-13
　3x4    14-17
　2x4    18-21
　1x4    22-25
　0x4    26-29
　-5x2   30-31
　-10    32
　x2     33
　MAX→0  34
　?（今回は対応しない）
'''
cardnames = [20, 15, 15, 10, 10, 10, 5, 5, 5, 5
 ,4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2
 ,1, 1, 1, 1, 0, 0, 0, 0, -5, -5, -10
 , 'x2', 'MAX→0']


# Cacheインスタンスの作成
cache = Cache(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.environ.get('REDIS_URL', 'redis://localhost:6379'),
    'CACHE_DEFAULT_TIMEOUT': 60 * 60 * 2,
})


@app.route('/')
def homepage():
    return render_template('index.html')


# create the game group
@app.route('/create/<nickname>')
def create_game(nickname):
    game = {
        'status': 'waiting',
        'routeidx': 0,
        'stocks': list(range(0, 35)),
        'coyote': False,
        'score': 0,
        'cardnames': cardnames,
        'players': []}
    player = {}

    gameid = str(uuid.uuid4())
    game['gameid'] = gameid
    player['playerid'] = gameid
    player['nickname'] = nickname
    player['holdcard'] = 0
    game['players'].append(player)

    app.logger.debug(gameid)
    app.logger.debug(game)
    cache.set(gameid, game)
    return gameid


# re:wait the game
@app.route('/<gameid>/waiting')
def waiting_game(gameid):
    game = cache.get(gameid)
    game['status'] = 'waiting'
    cache.set(gameid, game)
    return 'reset game status'


# join the game
@app.route('/<gameid>/join')
@app.route('/<gameid>/join/<nickname>')
def join_game(gameid, nickname='default'):
    game = cache.get(gameid)
    if game['status'] == 'waiting':
        player = {}

        playerid = str(uuid.uuid4())
        player['playerid'] = playerid
        if nickname == 'default':
            player['nickname'] = playerid
        else:
            player['nickname'] = nickname
        player['holdcard'] = 0
        game['players'].append(player)

        cache.set(gameid, game)
        return playerid + ' ,' + player['nickname'] + ' ,' + game['status']
    else:
        return 'Already started'


# processing the game
@app.route('/<gameid>/start')
def start_game(gameid):
    game = cache.get(gameid)
    game['status'] = 'started'
    game['answer'] = 0
    game_score_list = []
    tmp = []
    game_score = 0

    # playerids = [player['playerid'] for player in game['players']]
    routelist = copy.copy(game['players'])
    random.shuffle(routelist)
    game['routelist'] = routelist

    players = game['players']

    for player in players:
        if len(game['stocks']) == 0:
            # if count of all cards is not enogh less than count of players, there has to be refill it.
            game['stocks'] = list(range(0, 35))
        score = game['stocks'].pop(random.randint(0, len(game['stocks']) - 1))
        game_score_list.append(cardnames[score])
        player['holdcard'] = score
        player['lose'] = False

    # make numeric list for calculate score
    tmp = [i for i in game_score_list if type(i) is int]

    if 'MAX→0' in game_score_list:
        max_list = [i for i, v in enumerate(tmp) if v == max(tmp)]
        for i in max_list:
            tmp[i] = 0
        game_score_list.pop(game_score_list.index('MAX→0'))

    game_score = sum(tmp)

    if 'x2' in game_score_list:
        game_score *= 2

    game['score'] = game_score

    cache.set(gameid, game)
    return json.dumps(game['routelist'])


# set the card on the line
@app.route('/<gameid>/<clientid>/set/<int:answer>')
def setcard_game(gameid, clientid, answer):
    game = cache.get(gameid)

    game['answer'] = answer
    game['routeidx'] = (game['routeidx'] + 1) % len(game['players'])

    cache.set(gameid, game)
    return 'ok'


# coyote
@app.route('/<gameid>/<clientid>/coyote')
def coyote(gameid, clientid):
    game = cache.get(gameid)

    game['status'] = 'end'
    game['coyote'] = True

    # logic of calculate numbers
    print(clientid)
    if game['score'] < game['answer']:
        game['players'][game['routeidx']-2]['lose'] = True
    else:
        player = [_player for _player in game['players'] if _player['playerid'] == clientid][0]
        player['lose'] = True

    cache.set(gameid, game)
    return 'ok'


# all status the game
@app.route('/<gameid>/status')
def game_status(gameid):
    game = cache.get(gameid)

    return json.dumps(game)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
