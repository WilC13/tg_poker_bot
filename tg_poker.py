from telegram.ext import *
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, Update
import requests, random, itertools
from pokereval.card import Card
from pokereval.hand_evaluator import HandEvaluator
import logging, datetime

d = datetime.datetime.now()
d = d.strftime("%m_%d_%H_%M")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename=f"poker_{d}.txt",
)
logger = logging.getLogger(__name__)

# #test
# API_KEY = "5740654668:AAFlpQVzhuNZWiUdgXEbJrxGVwHI_r4OgxA"
# wc
API_KEY = "5724731969:AAED8gEx6KYkG8EObo_EMw2EgmheOLxIMzU"

bot = Bot(API_KEY)

MAX_PLAYER = 6

cur_option_pos = 1
sb_pos = 0
bb_pos = 0

chat_id = None

# did utg do first action
# bb_actioned = False

PREFLOP, OPTION, BET = "PREFLOP", "OPTION", "Bet"

print("Bot started...")
print(bot.get_me())


class poker_game:
    def __init__(self, sb=50, bb=100) -> None:

        self.a = ["♠️", "♣️", "♥️", "♦️"]
        self.b = [2, 3, 4, 5, 6, 7, 8, 9, 10, "J", "Q", "K", "A"]

        self.desk = []
        self.deck = list(itertools.product(self.a, self.b))

        self.sb = sb
        self.bb = bb

        self.cur_button = 1
        # +1 after check winner or active player == 1

        self.pre_flop_stage = False
        self.flop_stage = False
        self.turn_stage = False
        self.river_stage = False

        self.active_player = []

        self.pot = 0
        self.side_pot = 0
        self.cur_max_bet = bb

    def game_start(self):
        random.shuffle(self.deck)

    def reset(self):
        self.desk = []
        self.deck = list(itertools.product(self.a, self.b))
        self.pre_flop_stage = False
        self.flop_stage = False
        self.turn_stage = False
        self.river_stage = False

    def player_hand(self):
        return self.deck.pop()

    def flop(self):
        for _ in range(3):
            self.desk.append(self.deck.pop())
        self.flop_stage = True

    def turn(self):
        self.desk.append(self.deck.pop())
        self.turn_stage = True

    def river(self):
        self.desk.append(self.deck.pop())
        self.river_stage = True


class player:
    def __init__(self, id, name, cash) -> None:
        self.id = id
        self.name = name
        self.cash = cash
        self.card = []
        self.active = True  # No more money
        self.cur_bet = 0

        # for winner check
        self.formated_card = None
        self.score = 0

    def trans(self, card: list) -> list:
        temp = []
        for i in range(len(card)):
            s, n = 0, 0
            if card[i][0] == "♠️":  # 1
                s = 1
            elif card[i][0] == "♣️":  # 2
                s = 2
            elif card[i][0] == "♥️":  # 3
                s = 3
            elif card[i][0] == "♦️":  # 4
                s = 4

            if card[i][1] == "A":  # 14
                n = 14
            elif card[i][1] == "K":  # 13
                n = 13
            elif card[i][1] == "Q":  # 12
                n = 12
            elif card[i][1] == "J":  # 11
                n = 11
            else:
                n = card[i][1]
            temp.append(Card(n, s))
        return temp

    def format_card(self):
        self.formated_card = self.trans(self.card)

    def cal_score(self, board: list):
        self.format_card()
        formated_board = self.trans(board)
        self.score = HandEvaluator.evaluate_hand(self.formated_card, formated_board)
        return self.score


player_pool = dict()

game = poker_game()


def poker(update: Update, context: CallbackContext):
    global game, player_pool
    # SB BB
    game = poker_game()
    game.game_start()
    temp = update.message.text[6:]
    temp = temp.split()
    l = len(temp)
    if l > 0:
        if l == 2 and temp[0].isdigit() and temp[1].isdigit():
            game.sb = temp[0]
            game.bb = temp[1]
        else:
            update.message.reply_text("Must have two Blind\n e.g. /poker 50 100")
            return None

    game.game_start()
    player_pool = dict()

    kb = [
        [
            InlineKeyboardButton("Buy in 100BB", callback_data="100BB"),
            InlineKeyboardButton("Buy in 200BB", callback_data="200BB"),
        ],
    ]
    markup = InlineKeyboardMarkup(kb)
    # update.message.reply_text('Game Start\n/join (buy in) e.g. /join 500')
    update.message.reply_text(text="Game Start", reply_markup=markup)

    return OPTION


