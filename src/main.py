import copy
import json
import logging
import os
import string
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import boto3
import requests
from linebot import LineBotApi
from linebot.models import FlexSendMessage, TextSendMessage

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", logging.WARN))


def lambda_handler(event, context):
    """_summary_
        AWS Lambda エントリポイント。

    Args:
        event (Any): AWS event.
        context (Any): AWS context.

    Returns:
        dict: statusCode, body
    """
    try:
        logger.debug(f"event:{json.dumps(event)}")
        # lineからのリスクエストを分解
        ev = json.loads(event["body"])["events"]
        logger.info(f"ev:{json.dumps(ev)}")

        # データチェック
        if ev is None or len(ev) == 0:
            return {"statusCode": 400, "body": json.dumps("Not Execute.")}

        line_api = LineBotApi(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])

        # 位置情報設定
        if ev[0]["type"] == "message" and ev[0]["message"]["type"] == "location":
            put_Aws_Ssm({"weather-latitude": ev[0]["message"]["latitude"], "weather-longitude": ev[0]["message"]["longitude"]})
            ssm_param = get_Aws_Ssm(["weather-latitude", "weather-longitude"])

            if (
                "weather-latitude" in ssm_param
                and ssm_param["weather-latitude"] != ""
                and "weather-longitude" in ssm_param
                and ssm_param["weather-longitude"] != ""
            ):
                # テンプレート使用
                with open("./txt/Setting_Location_Info.txt") as f:
                    msg = string.Template(f.read())
                # 設定された位置情報を返信
                msg = msg.substitute(
                    latitude=ssm_param["weather-latitude"],
                    longitude=ssm_param["weather-longitude"],
                )
                logger.info(f"send message:{msg}")
            else:
                msg = "位置情報を設定できませんでした。"

            line_api.reply_message(ev[0]["replyToken"], TextSendMessage(text=msg))
        # 都市名設定(受け口)
        elif ev[0]["type"] == "message" and ev[0]["message"]["text"] == "天気予報の都市を変更させて！":
            # 別ファイルで定義
            with open("./json/City_Name.json") as f:
                msg = json.load(f)

            line_api.reply_message(ev[0]["replyToken"], FlexSendMessage(alt_text="City Name Flex Message", contents=msg))
        # 都市名設定(設定)
        elif ev[0]["type"] == "message" and "City Name Parameter:" in ev[0]["message"]["text"]:
            city = str(ev[0]["message"]["text"]).replace("City Name Parameter:", "")
            put_Aws_Ssm({"weather-city": city})
            ssm_param = get_Aws_Ssm(["weather-city"])

            if "weather-city" in ssm_param and ssm_param["weather-city"] != "":
                # テンプレート使用
                with open("./txt/Setting_City_Info.txt") as f:
                    msg = string.Template(f.read())
                # 設定された位置情報を返信
                msg = msg.substitute(
                    city_name=ssm_param["weather-city"],
                )
                logger.info(f"send message:{msg}")
            else:
                msg = "位置情報を設定できませんでした。"

            line_api.reply_message(ev[0]["replyToken"], TextSendMessage(text=msg))
        # APIで位置情報を特定する際に利用するパラメータの設定(受け口)
        elif ev[0]["type"] == "message" and ev[0]["message"]["text"] == "天気予報の地域特定方法を変更させて！":
            # 別ファイルで定義
            with open("./json/API_GEO_Params.json") as f:
                msg = json.load(f)

            line_api.reply_message(ev[0]["replyToken"], FlexSendMessage(alt_text="API GEO Params Flex Message", contents=msg))
        # APIで位置情報を特定する際に利用するパラメータの設定(設定)
        elif ev[0]["type"] == "message" and "WF Parameter:" in ev[0]["message"]["text"]:
            city = str(ev[0]["message"]["text"]).replace("WF Parameter:", "")
            put_Aws_Ssm({"weather-API-param": city})
            ssm_param = get_Aws_Ssm(["weather-API-param"])

            if "weather-API-param" in ssm_param and ssm_param["weather-API-param"] != "":
                # テンプレート使用
                with open("./txt/Setting_API_Params.txt") as f:
                    msg = string.Template(f.read())
                # 設定された位置情報を返信
                msg = msg.substitute(
                    wf_param=ssm_param["weather-API-param"],
                )
                logger.info(f"send message:{msg}")
            else:
                msg = "天気予報地域の特定方法を設定できませんでした。"

            line_api.reply_message(ev[0]["replyToken"], TextSendMessage(text=msg))
        # 現在のParameter Store設定
        elif ev[0]["type"] == "message" and ev[0]["message"]["text"] == "今の設定を教えて！":
            ssm_param = get_Aws_Ssm(["weather-latitude", "weather-longitude", "weather-city", "weather-API-param"])

            if (
                "weather-latitude" in ssm_param
                and ssm_param["weather-latitude"] != ""
                and "weather-longitude" in ssm_param
                and ssm_param["weather-longitude"] != ""
                and "weather-city" in ssm_param
                and ssm_param["weather-city"] != ""
                and "weather-API-param" in ssm_param
                and ssm_param["weather-API-param"] != ""
            ):
                # テンプレート使用
                with open("./txt/Setting_All_Params.txt") as f:
                    msg = string.Template(f.read())
                # 取得情報に書き換え
                msg = msg.substitute(
                    latitude=ssm_param["weather-latitude"],
                    longitude=ssm_param["weather-longitude"],
                    city_name=ssm_param["weather-city"],
                    wf_param=ssm_param["weather-API-param"],
                )
                logger.info(f"send message:{msg}")
            else:
                msg = "設定値を取得できませんでした。"

            line_api.reply_message(ev[0]["replyToken"], TextSendMessage(text=msg))
        # 今の天気
        elif ev[0]["type"] == "message" and ev[0]["message"]["text"] == "今の天気を教えて！":
            json_o = get_weather(os.environ["WEATHER_API_CURRENT_URL"])

            # テンプレート使用
            with open("./txt/Current_Weather_Forecast.txt") as f:
                msg = string.Template(f.read())

            # APIで取得した現在の天気情報を必要な部分だけ切り出し、リプライメッセージを作成
            msg = msg.substitute(
                description=json_o["weather"][0]["description"],
                icon=parse_weather_icon(json_o["weather"][0]["icon"]),
                temp=str(json_o["main"]["temp"]),
                temp_feels_like=str(json_o["main"]["feels_like"]),
                humidity=str(json_o["main"]["humidity"]),
                speed=str(json_o["wind"]["speed"]),
            )
            logger.info(f"send message:{msg}")

            line_api.reply_message(ev[0]["replyToken"], TextSendMessage(text=msg))
        # 明日までの3時間ごとの天気
        elif ev[0]["type"] == "message" and ev[0]["message"]["text"] == "明日までの天気を教えて！":
            line_api.reply_message(ev[0]["replyToken"], TextSendMessage(text=weather_forecast_2D3H()))
        # 明日までの3時間ごとの天気 (Cron用の受け口)
        elif ev[0]["type"] == "message" and ev[0]["message"]["text"] == "Scheduled Weather Forecast":
            line_api.push_message(os.environ["LINE_USER_ID"], TextSendMessage(text=weather_forecast_2D3H()))
        else:
            msg = f'申し訳ございません。【{ev[0]["message"]["text"]}】はご利用いただけません。'
            logger.info(f"send message:{msg}")
            # オウム返し
            line_api.reply_message(ev[0]["replyToken"], TextSendMessage(text=msg))
    except Exception as e:
        logger.error(f"Exception occurred. Cause:{e}")
        return {"statusCode": 500, "body": json.dumps("Exception occurred.")}

    return {"statusCode": 200, "body": json.dumps("Reply ended normally.")}


