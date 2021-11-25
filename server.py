from flask import Flask, request, abort
from apscheduler.schedulers.background import BackgroundScheduler
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from collections import defaultdict

import datetime
import time
import yaml
import atexit
import requests
import validators
import random

userProductDic = defaultdict(list)
userProductDic.update(yaml.load(open('userProductDic.yml', 'rb')))

productUserDic = defaultdict(list)
productUserDic.update(yaml.load(open('productUserDic.yml', 'rb')))


def zero():
    return 0


productCountDic = defaultdict(zero)
productCountDic.update(yaml.load(open('productCountDic.yml', 'rb')))


def web_crawler():
    website = config["website"]["hk"]
    msg = config["empty_error_msg"]
    headers = {
        'authority': 'www.hermes.cn',
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Google Chrome";v="95", "Chromium";v="95", ";Not A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'accept-language': 'en-US,en;q=0.9'
    }

    for product in productUserDic:
        response = requests.get(f"{website}{product}", headers=headers)
        print(f"{datetime.datetime.now()}")
        if response.status_code != 200:
            time.sleep(random.randint(3, 20))
            continue

        if msg not in response:
            productCountDic[product] += 1
            if productCountDic[product] > 1:
                for users in productUserDic[product]:
                    line_bot_api.push_message(
                        users,
                        TextSendMessage(text=f"your product id:{product} is onboard, please check url: {website}{product}")
                    )
                    userProductDic[users].remove(product)
                productCountDic[product] = 1
                productUserDic[product] = []
        time.sleep(random.randint(3, 20))


def update_file():
    with open('userProductDic.yml', 'w') as outfile:
        yaml.dump(dict(userProductDic), outfile, default_flow_style=False)
    with open('productUserDic.yml', 'w') as outfile:
        yaml.dump(dict(productUserDic), outfile, default_flow_style=False)
    with open('productCountDic.yml', 'w') as outfile:
        yaml.dump(dict(productCountDic), outfile, default_flow_style=False)
    print("files updated")


scheduler = BackgroundScheduler()
scheduler.add_job(func=web_crawler, trigger="interval", seconds=180)
scheduler.add_job(func=update_file, trigger="interval", seconds=30)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())


app = Flask(__name__)
config = {}
config.update(yaml.load(open('config.yaml', 'rb')))

line_bot_api = LineBotApi(config.get('line_bot_access_token'))
handler = WebhookHandler(config.get('line_bot_secret'))

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        print(body, signature)
        handler.handle(body, signature)

    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def reply(event):
    text = ""
    user_id = event.source.user_id
    message = event.message.text
    if message == "list":
        text = ",".join(userProductDic[user_id])
    elif not validators.url(message) or not message.startswith("https://www.hermes") or "product" not in message:
        text = "please input valid product url"
    else:
        split_message = message.split('/')
        product_id = split_message[-2]
        if message[-1] != '/':
            product_id = split_message[-1]
        if product_id in userProductDic[user_id]:
            userProductDic[user_id].remove(product_id)
            productUserDic[product_id].remove(user_id)
            text = f"removed product ID {product_id} from your watching list"
        else:
            userProductDic[user_id].append(product_id)
            productUserDic[product_id].append(user_id)
            text = f"added product ID {product_id} is in your watching list"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=text)
    )


app.run()
