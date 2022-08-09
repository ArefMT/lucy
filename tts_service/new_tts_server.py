from pathlib import Path
from re import U
from sanic import Sanic
from sanic.response import text
import json
import websockets
import concurrent.futures
import os
import time
import wave
import asyncio

from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer


synthesizer = None
SONIX_MODEL_NAME = "tts_models/en/ljspeech/tacotron2-DDC"
SONIX_DEFAULT_VOCODER_NAME = "vocoder_models/en/ljspeech/hifigan_v2"
pool = concurrent.futures.ThreadPoolExecutor((os.cpu_count() or 1))
loop = asyncio.get_event_loop()

PORT = 8081
HOST = '0.0.0.0'
connected_clients = dict()
bot_last_answers = {}

app = Sanic(__name__)

@app.get("/")
async def hello_world(request):
    return text("TTS server is running!")


# An endpoint repeat the last utterance by the bot
@app.route("/repeat",methods=["POST"])
async def hello_world(request):
    data = request.json
    user = data['recipient_id']
    msg = bot_last_answers[user]

    if user not in connected_clients:
        return "Error, user not found!"
    ws = connected_clients[user]
    timestamp = str(int(time.time()))
    await ws.send(timestamp)
    ##### Synth part
    filename = await synthesize_audio(user, msg, )
    #############
    # Send the file to the client ########
    wf = wave.open(filename, 'rb')
    wf_length = wf.getnframes()
    data = wf.readframes(wf_length)
    await ws.send(data)  # Try to send it in packages
    #####################################

    return text("200")

@app.route('/msg', methods=["POST"])
async def handler(request):
  global loop
  global pool

  data = request.json
  print(data)
  user = data['recipient_id']
  msg = data['text']

  bot_last_answers[user] = msg


  if user not in connected_clients:
    return "Error, user not found!"
  ws = connected_clients[user]
  timestamp = str(int(time.time()))
  await ws.send(timestamp)
  ##### Synth part
  filename = await synthesize_audio(user, msg,)
  #############
  # Send the file to the client ######## TODO SAVE THE FILE TO A BUFFER##
  wf = wave.open(filename, 'rb')
  wf_length = wf.getnframes()
  data = wf.readframes(wf_length)
  await ws.send(data) # Try to send it in packages
  #####################################

  return text("200!")


# websocket endpoint
@app.websocket("/feed")
async def feed(request, ws):

  while True:
    try:
      message = await ws.recv()
      print(message)
      if isinstance(message, str) and 'event' in message:
        data = json.loads(message)
        if data['event'] == 'connect':
          user_id =  data['user_id']
          print(user_id)
          connected_clients[user_id] = ws
          continue
        if data['event'] == 'disconnect':
          break
    except websockets.ConnectionClosed:
      del connected_clients[user_id]
      print('Error')


#################### For the TTS synthesizer
def create_synthesizer():
    # load model manager
    path = Path(__file__).parent / "../.models.json"
    manager = ModelManager(path)


    speakers_file_path = None
    language_ids_file_path = None
    encoder_path = None
    encoder_config_path = None

    # Download model files
    model_path, config_path, model_item = manager.download_model(SONIX_MODEL_NAME)

    # Download vocoder files
    vocoder_path, vocoder_config_path, _ = manager.download_model(SONIX_DEFAULT_VOCODER_NAME)


    # load models, last args is for using cuda. Choose True. Default to false.
    return Synthesizer(
        model_path,
        config_path,
        speakers_file_path,
        language_ids_file_path,
        vocoder_path,
        vocoder_config_path,
        encoder_path,
        encoder_config_path,
        False,
    )

async def synthesize_audio(user_id, text):
  path = f'wav/standard/{text}.wav'
  f = Path(path)
  if f.is_file():
    return path
  else:
    # generate wav if custom msg
    wav = synthesizer.tts(text)
    filename =  generate_file_name(user_id,'session_id')
    synthesizer.save_wav(wav, filename)
    return filename

def generate_file_name(userid, sessionid):
    timestamp = str(int(time.time()))
    return f'wav/{userid}_{sessionid}_{timestamp}.wav'


if __name__ == '__main__':
  synthesizer = create_synthesizer()
  app.run(host=HOST, port=PORT, debug=True)