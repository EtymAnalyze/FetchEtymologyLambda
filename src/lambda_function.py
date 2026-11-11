import requests
import os

api_key = os.environ.get("merriam_webster_api_key")

def fetchEtymology(word):
    res = requests.get(f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={api_key}")
    if res.status_code == 200:
        data = res.json()
        if data:
            return data[0].get('et', [])
    return []

def lambda_handler(event, context):
    batch_item_failures = []
    
    # SQS sends messages inside an array of Records
    for record in event.get('Records', []):
        message_id = record['messageId']
        try:
            # 1. Extract the payload
            word = record['body']
            
            # 2. Process / Ingest data (e.g., save to DynamoDB, S3, RDS, etc.)
            print(f"Processing message {message_id}: {word}")
            
            fetch_result = fetchEtymology(word)
            print(f"Fetched etymology for {word}: {fetch_result}")
            
        except Exception as e:
            print(f"Failed to process message {message_id}. Error: {str(e)}")
            # Keep track of failed messages so only they get retried
            batch_item_failures.append({"itemIdentifier": message_id})
            
    # Return the failures to SQS (Requires "Report batch item failures" enabled on the trigger)
    return {"batchItemFailures": batch_item_failures}