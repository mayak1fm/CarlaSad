/// CarlaSad Operator API — Dart reference client
///
/// Covers: REST, WebSocket state stream, WebSocket events.
/// gRPC stub generation: see pubspec.yaml → protoc + grpc-dart plugin.
///
/// Usage:
///   final client = CarlaSadClient(host: "localhost", port: 8080);
///   await client.connect();
///   final id = await client.startMission(MissionRequest(mapName: "Town01"));
///   client.stateStream.listen((s) => print(s.egoPose));

import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

// ── Data models ──────────────────────────────────────────────────────────────

class MissionRequest {
  final String mapName;
  final String worldMode;
  final String weatherPreset;
  final String loggingMode;
  final String sensorRigProfile;
  final int seed;

  const MissionRequest({
    required this.mapName,
    this.worldMode      = "editor",
    this.weatherPreset  = "ClearNoon",
    this.loggingMode    = "online_debug",
    this.sensorRigProfile = "full",
    this.seed           = 42,
  });

  Map<String, dynamic> toJson() => {
    "map_name":           mapName,
    "world_mode":         worldMode,
    "weather_preset":     weatherPreset,
    "logging_mode":       loggingMode,
    "sensor_rig_profile": sensorRigProfile,
    "seed":               seed,
  };
}

class EgoPose {
  final double x, y, z, yaw, vx, vy;
  const EgoPose({required this.x, required this.y, required this.z,
                 required this.yaw, required this.vx, required this.vy});

  factory EgoPose.fromJson(Map<String, dynamic> j) => EgoPose(
    x: (j["x"] as num).toDouble(),
    y: (j["y"] as num).toDouble(),
    z: (j["z"] as num).toDouble(),
    yaw: (j["yaw"] as num).toDouble(),
    vx: (j["vx"] as num).toDouble(),
    vy: (j["vy"] as num).toDouble(),
  );
}

class SimState {
  final double timestamp;
  final String missionState;
  final EgoPose? egoPose;

  const SimState({required this.timestamp, required this.missionState, this.egoPose});

  factory SimState.fromJson(Map<String, dynamic> j) => SimState(
    timestamp:     (j["ts"] as num).toDouble(),
    missionState:  j["mission"]?["state"] ?? "idle",
    egoPose:       j["ego_pose"] != null ? EgoPose.fromJson(j["ego_pose"]) : null,
  );
}

// ── Client ───────────────────────────────────────────────────────────────────

class CarlaSadClient {
  final String host;
  final int port;

  late final String _base;
  late final String _wsBase;

  WebSocketChannel? _stateChannel;
  WebSocketChannel? _eventsChannel;

  final _stateController  = StreamController<SimState>.broadcast();
  final _eventsController = StreamController<Map<String, dynamic>>.broadcast();

  Stream<SimState>              get stateStream  => _stateController.stream;
  Stream<Map<String, dynamic>>  get eventsStream => _eventsController.stream;

  CarlaSadClient({this.host = "localhost", this.port = 8080}) {
    _base   = "http://$host:$port";
    _wsBase = "ws://$host:$port";
  }

