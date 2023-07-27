import functions_framework
import os
import time
import json
import csv
from datetime import datetime

from twilio.rest import Client
from flask import Flask, request, render_template, make_response, jsonify, Response
from google.cloud import storage
@functions_framework.http
def hello_http(request):
  # Your Account SID from twilio.com/console
  account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
  # Your Auth Token from twilio.com/console
  auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
  #twilio number
  twilio_number = os.environ.get("TWILIO_NUMBER")
  client = Client(account_sid,auth_token)
  
  #google
  storage_client = storage.Client()
  bucket_name = os.environ.get("bucket_name")
  bucket = storage_client.bucket(bucket_name)


  #list of leads that are still live: they didn't explicitly ask us to stop, and they aren't landlines.
  liveLeads = []
  
  #undeliverable list
  und = []
  messages = client.messages.list(from_=twilio_number
                           )
  for message in messages:
      if message.status=="undelivered":
          und.append(str(message.to))

  print(len(und))
  

  for blob in bucket.list_blobs(prefix='leads'):
    with blob.open("r") as f:
        text=f.read()
    try:
        current = Conversation.loadJSON(text)
    except Exception as e:
        print("unable to load conversation for " + str(blob) + " due to " + str(e))
        continue
    
    #skip "stop" is in msg.lower
    skip = 0
    for msg in current.messages:#different kind of messages
        if ("stop" in msg["content"].lower() and msg["role"] == "user") or (str(current.number) in str(und)):
            skip = 1
    
    if skip == 0 and current.number not in und:
        liveLeads.append([current.number, current.name])

  #write liveLeads to file.
  blob = bucket.blob("liveLeads.csv")
  with blob.open("w",newline='') as f:
    csvwriter = csv.writer(f)
    csvwriter.writerow(["the total number of undelivered leads was:",len(und)])
    for lead in liveLeads:
        csvwriter.writerow(lead)

  
  return make_response("success",200)





