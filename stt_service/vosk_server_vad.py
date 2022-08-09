#!/usr/bin/env python3

import json
import os
import sys
import asyncio
import pathlib
import websockets
import concurrent.futures
import logging
import requests
from vosk import Model, SpkModel, KaldiRecognizer


# Original version written by Vosk
# This version edited by Aref El-Maarawi
### for VAD#################
import threading
import numpy as np
import torch
import wave
torch.set_num_threads(1)
import torchaudio
torchaudio.set_audio_backend("soundfile")
import io
import soundfile as sf
import scipy.io.wavfile
from scipy.io.wavfile import write


#############################
# Setup the VAD model
#############################
vad_model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                              model='silero_vad',
                              force_reload=True)

(get_speech_timestamps,
 save_audio,
 read_audio,
 VADIterator,
 collect_chunks) = utils

# minimum confidence of the VAD to be recognized as voice
vad_threshold = 0.8
silence_time = 3.5
num_samples = 1536
#############################
# Provided by Alexander Veysov
def int2float(sound):
    abs_max = np.abs(sound).max()
    sound = sound.astype('float32')
    if abs_max > 0:
        sound *= 1/abs_max
    sound = sound.squeeze()  # depends on the use case
    return sound
######################################################################################

# TODO: add the endpoint of rasa server
RASA_ENDPOINT = ''

# Current collected users via the websocket
connected_users = dict()

# Connect chunks together to form the text, so the reults are appended if they are not in text, and we reset.
#def process_chunk(rec, message, user_id):
def process_chunk(rec, message):
    if isinstance(message, str) and 'event' in message:
        data = json.loads(message)
        if data['event'] == 'stop_listening':
            text = json.loads(rec.FinalResult())['text']
            response_json = f'''{{"event":"final_response","message": "{text}"}}'''
            sender = data['user_id']
            return response_json, sender
    elif rec.AcceptWaveform(message):
        text = json.loads(rec.Result())['text']
        response_json = f'''{{"event":"response","message": "{text}"}}'''
        # Change the sender:
        sender = 'partial_sender'
        return response_json, sender
    else:
        text = json.loads(rec.PartialResult())['partial']
        response_json = f'''{{"event":"partial_response","message": "{text}"}}'''
        sender = 'partial_sender'
        return response_json, sender



async def send_message_to_rasa(user,message):
    data = {'sender':user, 'message': message}
    response = requests.post(url=RASA_ENDPOINT, json=data)
    print(message)
    print(response.text)

# We create a new event loop to be able to access it in the new timer thread.
def signal_recording_stop(websocket):
    print('#############################STOPED Receiving############################')
    asyncio.set_event_loop(asyncio.new_event_loop())
    message = '''{"event":"stopped_receiving","message": "Silence detected."}'''
    asyncio.get_event_loop().run_until_complete(websocket.send(message))

# websockets take care of closing the connection when this handler exits.
async def recognize(websocket, path):
    global model
    global spk_model
    global args
    global loop
    global pool

    global vad_model

    result = ''

    kaldi_recognizer = None
    phrase_list = None

    sample_rate = args.sample_rate
    show_words = args.show_words
    max_alternatives = args.max_alternatives

    logging.info('Connection from %s', websocket.remote_address)

    ######################################
    #Which instead of writing the contents to a file, it's written to an in memory buffer. In other words a chunk of RAM
    seek_curso = 0
    bytes_wav = bytearray()
    byte_io = io.BytesIO(bytes_wav)
    timer = threading.Timer(silence_time, signal_recording_stop, [websocket])
    is_stop_triggerd = False
    ######################################
    try:
        while True:
            message = await websocket.recv()
            #####################################################
            # We receive bytes.
            # We need to buffer preferably 4000 bytes
            if not isinstance(message, str):
                byte_io.write(message)
                if byte_io.getbuffer().nbytes > num_samples + seek_curso:
                    #Fill puffer with zeros "silence" and then the voice
                    # we write the byte to an in-memory buffer
                    byte_io.seek(seek_curso)
                    seek_curso += num_samples
                    audio_chunk = byte_io.read1(num_samples)
                    audio_int16 = np.frombuffer(audio_chunk, np.int16)
                    audio_float32 = int2float(audio_int16)
                    # get the confidence level, where 1.0 means a 100% chance that a human voice is detected.
                    #voice_confidence = await asyncio.create_task(vad_model(torch.from_numpy(audio_float32), 16000).item())
                    voice_confidence = vad_model(torch.from_numpy(audio_float32), 16000).item()
                    #################################################################################
                    # If no voice detected for 3 seconds trigger stopping the recording
                    if voice_confidence > vad_threshold:
                        print('Voice detected!')
                        is_stop_triggerd = False
                        if timer.is_alive():
                            print("----Cancel timer----")
                            timer.cancel()
                        continue
                    if 1 > vad_threshold > voice_confidence and not is_stop_triggerd:
                        print('Silence detected.')
                        is_stop_triggerd = True
                        if timer.is_alive():
                            timer.cancel()
                        timer = threading.Timer(silence_time, signal_recording_stop, [websocket])
                        timer.start()
                        print("----timer triggered----")
                        continue
                        #also run the model in its own thread/ task.



            # todo: handel unknown message type
            if isinstance(message, str) and 'event' in message:
                data = json.loads(message)
                if data['event'] == 'connect':
                    user_id =  data['user_id']
                    connected_users[websocket] = user_id
                    logging.info(f'{user_id} is connected under the connection {websocket}')
                    continue
                if data['event'] == 'disconnect':
                    #logging.info(f'{user_id} is disconnected')
                    break

            # Load configuration if provided
            if isinstance(message, str) and 'config' in message:
                jobj = json.loads(message)['config']
                logging.info("Config %s", jobj)
                if 'phrase_list' in jobj:
                    phrase_list = jobj['phrase_list']
                if 'sample_rate' in jobj:
                    sample_rate = float(jobj['sample_rate'])
                if 'words' in jobj:
                    show_words = bool(jobj['words'])
                if 'max_alternatives' in jobj:
                    max_alternatives = int(jobj['max_alternatives'])
                continue

            # Create the recognizer, word list is temporary disabled since not every model supports it
            if not kaldi_recognizer:
                if phrase_list:
                    kaldi_recognizer = KaldiRecognizer(model, sample_rate, json.dumps(phrase_list, ensure_ascii=False))
                else:
                    kaldi_recognizer = KaldiRecognizer(model, sample_rate)
                kaldi_recognizer.SetWords(show_words)
                kaldi_recognizer.SetMaxAlternatives(max_alternatives)
                if spk_model:
                    kaldi_recognizer.SetSpkModel(spk_model)
            #response = await loop.run_in_executor(pool, process_chunk, kaldi_recognizer, message)
            #             response = await loop.run_in_executor(pool, process_chunk, kaldi_recognizer,
            #             message,connected_users[websocket])
            response, sender = await loop.run_in_executor(pool, process_chunk, kaldi_recognizer, message)

