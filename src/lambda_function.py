import requests
import boto3
import os
from languages import language_trie 

api_key = os.environ.get("merriam_webster_api_key")

def getLanguageChain(text):
    # I observed that semicolons often mention words from sibling languages rather than the direct chain of descent
    # Therefore we ultimately want the oldest language in the first chain
    chainOfDescentText = text.split(";")[0]

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

        # print("Matches: ", matches, "Prefix: ", prefix, "Word: ", word)
        
        if len(matches) == 0:
            # Not a language, so we just skip to the next word
            prefix = ""
        elif len(matches) == 1 and (matches[0][0] == word or matches[0][0] == f"{prefix} {word}"):
            language_chain.append(matches[0][0])
            prefix = ""
        else:
            if prefix == "":
                prefix = word
            else:
                prefix += " " + word
    
    return language_chain


def fetchEtymology(word):
    res = requests.get(f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={api_key}")
    if res.status_code == 200:
        data = res.json()
        if data:
            etymology = data[0].get('et', [])
            if not etymology:
                return {"fullText": "", "languageChain": []}
            print(f"Fetched etymology from API for {word}: {etymology}")
            suppText = ""
            for entry in etymology:
                if entry[0] == "text":
                    mainText = entry[1]
                elif entry[0] == "et_snote":
                    suppText = entry[1][0][1]  # Assuming the structure is ["et_snote", [["t", string]]]

            if suppText:
                fullText += "\n\n" + suppText
            else:
                fullText = mainText
            return {"fullText": fullText, "languageChain": getLanguageChain(mainText)}
    raise requests.exceptions.HTTPError("Dictionary API request failed with HTTP status code: {}".format(res.status_code))

def lambda_handler(event, context):
    batch_item_failures = []
    
    # SQS sends messages inside an array of Records
    for record in event.get('Records', []):
        message_id = record['messageId']
        try:
            # 1. Extract the payload
            word = record['body']
            
            print(f"Processing message {message_id}: {word}")
            fetch_result = fetchEtymology(word)
            print(f"Fetched etymology for {word}: {fetch_result}")

            db_client = boto3.client('dynamodb')

            if not fetch_result['fullText']:
                print(f"No etymology found for {word}.")
                db_client.put_item(
                                TableName='english_words',
                                Item={
                                    'word': {'S': word},
                                    'MerriamStatus': {'S': 'NoEtymologyFound'},
                                }
                            )
                continue  # Skip to the next message if no etymology is found

            # Insert into DynamoDB
            
            db_client.put_item(
                TableName='merriam-webster-etymologies',
                Item={
                    'word': {'S': word},
                    'fullText': {'S': fetch_result['fullText']},
                    'languageChain': {'SS': fetch_result['languageChain']}
                }
            )
            db_client.put_item(
                TableName='english-words',
                Item={
                    'word': {'S': word},
                    'MerriamStatus': {'S': 'Fetched'},
                }
            )

        except Exception as e:
            print(f"Failed to process message {message_id}. Error: {str(e)}")
            # Keep track of failed messages so only they get retried
            batch_item_failures.append({"itemIdentifier": message_id})
            
    # Return the failures to SQS (Requires "Report batch item failures" enabled on the trigger)
    return {"batchItemFailures": batch_item_failures}