def join(update: Update, context: CallbackContext):
    global player_pool
    if len(player_pool) < MAX_PLAYER:
        user = update.message.from_user
        player_id = user["id"]
        player_name = "@" + user["username"]
        player_cash = 0
        if len(update.message.text) == 5:
            player_cash = game.bb * 100
        else:
            temp = update.message.text[6:].split()[0]
            if temp.isdigit():
                player_cash = int(update.message.text[6:])
                if player_cash < game.bb * 100:
                    update.message.reply_text(f"At least {game.bb *100}")
                    return None
            else:
                update.message.reply_text("buy in must be number")

        player_pos = len(player_pool) + 1
        player_pool[player_pos] = player(player_id, player_name, player_cash)
        update.message.reply_text(player_list())
    else:
        update.message.reply_text("Full\n", player_list())


def pre_flop(update: Update, context: CallbackContext):
    global game, cur_option_pos, sb_pos, bb_pos, player_pool

    if game.pre_flop_stage == True:
        game.reset()
        game.game_start()
        for k, v in player_pool.items():
            v.card = []
            v.formated_card = None
            v.score = 0

    game.pre_flop_stage = True

    game.active_player = [False for _ in range(len(player_pool))]

    context.bot.send_message(chat_id=chat_id, text=f"Pre Flop")

    for i in range(1, len(player_pool) + 1):
        for _ in range(2):
            player_pool[i].card.append(game.player_hand())
        send(player_pool[i].id, str(player_pool[i].card))

    def _next(but, len=len(player_pool)):
        return but % len if but > len else but

    print("player_pool", player_pool)
    print("sb_pos", sb_pos)
    print("bb_pos", bb_pos)

    sb_pos = _next((game.cur_button + 1))
    bb_pos = _next((game.cur_button + 2))

    player_pool[sb_pos].cash -= game.sb
    player_pool[sb_pos].cur_bet = game.sb

    player_pool[bb_pos].cash -= game.bb
    player_pool[bb_pos].cur_bet = game.bb

    game.cur_max_bet = game.bb

    game.pot = game.pot + game.sb + game.bb

    try:

        context.bot.send_message(
            chat_id=chat_id,
            text=f"seat {sb_pos}: {player_pool[sb_pos].name} SB: {game.sb}\nseat {bb_pos}: {player_pool[bb_pos].name} BB: {game.bb}",
        )
    except:
        pass
    cur_option_pos = _next(bb_pos + 1)
    print("pre cur pos", cur_option_pos)
    print("preact", game.active_player)
    option(update, context)
    return OPTION


def flop(update: Update, context: CallbackContext):
    global game, cur_option_pos
    game.flop_stage = True

    reset_player_pot()
    context.bot.send_message(chat_id=chat_id, text=f"Flop")
    game.flop()
    context.bot.send_message(chat_id=chat_id, text=f"{game.desk}")
    cur_option_pos = sb_pos
    reactive_player(False)
    option(update, context)


def turn(update: Update, context: CallbackContext):
    global game, cur_option_pos
    game.turn_stage = True

    reset_player_pot()
    context.bot.send_message(chat_id=chat_id, text=f"Turn")
    game.turn()
    context.bot.send_message(chat_id=chat_id, text=f"{game.desk}")
    cur_option_pos = sb_pos
    reactive_player(False)
    option(update, context)


def river(update: Update, context: CallbackContext):
    global game, cur_option_pos
    game.river_stage = True

    reset_player_pot()
    context.bot.send_message(chat_id=chat_id, text=f"River")
    game.river()
    context.bot.send_message(chat_id=chat_id, text=f"{game.desk}")
    cur_option_pos = sb_pos
    reactive_player(False)
    option(update, context)


