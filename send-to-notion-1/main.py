import functions_framework
import os
import requests
import json
import math
from flask import make_response, Response
from google.cloud import storage
#TODO: use additional text fields for longer responses.

@functions_framework.http
def hello_http(request):
    IO.start()
    
    #get pages
    try:
        pages = getPageDict()
    except Exception as e:
        print("unable to get pageDict due to " + str(e)+ "______________CRITICAL ERROR")
        return make_response("error",400)
    
    #get parts
    try:
        partDict = getPartsDict()
    except Exception as e:
        print("unable to get parts Dict due to " + str(e)+ "______________CRITICAL ERROR")
        return make_response("error",400)
    
    for number, part in partDict.items():
        try:
            if number in pages.keys():
                #compare times
                print("exists already.")
                if float(part["timestamp"])>float(pages[number]["properties"]["Timestamp"]["rich_text"][0]["text"]["content"]):
                    IO.archivePage(pages[number])
                    IO.uploadPage(part)
            else:
                try:
                    IO.uploadPage(part)
                except Exception as e:
                    print("failed to upload.")
                    raise e
        except Exception as e:
            print("unable to compare page/conversation for " + str(number) + " because of " + str(e))
   
        
    return make_response("success", 200)



def getPartsDict():
    out = {}
    for blob in IO.bucket.list_blobs(prefix='leads'):
        try:
            with blob.open("r") as f:
                txt = f.read()
            parts = getParts(txt)
            print("got a part:" + str(parts))
            if parts == {}:
                continue
            out[parts["number"]] = parts
        except Exception as e:
            print("unable to get parts for " + str(blob))
            raise e
    return out



def getPageDict():
    try:
        response = requests.post("https://api.notion.com/v1/databases/"+IO.databaseID + "/query", headers = IO.notionHeaders)
        print(response.status_code)
    except Exception as e:
        print("failed to getPages due to " + str(e))
        raise e
    out = {}
    for page in response.json()["results"]:
        out[page["properties"]["Number"]["phone_number"]] = page
    return out
    

#takes a json of a conversation and returns a python dict {number:str, messages:list[str], prompt:str,closed:int,timestamp:int}
def getParts(jsonIn):
    print("getting parts...")
    try:
        data = eval(jsonIn)
    except:
        print("unable to evaluate json. Skipping...")
        return {}

    number = data["number"]
    print(number)
    allmsg = list(eval(str(data["messages"])))
    if(len(allmsg)>3):
        split = math.floor((len(allmsg)-1)/2)
        msg2 = allmsg[split:]
        msg1 = allmsg[1:split]
    else:
        msg1 = allmsg[1:]
        msg2 = ""
    prompt = str(allmsg[0]["content"])
    if len(prompt)>1999:
        prompt = prompt[0:1997]
    closed = data["closed"]
    try:
        timestamp = allmsg[len(allmsg)-1]["timestamp"]
    except Exception as e:
        print("unable to get timestamp due to " + str(e))
        timestamp = ""
    return {"number":number,"messages":str(msg1),"messages2":str(msg2),"prompt":str(prompt), "closed":closed, "timestamp":timestamp}




#MUST run start to use methods.
class IO:
    
    @staticmethod
    def start():
        #google
        IO.storage_client = storage.Client()
        IO.bucket = IO.storage_client.bucket(os.environ.get("bucket_name"))

        #Notion
        SECRET = os.environ.get('NOTION_KEY').__str__()
        IO.notionHeaders = {
            'Authorization': 'Bearer '+ SECRET,
            'Notion-Version': '2022-06-28',
            'Content-Type': 'application/json',
            }
        
        #default database ID: logs for gpt.
        IO.databaseID = "09beea08a1944616a115feb5601322f0"
        
    #inserts the parent page information to an otherwise complete json, then posts.
    @staticmethod
    def createDatabase(parentPage,data):
        data = str(data)
        data = "{'parent':{'type':'page_id','pageid':'"+str(parentPage)+"'}," + data[1:]
        try:
            requests.post("https://api.notion.com/v1/databases/",headers=IO.notionHeaders(),data=data)
        except Exception as e:
            print("error posting database " + str(e))
    
    def setDatabaseID(databaseid):
        IO.databaseID=databaseid

    def getDatabase(filename):
        try:
            response = requests.get("https://api.notion.com/v1/databases/"+IO.databaseID, headers=IO.notionHeaders)
            print(response.json())
            try:
                blob = IO.bucket.blob(filename)
                with blob.open("w") as f:
                    f.write(json.dumps(response.json()))
            except Exception as e:
                raise e
        except Exception as e:
            print("unable to retrieve database due to " + str(e))

    @staticmethod
    def uploadPage(info):
        print("uploading page...")
        try:
            if str(info["closed"])=="1":
                typeO = "Closed"
            else:
                typeO = "Open"
            try:
                messages = ""
                messages2 = ""
                messagelist = list(eval(str(info["messages"])))
                for msg in messagelist:
                    messages = messages + msg["role"] + ": " + msg["content"] + "\n"
                print(len(messages))
                print(messages)
                messagelist2 = list(eval(str(info["messages2"])))
                for msg in messagelist2:
                    messages2 = messages2 + msg["role"] + ": " + msg["content"] + "\n"
                print(messages2)
            except Exception as e:
                print("fuckin message stuff " + str(e))
            jsonOut = {
                "parent":{
                        "type": "database_id",
                        "database_id":IO.databaseID
                        },

                "properties":{
                    "URL": {
                    "type": "url",
                    "url": None
                    },
                    "Status": {
                        "type": "status",
                        "status": {
                            "id": "16561080-e9e0-4ac6-abca-b82a60fb445d",
                            "name": "Not started",
                            "color": "default"
                        }
                    },
                    "Messages": {
                        "type": "rich_text",
                        "rich_text": [{"text":{"content":str(messages)}}]
                    },
                    "Messages2": {
                        "type": "rich_text",
                        "rich_text":[{"text":{"content":str(messages2)}}]
                    },
                    "Number": {
                        "type": "phone_number",
                        "phone_number": str(info["number"])
                    },
                    "Timestamp": {
                        "type": "rich_text",
                        "rich_text": [{"text":{"content":str(info["timestamp"])}}]
                    },
                    "Prompt": {
                        "type": "rich_text",
                        "rich_text": [{"text":{"content":str(info["prompt"])}}]
                    },
                    "Type": {
                        "id": "title",
                        "type": "title",
                        "title": [
                            {
                                "type": "text",
                                "text": {
                                    "content": typeO,
                                    "link": None
                                },
                                "annotations": {
                                    "bold": False,
                                    "italic": False,
                                    "strikethrough": False,
                                    "underline": False,
                                    "code": False,
                                    "color": "default"
                                },
                                "plain_text": typeO,
                                "href": None
                            }
                        ]
                    }
                }
            }
            print(jsonOut)
            response = requests.post("https://api.notion.com/v1/pages", headers = IO.notionHeaders,data=json.dumps(jsonOut))
            print(str(response.status_code) + str(response.content))
        except Exception as e:
            raise e
    

    @staticmethod
    def writeToBucket(path, contents):
        try:
            blob = IO.bucket.blob(path)
            with blob.open("w") as f:
                f.write(contents)
        except Exception as e:
            print("unable to write to" + str(blob) + " due to " + str(e))
        
    #archives a Notion page
    def archivePage(page):
        try:
            response = requests.patch("https://api.notion.com/v1/pages/"+page["id"], headers=IO.notionHeaders,data=json.dumps({"archived":True}))
            print(response.content)
        except Exception as e:
            print("unable to archive page " + str(page))
