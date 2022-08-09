import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:audio_session/audio_session.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:porcupine_flutter/porcupine_error.dart';
import 'package:porcupine_flutter/porcupine_manager.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

// TODO please add the wake word access key here.
const accessKey = "";
const _lucyFeedBack = {
  0: 'assets/audio/lucy/on_call/i_hear_you.wav',
  1: 'assets/audio/lucy/on_call/im_listening.wav',
  2: 'assets/audio/lucy/on_call/please_continue.wav',
  3: 'assets/audio/lucy/on_call/yes.wav'
};

void main() {
  try {
    SttWebSocket();
    TTSWebSocket();
  } catch (e) {
    debugPrint(e.toString());
  }

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  // This widget is the root of your application.
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Lucy Demo',
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
      ),
      home: const MyHomePage(title: 'Lucy Demo'),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({Key? key, required this.title}) : super(key: key);

  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  Random random = Random();
  late PorcupineManager _porcupineManager;
  final recorder = SoundRecorder();
  final player = SoundPlayer();
  final sttWebSocket = SttWebSocket();
  final ttsWebSocket = TTSWebSocket();
  late final Map<int, Uint8List?> lucyAudioData;
  late bool isRecording;
  late String userId;

  final StreamController _streamController = StreamController();
  String sttTranscription = 'The transcription will appear here.';
  String partialTranscription = 'What I am hearing';
  var _lucySays = 'Say something 🤗';
  final _textFieldController = TextEditingController();
  bool _isNameEntered = false;
  late String disconnectEvent;
  late String connectEvent;
  late String stopListeningEvent;

  StreamSubscription? _streamSubscriptionStream;

  @override
  void initState() {
    super.initState();
    createPorcupineManager();
    recorder.init();
    player.init();
    _streamController.addStream(sttWebSocket.channel.stream);
    isRecording = recorder.isRecording;
    convertWavToPmc();
  }

  @override
  Future<void> dispose() async {
    player.stopPlayer();
    recorder.dispose();
    player.dispose();
    sttWebSocket.closeSocket();
    ttsWebSocket.closeSocket();
    await _porcupineManager.delete();
    super.dispose();
  }

  /// Start receiving the data form the TTS service
  void recvTTS() {
    ttsWebSocket.channel.sink.add(connectEvent);
    ttsWebSocket.channel.stream.listen((event) async {
      if (event.runtimeType == String) {
        debugPrint(event);
      } else {
        final bytes = event as Uint8List;
        if (bytes.isNotEmpty) {
          setState(() {
            _lucySays = 'Talking... 💬';
          });
          await player.playFromWSStream(bytes, () async {
            await _porcupineManager.start();
            setState(() {
              _lucySays = 'Say something 🤗';
            });
          });
        }
      }
    }, onDone: () {
      debugPrint('WS server / channel closed');
    }, onError: (error) {
      debugPrint('ws error $error');
    });
  }

  /// Start receiving the data form the STT service
  void recvSTT() {
    sttWebSocket.channel.sink.add(connectEvent);
    sttWebSocket.channel.sink.add('{ "config" : { "sample_rate" : 16000 } }');
    if (!_streamController.isClosed && !_streamController.hasListener) {
      _streamSubscriptionStream =
          _streamController.stream.listen((event) async {
        Map<String, dynamic> data = jsonDecode(event);
        //Check if is transcription event
        if (data['event'] == 'response') {
          setState(() {
            sttTranscription = data['message'];
          });
        } else if (data['event'] == 'partial_response') {
          setState(() {
            partialTranscription = data['message'];
          });
        }
        // check if it is the last stream to cancel the stream
        else if (data['event'] == 'stopped_receiving') {
          sttWebSocket.channel.sink.add(stopListeningEvent);
          recorder.stop();
          setState(() {
            _lucySays = 'I\'m thinking 🤔';
          });
          setState(() {
            partialTranscription = '';
          });
          debugPrint('Stopped receiving.');
        }
      });
    }
  }

  //  For getting wav sound files form assets as bytes
  Future<Uint8List> getAssetData(String path) async {
    var asset = await rootBundle.load(path);
    return asset.buffer.asUint8List();
  }

  // For turning assets from wav to pmc and adding it to the "play list"
  void convertWavToPmc() async {
    lucyAudioData = {};
    for (var k in _lucyFeedBack.keys) {
      var pmc = FlutterSoundHelper().waveToPCMBuffer(
        inputBuffer: await getAssetData(_lucyFeedBack[k]!),
      );
      lucyAudioData[k] = pmc;
    }
  }

  /// Initiate the wake word engine
  Future<void> createPorcupineManager() async {
    // TODO: Please use your key here.
    String keywordAsset = "assets/";
    try {
      _porcupineManager = await PorcupineManager.fromKeywordPaths(
          accessKey, [keywordAsset], _wakeWordStartListening);
      try {
        await _porcupineManager.start();
      } on PorcupineException catch (ex) {
        debugPrint('A proplem occured! $ex');
        // deal with either audio exception
        debugPrint('$ex ${ex.message}');
      }
    } on PorcupineException catch (err) {
      debugPrint('$err ${err.message}');
    }
  }

  // Give a voice feedback and start listening to user voice
  Future<void> _wakeWordStartListening(int keywordIndex) async {
    _porcupineManager.stop();
    setState(() {
      _lucySays = 'I\'m listening 👂';
    });
    player.playAssets(lucyAudioData[random.nextInt(4)], () {
      debugPrint('Lucy is listening.');
    });
    setState(() {
      sttTranscription = '';
    });
    await Future.delayed(const Duration(seconds: 1));
    final recordingStream = await recorder.recordToStream();
    recordingStream.listen((event) {
      if (event is FoodData) {
        sttWebSocket.channel.sink.add(event.data);
      }
    }).onDone(() {
      debugPrint('Connection is down.');
    });
  }

  // a setter for messaging events with the backend services
  void setEvents(String id) {
    disconnectEvent =
        '''{"event":"disconnect", "user_id": "$id", "reason":"close connection"}''';

    connectEvent = '''{"event":"connect", "user_id": "$id"}''';

    stopListeningEvent = '''{"event":"stop_listening", "user_id": "$id"}''';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        centerTitle: true,
        title: Text(widget.title),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            _isNameEntered
                ? Padding(
                    padding: const EdgeInsets.all(8.0),
                    child: Text(
                      _lucySays,
                      style: const TextStyle(
                          color: Colors.green,
                          fontSize: 22,
                          fontWeight: FontWeight.bold),
                    ),
                  )
                : TextButton(
                    onPressed: () {
                      _displayTextInputDialog(context);
                    },
                    child:
                        const Text('Enter ID', style: TextStyle(fontSize: 24)),
                    style: TextButton.styleFrom(
                      minimumSize: const Size(50, 60),
                      primary: Colors.white,
                      backgroundColor: Colors.deepPurple,
                      onSurface: Colors.grey,
                    ),
                  ),
            const SizedBox(
              width: 500,
              height: 250,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _displayTextInputDialog(BuildContext context) async {
    return showDialog(
        context: context,
        builder: (context) {
          return AlertDialog(
            title: const Text('Please enter your id'),
            content: TextField(
              onChanged: (value) {
                setState(() {
                  userId = value;
                });
              },
              controller: _textFieldController,
              decoration: const InputDecoration(hintText: "Your id goes here."),
            ),
            actions: <Widget>[
              TextButton(
                  child: const Text('OK', style: TextStyle(fontSize: 24)),
                  style: TextButton.styleFrom(
                    minimumSize: const Size(50, 30),
                    primary: Colors.white,
                    backgroundColor: Colors.green,
                    onSurface: Colors.grey,
                  ),
                  onPressed: () {
                    if (_textFieldController.text.isNotEmpty) {
                      setState(() {
                        _isNameEntered = true;
                      });
                      setEvents(userId);
                      recvTTS();
                      recvSTT();
                      Navigator.pop(context);
                    }
                  })
            ],
          );
        });
  }
}

/////////////////////////////////////////////////////////////////t

/// We have a SoundRecorder and a SoundPlayer and a session.
/// We have to start a session before starting the player and the recorder.
/// We do it in the init state. And then we close it to release the resources.
/// We also have to save the audio file if we dont want to stream.

class SoundRecorder {
  FlutterSoundRecorder? _audioRecorder;
  bool _isRecorderInitialised = false;
  bool get isRecording => _audioRecorder!.isRecording;

  Future<void> init() async {
    _audioRecorder = FlutterSoundRecorder();

    final status = await Permission.microphone.request();
    if (status != PermissionStatus.granted) {
      throw RecordingPermissionException('Recording permission denied.');
    }
    _audioRecorder!.openRecorder();
    final session = await AudioSession.instance;
    await session.configure(AudioSessionConfiguration(
      avAudioSessionCategory: AVAudioSessionCategory.playAndRecord,
      avAudioSessionCategoryOptions:
          AVAudioSessionCategoryOptions.allowBluetooth |
              AVAudioSessionCategoryOptions.defaultToSpeaker,
      avAudioSessionMode: AVAudioSessionMode.spokenAudio,
      avAudioSessionRouteSharingPolicy:
          AVAudioSessionRouteSharingPolicy.defaultPolicy,
      avAudioSessionSetActiveOptions: AVAudioSessionSetActiveOptions.none,
      androidAudioAttributes: const AndroidAudioAttributes(
        contentType: AndroidAudioContentType.speech,
        flags: AndroidAudioFlags.none,
        usage: AndroidAudioUsage.voiceCommunication,
      ),
      androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
      androidWillPauseWhenDucked: true,
    ));
    _isRecorderInitialised = true;
  }

  Future<void> dispose() async {
    _audioRecorder!.closeRecorder();
    _audioRecorder = null;
    _isRecorderInitialised = false;
  }

  Future<Stream<Food>> recordToStream() async {
    StreamController<Food> recordingDataController = StreamController<Food>();
    await _audioRecorder!.startRecorder(
        codec: Codec.pcm16,
        toStream: recordingDataController.sink,
        sampleRate: 16000,
        numChannels: 1);
    return recordingDataController.stream;
  }

  Future<void> stop() async {
    if (!_isRecorderInitialised) return;
    await _audioRecorder!.stopRecorder();
  }

  Future<void> toggleRecording() async {
    if (_audioRecorder!.isStopped) {
      await recordToStream();
    } else {
      await stop();
    }
  }
}

class SoundPlayer {
  FlutterSoundPlayer? _mPlayer;
  bool busy = false;

  Future<void> init() async {
    _mPlayer = FlutterSoundPlayer();
    _mPlayer!.openPlayer();
  }

  void playAssets(Uint8List? data, void Function() func) async {
    await _mPlayer!
        .startPlayerFromStream(
          codec: Codec.pcm16,
          numChannels: 1,
          sampleRate: 22050,
        )
        .whenComplete(func);
    if (!busy) {
      await _mPlayer!.feedFromStream(data!).then((value) => busy = false);
    }
  }

  Future<void> playFromWSStream(
      Uint8List buffer, void Function() callback) async {
    await _mPlayer!.startPlayerFromStream(
      codec: Codec.pcm16,
      numChannels: 1,
      sampleRate: 22050,
    );
    _mPlayer!.feedFromStream(buffer).whenComplete(callback);
  }

  Future<void> stopPlayer() async {
    if (_mPlayer != null) {
      await _mPlayer!.stopPlayer();
    }
  }

  Future<void> dispose() async {
    _mPlayer!.closePlayer();
    _mPlayer = null;
  }
}

// Establishes the websocket connection with the STT service
class SttWebSocket {
  late final WebSocketChannel _channel;

  static final SttWebSocket _instance = SttWebSocket._internal();

  factory SttWebSocket() => _instance;

  // to connect to local android host use: http://10.0.2.2:8080
  SttWebSocket._internal() {
    _channel = IOWebSocketChannel.connect("ws");
  }

  WebSocketChannel get channel {
    return _channel;
  }

  void sendData(String msg) {
    _channel.sink.add(msg);
  }

  void closeSocket() {
    _channel.sink.close(1000, 'Socket is closed.');
  }
}

// Establishes the websocket connection with the TTS service
class TTSWebSocket {
  late final WebSocketChannel _channel;
  static final TTSWebSocket _instance = TTSWebSocket._internal();

  factory TTSWebSocket() => _instance;

  // to connect to local android host use: http://10.0.2.2:8080
  TTSWebSocket._internal() {
    _channel = IOWebSocketChannel.connect("");
  }

  WebSocketChannel get channel {
    return _channel;
  }

  void sendData(String msg) {
    _channel.sink.add(msg);
  }

  void closeSocket() {
    _channel.sink.close(1000, 'Socket is closed.');
  }
}