  // ── REST helpers ──────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> _get(String path) async {
    final r = await http.get(Uri.parse("$_base$path"));
    _checkStatus(r);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> _post(String path, [Object? body]) async {
    final r = await http.post(
      Uri.parse("$_base$path"),
      headers: {"Content-Type": "application/json"},
      body: body != null ? jsonEncode(body) : null,
    );
    _checkStatus(r);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  void _checkStatus(http.Response r) {
    if (r.statusCode >= 400) {
      throw CarlaSadApiException(r.statusCode, r.body);
    }
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────

  void connectStateStream() {
    _stateChannel = WebSocketChannel.connect(Uri.parse("$_wsBase/ws/state"));
    _stateChannel!.stream.listen(
      (raw) {
        final j = jsonDecode(raw as String) as Map<String, dynamic>;
        _stateController.add(SimState.fromJson(j));
      },
      onError: (e) => _stateController.addError(e),
    );
  }

  void connectEventsStream() {
    _eventsChannel = WebSocketChannel.connect(Uri.parse("$_wsBase/ws/events"));
    _eventsChannel!.stream.listen(
      (raw) {
        final j = jsonDecode(raw as String) as Map<String, dynamic>;
        _eventsController.add(j);
      },
      onError: (e) => _eventsController.addError(e),
    );
  }

  void sendEventsPing() {
    _eventsChannel?.sink.add(jsonEncode({"type": "ping"}));
  }

  void disconnect() {
    _stateChannel?.sink.close();
    _eventsChannel?.sink.close();
  }

  // ── Mission API ───────────────────────────────────────────────────────────

  Future<String> startMission(MissionRequest req) async {
    final r = await _post("/api/v1/mission/start", req.toJson());
    return r["mission_id"] as String;
  }

  Future<void> stopMission() => _post("/api/v1/mission/stop");

  Future<Map<String, dynamic>> getMissionStatus() => _get("/api/v1/mission/status");

  // ── World API ─────────────────────────────────────────────────────────────

  Future<void> loadWorld(String mapName, {String mode = "editor"}) =>
      _post("/api/v1/world/load", {"map_name": mapName, "mode": mode});

  Future<void> setWeather(String preset) =>
      _post("/api/v1/world/weather", {"preset": preset});

  // ── Sim control ───────────────────────────────────────────────────────────

  Future<void> play()  => _post("/api/v1/sim/play");
  Future<void> pause() => _post("/api/v1/sim/pause");

  Future<int> tick() async {
    final r = await _post("/api/v1/sim/tick");
    return r["frame_id"] as int? ?? 0;
  }

  Future<void> enterPassiveTick({double deltaSeconds = 0.05}) =>
      _post("/api/v1/sim/passive-tick/enter?fixed_delta_seconds=$deltaSeconds");

  Future<void> exitPassiveTick() => _post("/api/v1/sim/passive-tick/exit");

  // ── Recording API ─────────────────────────────────────────────────────────

  Future<void> startRecording(String sessionName) =>
      _post("/api/v1/recording/start", {"session_name": sessionName});

  Future<void> stopRecording() => _post("/api/v1/recording/stop");

  // ── Health ────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> health() => _get("/health");
}

// ── Exception ────────────────────────────────────────────────────────────────

class CarlaSadApiException implements Exception {
  final int statusCode;
  final String body;
  CarlaSadApiException(this.statusCode, this.body);

  @override
  String toString() => "CarlaSadApiException($statusCode): $body";
}

// ── Usage example ────────────────────────────────────────────────────────────

Future<void> main() async {
  final client = CarlaSadClient(host: "localhost", port: 8080);

  // Check health
  final h = await client.health();
  print("Health: $h");

  // Connect WebSocket streams
  client.connectStateStream();
  client.connectEventsStream();

  client.stateStream.listen((state) {
    print("[state] mission=${state.missionState} "
          "pos=(${state.egoPose?.x.toStringAsFixed(1)}, "
          "${state.egoPose?.y.toStringAsFixed(1)})");
  });

  client.eventsStream.listen((event) {
    print("[event] ${event["event_type"]} — ${event["payload"]}");
  });

  // Start mission
  final missionId = await client.startMission(const MissionRequest(
    mapName:      "CarlaSad_Field_01",
    loggingMode:  "online_debug",
    weatherPreset: "ClearNoon",
  ));
  print("Mission started: $missionId");

  // Drive 10 passive ticks from Dart
  await client.enterPassiveTick(deltaSeconds: 0.05);
  for (int i = 0; i < 10; i++) {
    final frame = await client.tick();
    print("Ticked frame $frame");
    await Future.delayed(const Duration(milliseconds: 50));
  }
  await client.exitPassiveTick();

  // Stop
  await client.stopMission();
  client.disconnect();
}