def weather_forecast_2D3H():
    """_summary_
        明日までの3時間ごとの天気を取得する。

    Returns:
        str: 明日までの3時間ごとの天気
    """
    json_o = get_weather(os.environ["WEATHER_API_5D3H_URL"])

    # 現在日時以降の天気を取得するため、現在日時を取得
    # 明日の天気を取得するため、翌々日の0時データを作成
    now = datetime.now(tz=ZoneInfo("Asia/Tokyo"))
    two_days_later = now + timedelta(days=2.0)
    tdl = datetime(
        year=two_days_later.year,
        month=two_days_later.month,
        day=two_days_later.day,
        hour=0,
        minute=0,
        second=0,
        tzinfo=ZoneInfo("Asia/Tokyo"),
    )

    # テンプレート使用
    with open("./txt/2D3H_Weather_Forecast.txt") as f:
        template = string.Template(f.read())

    msg = ""
    for li in json_o["list"]:
        if "dt_txt" not in li:
            continue

        one_line = copy.copy(template)
        compare_dt = datetime.strptime(li["dt_txt"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Tokyo"))
        compare_dt += timedelta(hours=9.0)

        if now <= compare_dt <= tdl:
            one_line = one_line.substitute(
                dt=compare_dt.strftime("%m/%d %H時"),
                weather_icon=parse_weather_icon(li["weather"][0]["icon"]),
                temperature=str(li["main"]["temp"]),
            )
            msg += one_line + "\n"

    msg = msg.rstrip("\n")
    logger.info(f"send message:{msg}")
    return msg


def get_weather(url: str):
    """_summary_
        天気API実行。

    Args:
        url (str): API URL.

    Returns:
        dict: Weather API response.
    """
    params = {
        "appid": os.environ["WEATHER_API_TOKEN"],
        "units": "metric",
        "lang": "ja",
    }
    params.update(get_Location_Or_Default())
    logger.debug(json.dumps(params))
    response = requests.get(url, params)
    logger.info(response.text)

    return response.json()


def get_Location_Or_Default():
    """_summary_
        Locationの情報を取得する。
        latitude, longitude 情報がない場合、デフォルトの都市名(tokyo)を返す。

    Args:
        json (dict): lineから送信されたlocation情報

    Returns:
        dict: 位置情報 or 都市名
    """
    # AWS Parameter Storeから緯度、経度、都市名を取得
    ssm_param = get_Aws_Ssm(["weather-city", "weather-latitude", "weather-longitude"])

    if (
        "weather-latitude" in ssm_param
        and ssm_param["weather-latitude"] != ""
        and "weather-longitude" in ssm_param
        and ssm_param["weather-longitude"] != ""
    ):
        return {"lat": ssm_param["weather-latitude"], "lon": ssm_param["weather-longitude"]}
    elif "weather-city" in ssm_param and ssm_param["weather-city"] != "":
        return {"q": ssm_param["weather-city"]}
    else:
        return {"q": "tokyo"}


def put_Aws_Ssm(param: dict):
    """_summary_
        AWS System ManagerのParamter Storeに設定する。

    Args:
        param (dict): Paramter Storeに設定したいkey-value
    """
    ssm = boto3.client("ssm", os.environ["AWS_SSM_REGION"])

    for key, val in param.items():
        ssm.put_parameter(Name=key, Value=str(val), Type="String", Overwrite=True)


def get_Aws_Ssm(param: list):
    """_summary_
        AWS System ManagerのParamter Storeから取得する。

    Args:
        param (list): Parameter Storeから取得したいキー

    Returns:
        dict: Parameter Store の情報
    """
    ssm = boto3.client("ssm", os.environ["AWS_SSM_REGION"])
    response = ssm.get_parameters(
        Names=param,
        WithDecryption=True,
    )

    ssm_param = {}
    for p in response["Parameters"]:
        ssm_param.update({p["Name"]: p["Value"]})

    return ssm_param


def parse_weather_icon(icon_text: str):
    """_summary_
        weather iconを変換。

    Args:
        icon_text (str): icon id

    Returns:
        str: icon (環境依存文字)
    """
    if icon_text == "01d" or icon_text == "01n":
        return "☀"
    elif icon_text == "02d" or icon_text == "02n" or icon_text == "03d" or icon_text == "03n" or icon_text == "04d" or icon_text == "04n":
        return "☁"
    elif icon_text == "09d" or icon_text == "09n" or icon_text == "10d" or icon_text == "10n":
        return "☂️"
    elif icon_text == "11d" or icon_text == "11n":
        return "⚡️"
    elif icon_text == "13d" or icon_text == "13n":
        return "☃️"
    else:
        return ""