#################### dealing with the responses: send to Rasa/client ############################
            response_json = json.loads(response)
            if response_json["event"] == "partial_response":
                await websocket.send(response)
            elif response_json["event"] == "response":
                result += f'''{response_json["message"]} '''
                message = f'''{{"event":"response","message": "{result}"}}'''
                await websocket.send(message)
            elif response_json["event"] == "final_response":
                print("XXXXXXXXXXXX Final response! XXXXXXXXXXXX")
                result += f'''{response_json["message"]} '''
                # Here we use the language detector, we use the wave buffer and feed the model to detect langauge, if
                # it is english we forward the message to Rasa, if not we send to RASA (say language is not english).
                print("----Restarting the buffer----")
                # TODO: Reset the model after finishing! For every new sentence
                #VADIterator.reset_states()
                # Restart buffer.
                bytes_wav = bytearray()
                byte_io = io.BytesIO(bytes_wav)
                seek_curso = 0
                byte_io.seek(seek_curso)

                # send to rase core server
                await send_message_to_rasa(sender, result)
                print('Message sent to Rasa')
                result = ''
                logging.info('Lucy stopped listening.')


    except websockets.exceptions.ConnectionClosedOK:
        pass
        #Remove the connected client from dict
        #user_id = connected_users[websocket]
        #logging.info(f'The connection to {user_id} has been closed in a normal way, hooray!')
    except websockets.exceptions.ConnectionClosedError:
        pass
        #Remove the connected client from dict
        #user_id = connected_users[websocket]
        #logging.info(f'The connection to {user_id} has been closed in abnormal way, boo!')
    finally:
        byte_io.close()
        # user_id = connected_users[websocket]
        # connected_users.pop(websocket, None)
        # logging.info(f'{user_id} is removed and not anymore connected')


def start():

    global model
    global spk_model
    global args
    global loop
    global pool

    # Enable loging if needed
    #
    # logger = logging.getLogger('websockets')
    # logger.setLevel(logging.INFO)
    # logger.addHandler(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO)


    # ?? maybe create a class to save the attribute?
    args = type('', (), {})()

    #'172.0.0.1'
    args.interface = os.environ.get('VOSK_SERVER_INTERFACE','0.0.0.0')
    args.port = int(os.environ.get('VOSK_SERVER_PORT', 8080))
    args.model_path = os.environ.get('VOSK_MODEL_PATH', 'model')
    args.spk_model_path = os.environ.get('VOSK_SPK_MODEL_PATH')
    args.sample_rate = float(os.environ.get('VOSK_SAMPLE_RATE', 8000))
    args.max_alternatives = int(os.environ.get('VOSK_ALTERNATIVES', 0))
    args.show_words = bool(os.environ.get('VOSK_SHOW_WORDS', True))

    if len(sys.argv) > 1:
       args.model_path = sys.argv[1]

    # Gpu part, uncomment if vosk-api has gpu support
    #
    # from vosk import GpuInit, GpuInstantiate
    # GpuInit()
    # def thread_init():
    #     GpuInstantiate()
    # pool = concurrent.futures.ThreadPoolExecutor(initializer=thread_init)

    model = Model(args.model_path)
    spk_model = SpkModel(args.spk_model_path) if args.spk_model_path else None

    pool = concurrent.futures.ThreadPoolExecutor((os.cpu_count() or 1))
    loop = asyncio.get_event_loop()

    start_server = websockets.serve(
        recognize, args.interface, args.port)

    logging.info("Listening on %s:%d", args.interface, args.port)
    loop.run_until_complete(start_server)
    loop.run_forever()

if __name__ == '__main__':
    start()
