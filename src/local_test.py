import lambda_function

lambda_function.lambda_handler({
    "Records": [
        {
            "messageId": "1",
            "body": "example"
        },
    ]
}, {})
