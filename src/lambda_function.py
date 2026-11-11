import requests
import os
from languages import language_trie 

api_key = os.environ.get("merriam_webster_api_key")

def getLanguageChain(fullText):
    # I observed that semicolons often mention words from sibling languages rather than the direct chain of descent
    # Therefore we ultimately want the oldest language in the first chain
    chainOfDescentText = fullText.split(";")[0]

    #Split on whitespace and commas
    words = chainOfDescentText.replace(",", " ").split()

    language_chain = []

    # Some languages are multi-word, so we need to check if it's a prefix of a language
    prefix = ""

    for word in words:
        if prefix == "":
            matches = language_trie.items(word)
        else:
            matches = language_trie.items(f"{prefix} {word}")
        if len(matches) == 0:
            # Not a language, so we just skip to the next word
            prefix = ""
            continue
        elif len(matches) == 1 and matches[0][0] == f"{prefix} {word}":
            language_chain.append(matches[0][0])
            prefix = ""
            continue
        else:
            prefix += " " + word
    
    return language_chain


def fetchEtymology(word):
    res = requests.get(f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={api_key}")
    if res.status_code == 200:
        data = res.json()
        if data:
            etymology = data[0].get('et', [])
            fullText = etymology.get('text', '') if etymology else ''
            return {"fullText": fullText, "languageChain": getLanguageChain(fullText)}
    raise ValueError("Dictionary API request failed with HTTP status code: {}".format(res.status_code))

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