def option(update: Update, context: CallbackContext):
    print("option")
    global chat_id, game

    kb_setting = None
    full_option_kb = [
        [
            InlineKeyboardButton("Check", callback_data="Check"),
            InlineKeyboardButton("Call", callback_data="Call"),
            InlineKeyboardButton("Bet", callback_data="Bet"),
            InlineKeyboardButton("Fold", callback_data="Fold"),
        ],
    ]

    no_call_option_kb = [
        [
            InlineKeyboardButton("Check", callback_data="Check"),
            InlineKeyboardButton("Bet", callback_data="Bet"),
            InlineKeyboardButton("Fold", callback_data="Fold"),
        ],
    ]
    no_check_option_kb = [
        [
            InlineKeyboardButton("Call", callback_data="Call"),
            InlineKeyboardButton("Bet", callback_data="Bet"),
            InlineKeyboardButton("Fold", callback_data="Fold"),
        ],
    ]

    if player_pool[cur_option_pos].cur_bet == game.cur_max_bet:
        kb_setting = no_call_option_kb
    elif player_pool[cur_option_pos].cur_bet < game.cur_max_bet:
        kb_setting = no_check_option_kb
    else:
        kb_setting = full_option_kb

    markup = InlineKeyboardMarkup(kb_setting)
    print("False count ", game.active_player.count(False))

    # All other player fold
    if check_winner(update, context):
        # pre_flop(update, context)
        return
    else:
        if game.active_player.count(False) == 0:
            return

        else:
            while game.active_player[cur_option_pos - 1] == None:
                next_pos()
            tocall = (
                f" To Call: {game.cur_max_bet}"
                if game.cur_max_bet > player_pool[cur_option_pos].cur_bet
                else ""
            )
            context.bot.send_message(
                chat_id=chat_id,
                text=f"Seat {cur_option_pos} {player_pool[cur_option_pos].name} Cash: {player_pool[cur_option_pos].cash} Cur Bet: {player_pool[cur_option_pos].cur_bet}\nPot: {game.pot}{tocall}",
                reply_markup=markup,
            )
            print("option sent")


# options func
def actioned(arg):
    def act():
        global game, cur_option_pos
        game.active_player[cur_option_pos - 1] = True
        arg()

    return act


@actioned
def check():
    pass


@actioned
def call():
    global game, cur_option_pos

    temp = 0
    bet = 0

    # raised before
    if player_pool[cur_option_pos].cash > 0:
        temp = player_pool[cur_option_pos].cur_bet
        bet = game.cur_max_bet - temp  # last turn bet

        player_pool[cur_option_pos].cash -= bet
        player_pool[cur_option_pos].cur_bet = game.cur_max_bet
        game.pot += bet

    else:
        player_pool[cur_option_pos].cash -= game.cur_max_bet
        player_pool[cur_option_pos].cur_bet = game.cur_max_bet

        game.pot += game.cur_max_bet

    print(
        player_pool[cur_option_pos].cash,
        player_pool[cur_option_pos].cur_bet,
        game.cur_max_bet,
    )


# @actioned
def fold(update, context):
    game.active_player[cur_option_pos - 1] = None


# sup func
def check_winner(update: Update, context: CallbackContext) -> bool:
    print("check winner")

    if game.active_player.count(None) == len(game.active_player) - 1:  # All fold
        # for player_pool: dict()
        winner_pos = 0
        try:
            winner_pos = game.active_player.index(True) + 1
        except:
            winner_pos = game.active_player.index(False) + 1

        player_pool[winner_pos].cash += game.pot
        context.bot.send_message(
            chat_id=chat_id,
            text=f"{player_pool[winner_pos].name} Won ${game.pot} Cash: {player_pool[winner_pos].cash}\nNext Game: /pre",
        )
        game.pot = 0

        def _next(but, len=len(player_pool)):
            return but % len if but > len else but

        print("cw _next", _next((game.cur_button + 1)))
        game.cur_button = _next((game.cur_button + 1))
        print("cw game.cur_button", game.cur_button)

        return True

    # After River
    if game.river_stage == True and game.pot > game.sb + game.bb:
        if len(game.desk) != 5:
            return None
        winner_list = []  # maybe more than one
        for i in range(1, len(player_pool) + 1):
            if game.active_player[i - 1] == None:
                player_pool[i].score = 0
            else:
                player_pool[i].cal_score(game.desk)  # count all player
        highest = max(i.score for k, i in player_pool.items())
        for k, v in player_pool.items():
            if v.score == highest:
                winner_list.append(k)  # produce winner

        player_card_list = ""
        for k, v in player_pool.items():
            if v.score > 0:
                player_card_list += f"Seat {k} {v.name}: {v.card}\n"
        context.bot.send_message(
            chat_id=chat_id,
            text=player_card_list,
        )
        prize = game.pot / len(winner_list)  # if spilt
        for i in winner_list:
            player_pool[i].cash += prize
            context.bot.send_message(
                chat_id=chat_id,
                text=f"{player_pool[i].name} Won ${prize} Cash: {player_pool[i].cash}\nNext Game: /pre",
            )

        game.pot = 0

        def _next(but, len=len(player_pool)):
            return but % len if but > len else but

        game.cur_button = _next((game.cur_button + 1))

        return True


