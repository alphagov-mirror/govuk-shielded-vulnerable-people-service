import boto3
from boto3.dynamodb.conditions import Key
import datetime
import decimal
import secrets
import time

from flask import current_app


def get_dynamodb_client():
    return boto3.resource(
        "dynamodb", endpoint_url=current_app.config.get("LOCAL_AWS_ENDPOINT_URL")
    )


def _form_response_tablename():
    return current_app.config.get(
        "AWS_DYNAMODB_SUBMISSIONS_TABLE_NAME", "coronavirus-vulnerable-people"
    )


def generate_reference_number():
    return f'{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}-{secrets.token_hex(3)}'


def write_answers_to_table(nhs_sub, answers):
    get_dynamodb_client().Table(_form_response_tablename()).put_item(
        Item={
            "NHSSub": nhs_sub,
            "ReferenceId": generate_reference_number(),
            "UnixTimestamp": decimal.Decimal(time.time()),
            "FormResponse": answers,
        }
    )


def get_record_using_nhs_sub(nhs_sub):
    result = (
        get_dynamodb_client()
        .Table(_form_response_tablename())
        .query(
            IndexName="NHSSub-index", KeyConditionExpression=Key("NHSSub").eq(nhs_sub)
        )
    )
    if result["ResponseMetadata"]["HTTPStatusCode"] != 200:
        raise RuntimeError(
            f"Could not retrieve stored answers from dynamodb retrieved ResponseMetadata {result['ResponseMetadata']}"
        )
    items = result["Items"]
    if len(items) > 1:
        current_app.logger.error(
            f"Found {len(items)} results for nhs_sub: {nhs_sub} expected 1 item continuing with oldest item"
        )
    return min(items, default=None, key=lambda item: item["UnixTimestamp"])


def create_tables_if_not_exist():
    client = get_dynamodb_client()

    # client.meta.client.delete_table(TableName=_form_response_tablename())
    try:
        client.create_table(
            TableName=_form_response_tablename(),
            KeySchema=[
                {"AttributeName": "ReferenceId", "KeyType": "HASH"},
                {"AttributeName": "UnixTimestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "ReferenceId", "AttributeType": "S"},
                {"AttributeName": "NHSSub", "AttributeType": "S"},
                {"AttributeName": "UnixTimestamp", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "string",
                    "KeySchema": [{"AttributeName": "NHSSub", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 120,
                        "WriteCapacityUnits": 20,
                    },
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 120, "WriteCapacityUnits": 20},
        )
    except client.meta.client.exceptions.ResourceInUseException:
        return False
    return True

