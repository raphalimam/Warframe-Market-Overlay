import requests
import json
import boto3
import os

API = "https://api.warframe.market/v1/"
S3_BUCKET = os.getenv("WFMO_S3_BUCKET", "www.jsourdough.com")


def get_json(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def itemCheck():
    itemsNames = {}
    itemsIds = {}
    setsIds = {}
    itemsRaw = get_json(API + "items")["payload"]["items"]
    for v in itemsRaw:
        if (" Prime " in v["item_name"]) and (not " Set" in v["item_name"]):
            itemsNames[v["item_name"]] = v["url_name"]
            itemsIds[v["id"]] = v["item_name"]
        elif (" Prime " in v["item_name"]) and (" Set" in v["item_name"]):
            setsIds[v["id"]] = v["item_name"]
    return itemsNames, itemsIds, setsIds


def ducatCheck(itemsIds, setsIds):
    itemsDucat = {}
    ducatsRaw = get_json(API + "tools/ducats")["payload"]["previous_hour"]
    for i, v in enumerate(ducatsRaw):
        if not any(x in v["item"] for x in setsIds):
            itemsDucat[itemsIds[v["item"]]] = v["ducats"]
    return itemsDucat


def lambda_handler(event, context):
    print("Started item and ducat check")
    itemsNames, itemsIds, setsIds = itemCheck()
    itemsDucat = ducatCheck(itemsIds, setsIds)
    ItemList = {"itemsNames": itemsNames, "itemsDucat": itemsDucat}
    client = boto3.client("s3")
    client.put_object(
        Bucket=S3_BUCKET,
        Key="ItemsAndDucats.json",
        Body=json.dumps(ItemList, indent=4),
        ContentType="text/plain",
    )
    print("Page Updated")