def next_pos():
    global cur_option_pos, game
    cur_option_pos = (
        (cur_option_pos + 1) % len(player_pool)
        if (cur_option_pos + 1) > len(player_pool)
        else cur_option_pos + 1
    )


def player_list() -> str:
    global game
    min_max = f"  Min: 3  Max: {MAX_PLAYER}" if game.flop_stage == False else ""
    temp = "when ready   /pre" if game.flop_stage == False else ""
    st = f"Player List:{min_max}\n"
    for i in range(1, len(player_pool) + 1):
        st += f"Seat {i}: {player_pool[i].name} Cash: {player_pool[i].cash}\n"
    st += temp
    return st


def reactive_player(cur_included=True):
    global game
    for i in range(len(game.active_player)):
        if game.active_player[i] == None:
            continue
        elif game.active_player[i] == True:
            game.active_player[i] = False
    game.active_player[cur_option_pos - 1] = cur_included
    print("player reactive", game.active_player)


def reset_player_pot():
    for i in range(1, len(player_pool) + 1):
        player_pool[i].cur_bet = 0
    game.cur_max_bet = 0


def error(update: Update, context: CallbackContext):
    global chat_id
    chat_id = update.callback_query.message.chat_id
    print(f"Update {update} caused error {context.error}")
    context.bot.send_message(chat_id=chat_id, text="Something wrong, try again")


def send(id, text):
    url = f"https://api.telegram.org/bot{API_KEY}/sendMessage"
    params = {
        "chat_id": id,
        "text": f"You got {text}",
    }
    resp = requests.get(url, params=params)


