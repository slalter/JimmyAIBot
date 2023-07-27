import functions_framework
import os
import openai
import time
import json
from datetime import datetime

from twilio.rest import Client
from flask import Flask, request, render_template, make_response, jsonify, Response
from twilio.twiml.messaging_response import MessagingResponse
from google.cloud import storage


@functions_framework.http
def hello_http(request):
    storage_client = storage.Client()
    bucket_name = os.environ.get("bucket_name")
    bucket = storage_client.bucket(bucket_name)
    dump = ""
    for blob in bucket.list_blobs(prefix='leads'):
        try:
            with blob.open("r") as f:
                dump = dump + "\n" + f.read()
        except:
            pass

    blob = bucket.blob("DUMP" + str(datetime.now()) + ".txt")
    with blob.open("w") as f:
        f.write(dump)
    return make_response("DUMP TAKEN",200)