class Conversation:

    def __init__(self, number, initiate, name): 
        self.number = number
        self.closed = 0
        self.log = []
        self.messages = [] #messages are always added as dictionaries. Message.get() returns a dictionary.
        self.name = name

        if(initiate==1):
            self.begin()

    def begin(self):
        #add prompt to messages
        msg = Message("system", loadPrompt() + "\nthe candidate's name is " + self.name)
        self.messages.append(msg.get())
        self.GPTrequest()

    #call this when a new message is received from candidate. Handles everything. Returns 1 on success and 0 on fail.
    def newInbound(self, message):
        #reopen if closed
        if(str(self.closed) == 1):
            self.open()
        
        self.messages.append(message.get())
        response = "error"
        i=0
        tries = 3
        while(response=="error"):
            i = i + 1
            if(i==tries):
                break
            response = self.GPTrequest()
            
        if(response=="error"):
            print("failed to send response to GPT for " + self.number + "after " + tries + "attempts")
            return 0
        return 1

    #sends message chain to GPT for response. Returns a GPT response object on success, and "error" on fail.
    def GPTrequest(self):
        try:
            print(self.messages)
            response =  openai.ChatCompletion.create(
                model="gpt-3.5-turbo",messages = self.gptMessage())
            print(response)
            if(response['choices'][0]['finish_reason']!='stop'):
                print("error getting gpt response due to " + response['choices'][0]['finish_reason'])
                return "error"
        except Exception as e:
            print("attempt: failed to get GPT response due to " + str(e))
            return "error"
        msg = Message("assistant",response['choices'][0]['message']['content'])
        self.messages.append(msg.get())
        if("$EC" in response['choices'][0]['message']['content']):
            self.close()
            return response
        self.sendSMS(response['choices'][0]['message']['content'])
        if("1-888-228-3133" in response['choices'][0]['message']['content']):
            self.close()

        return response

    #checks to see if followup criteria are met, then follows up or closes conversation.
    def followUp(self):
        
        #followup criteria. timing is handled in Cleaner function
        followup =  int(self.closed)==0

        followmsg = "Hi " + self.name + "! Are you still there? Free or reduced health insurance could be just a few steps away. (this is our final follow-up text, but you can reach out again at any time)"
        try:
            if(followup):
                if(str(self.messages[len(self.messages)-1]["content"])==followmsg or self.messages[len(self.messages)-1]["content"].lower()=="stop"):
                    self.close()
                else:
                    try:
                        msg = Message("assistant",followmsg)
                        self.messages.append(msg.get())
                        self.sendSMS(msg.getContent())
                    except Exception as e:
                        self.addLog("unable to send followup " + datetime.now().__str__())
                        raise RuntimeError("unable to handle error")
        except Exception as e:
            self.addLog("Failed to followup" + str(e))
            raise RuntimeError("unable to handle error")
        
    def sendSMS(self, content):
        #sendstwiliosms

        # Your Account SID from twilio.com/console
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        # Your Auth Token from twilio.com/console
        auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
        #twilio number
        twilio_number = os.environ.get("TWILIO_NUMBER")
        client = Client(account_sid,auth_token)
        try:
            message = client.messages.create(
                              body=content,
                              from_=twilio_number,
                              to=self.number
                          )
        except Exception as e:
            self.addLog(e)

    def addLog(self,log):
        print("error logged for " + self.number)
        print("error:" + str(log))
        self.log.append(str(log))
    
    def clearLog(self):
        self.log = []

    #creates a list of message dictionaries that are in the form GPT wants.
    def gptMessage(self):
        out = []
        for msg in self.messages:
            out.append({"role" : msg["role"], "content": msg["content"]})
        return out

    def open(self):
        try:
            storage_client = storage.Client()
            bucket_name = os.environ.get("bucket_name")
            bucket = storage_client.get_bucket(bucket_name)
            blob = bucket.blob("closed.txt")
            with blob.open("r") as f:
                closed = f.read()
            
            closed = closed.replace(str(self.number), "")

            with blob.open("w") as f:
                f.write(closed)
            self.closed = 0
        except Exception as e:
            self.addLog("failed to open conversation.")
        

    def close(self):
        try:
            storage_client = storage.Client()
            bucket_name = os.environ.get("bucket_name")
            bucket = storage_client.get_bucket(bucket_name)
            blob = bucket.blob("closed.txt")
            with blob.open("r") as f:
                closed = f.read()

            closed = closed + " " + str(self.number)

            with blob.open("w") as f:
                f.write(closed)
            self.closed = 1
            self.messages[len(self.messages)-1]["timestamp"] = (datetime.now()-datetime(2022,1,1)).total_seconds()
        except Exception as e:
            self.addLog("failed to close conversation due to " + str(e))


    #takes a list of dictionaries with each dictionary equal to a message
    def loadMessages(self, messages):
        self.messages = list(eval(str(messages)))
        
    def getJSON(self):
      return json.dumps({"number":self.number,"log":self.log,"messages":str(self.messages),"closed":self.closed, "name":self.name})
    
    #this method takes a STRING and makes it a dictionary.
    @staticmethod
    def loadJSON(jsonIn):
        jsonIn = eval(jsonIn)
        try: 
            jsonIn['name']
        except:
            jsonIn['name'] = "unknown"
        conversation = Conversation(jsonIn['number'],0,jsonIn['name'])
        #jsonIn is a dictionary. messages is a list of dictionaries as a string.
        conversation.loadMessages(jsonIn['messages'])
        conversation.log = jsonIn['log']
        conversation.closed = int(jsonIn['closed'])
        conversation.name = jsonIn['name']
        return conversation
    
    
class Message:
    def __init__(self, role, content):
        self.role = role
        self.content = content
        self.timestamp = (datetime.now()-datetime(2022,1,1)).total_seconds()
    
    def getRole(self):
        return self.role
    
    def get(self):
        return {"role": self.role, "content": str(self.content), "timestamp": self.timestamp}
    
    def getTimestamp(self):
        return self.timestamp

    def getContent(self):
        return self.content
    
    def __str__(self):
        return self.role + ":" + self.content