def callback_handler(update: Update, context: CallbackContext):
    print("preflop handler")
    global player_pool, chat_id, game

    query = update.callback_query.data
    update.callback_query.answer()
    player_id = update.callback_query.from_user.id
    player_name = update.callback_query.from_user.name
    chat_id = update.callback_query.message.chat_id

    if "100BB" in query or "200BB" in query:
        if len(player_pool) < MAX_PLAYER:
            player_cash = 0
            if "100BB" in query:
                player_cash = game.bb * 100
            if "200BB" in query:
                player_cash = game.bb * 200
            player_pos = len(player_pool) + 1
            player_pool[player_pos] = player(player_id, player_name, player_cash)
            # for _ in range(2):
            #     player_pool[player_pos].card.append(game.player_hand())
            # send(player_id, str(player_pool[player_pos].card))

            context.bot.send_message(chat_id=chat_id, text=player_list())
        else:
            context.bot.send_message(chat_id=chat_id, text=f"Full\n {player_list()}")

    print("query ", query)

    if "Check" in query or "Call" in query or "Bet" in query or "Fold" in query:
        game.active_player[cur_option_pos - 1] = (
            True
            if game.active_player[cur_option_pos - 1] != None
            else game.active_player[cur_option_pos - 1]
        )

        opt = None

        if "Check" in query:
            opt = "Check"
            check()
        if "Call" in query:
            # game.active_player[cur_option_pos-1] = True
            call()

            opt = f"Call {game.cur_max_bet}"

            # player_pool[cur_option_pos].cash -= game.cur_max_bet
            # player_pool[cur_option_pos].cur_bet = game.cur_max_bet

            # game.pot += game.cur_max_bet

            # print(player_pool[cur_option_pos].cash, player_pool[cur_option_pos].cur_bet, game.cur_max_bet)
        if "Bet" in query:
            kb_bb_bet = [
                [
                    InlineKeyboardButton("2BB", callback_data="2BB"),
                    InlineKeyboardButton("3BB", callback_data="3BB"),
                    InlineKeyboardButton("5BB", callback_data="5BB"),
                ],
            ]
            kb_bet = [
                [
                    InlineKeyboardButton(f"{game.pot*0.33}", callback_data="33P"),
                    InlineKeyboardButton(f"{game.pot*0.5}", callback_data="50P"),
                    InlineKeyboardButton(f"{game.pot*0.75}", callback_data="75P"),
                    InlineKeyboardButton(f"{game.pot}", callback_data="100P"),
                ],
                [
                    InlineKeyboardButton(
                        f"All in: {player_pool[cur_option_pos].cash}",
                        callback_data="allin",
                    )
                ],
            ]
            kb = (
                kb_bb_bet
                if game.cur_max_bet == game.bb and game.pre_flop_stage == True
                else kb_bet
            )
            markup = InlineKeyboardMarkup(kb)
            update.callback_query.edit_message_text("How much?", reply_markup=markup)
            print("BET returned")
            return BET
            # return None
        if "Fold" in query:
            opt = "Fold"
            fold(update, context)

        update.callback_query.edit_message_text(
            f"Seat {cur_option_pos}: {player_pool[cur_option_pos].name} {opt} CASH:{player_pool[cur_option_pos].cash}\nPOT: {game.pot}"
        )

        next_pos()
        if game.active_player.count(False) != 0:
            option(update, context)

        if game.active_player.count(False) == 0:
            if (
                game.pre_flop_stage == True
                and game.flop_stage == True
                and game.turn_stage == True
                and game.river_stage == True
            ):
                check_winner(update, context)
            elif (
                game.pre_flop_stage == True
                and game.flop_stage == True
                and game.turn_stage == True
            ):
                river(update, context)
            elif game.pre_flop_stage == True and game.flop_stage == True:
                turn(update, context)
            elif game.pre_flop_stage == True:
                flop(update, context)

        print("act", game.active_player)

    return OPTION


def bet_handler(update: Update, context: CallbackContext):
    print("bet handler")

    global player_pool, chat_id, game

    query = update.callback_query.data

    bet = game.bb
    match query:
        case "2BB":
            bet *= 2
        case "3BB":
            bet *= 3
        case "5BB":
            bet *= 5
        case "33P":
            bet = game.pot * 0.33
        case "50P":
            bet = game.pot * 0.5
        case "75P":
            bet = game.pot * 0.75
        case "100P":
            bet = game.pot
        case "allin":
            bet = player_pool[cur_option_pos].cash + player_pool[cur_option_pos].cur_bet

    if player_pool[cur_option_pos].cash + player_pool[cur_option_pos].cur_bet < bet:
        context.bot.send_message(chat_id=chat_id, text="Not enought Cash")
        option(update, context)
        return

    game.cur_max_bet = bet

    # raised before
    if player_pool[cur_option_pos].cash > 0:
        bet -= player_pool[cur_option_pos].cur_bet  # last turn bet

    game.pot += bet
    player_pool[cur_option_pos].cash -= bet
    player_pool[cur_option_pos].cur_bet += bet
    reactive_player()

    update.callback_query.edit_message_text(
        f"seat {cur_option_pos}: {player_pool[cur_option_pos].name} BET: {bet} CASH:{player_pool[cur_option_pos].cash}\nPOT: {game.pot}"
    )
    next_pos()
    option(update, context)
    return OPTION


updater = Updater(API_KEY, use_context=True)
dp = updater.dispatcher

dp.add_handler(
    ConversationHandler(
        entry_points=[CommandHandler("poker", poker)],
        states={
            OPTION: [CallbackQueryHandler(callback_handler)],
            # OPTION:[CallbackQueryHandler(option_handler)],
            BET: [CallbackQueryHandler(bet_handler)],
        },
        fallbacks=[CommandHandler("poker", poker)],
        per_user=False,
    )
)

dp.add_handler(CommandHandler("pre", pre_flop))
# dp.add_handler(CommandHandler("join", join))
# dp.add_handler(CommandHandler("option", option))
dp.add_error_handler(error)
updater.start_polling()
updater.idle()
