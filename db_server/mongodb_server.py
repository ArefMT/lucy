from sanic import Sanic
from sanic.response import text
import urllib.parse
from pymongo import MongoClient
import json

PORT = 8082
HOST = '0.0.0.0'
app = Sanic(__name__)
usr = "give usr name"
psw = "give password"
db = 'rasa_db'
client = MongoClient(f'mongodb://{usr}:{urllib.parse.quote_plus(psw)}@/{db}')

rasa_db = client['rasa_db']
collection = rasa_db['infos']


@app.get("/")
async def hello_world(request):
    return text("DB server is running!")

# save incoming data to db
@app.route('/api', methods=["POST"])
async def handler(request):
  data = request.json

  if data:
      id = data['user_id']
      filter = {'user_id': id}
      values = {}

      for i in data:
          values.update({i: data[i]})

      newvalues = {"$set": values}
      collection.update_one(filter, newvalues, upsert=True)
      print(data)

  return text("200!")


if __name__ == '__main__':

    app.run(host=HOST, port=PORT, debug=True)