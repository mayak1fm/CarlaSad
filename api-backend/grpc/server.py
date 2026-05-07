"""
CarlaSad gRPC server.

Run alongside FastAPI (on separate port 50051).
Generated stubs: python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. carlasad.proto
"""
import asyncio
import time
import logging
import sys
from pathlib import Path

logger = logging.getLogger("carlasad.grpc")

try:
    import grpc
    from grpc import aio as grpc_aio
    # Import generated stubs (generated via protoc)
    from . import carlasad_pb2
    from . import carlasad_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    logger.warning("grpcio or generated stubs not available. Run: python -m grpc_tools.protoc ...")


if GRPC_AVAILABLE:
    class CarlaSadOperatorServicer(carlasad_pb2_grpc.CarlaSadOperatorServicer):
        """gRPC service implementation — delegates to same sim_controller as REST."""

        async def StartMission(self, request, context):
            from sim_controller import sim_controller
            from models.mission import MissionRequest
            req = MissionRequest(
                map_name=request.map_name or "CarlaSad/Field_Main",
                world_mode=request.world_mode or "editor",
                route_id=request.route_id or None,
                logging_mode=request.logging_mode or "online_debug",
                weather_preset=request.weather_preset or "ClearNoon",
                sensor_rig_profile=request.sensor_rig_profile or "default",
                seed=request.seed or 42,
            )
            try:
                mission_id = await sim_controller.start_mission(req)
                return carlasad_pb2.MissionResponse(ok=True, mission_id=mission_id)
            except Exception as e:
                return carlasad_pb2.MissionResponse(ok=False, error=str(e))

        async def StopMission(self, request, context):
            from sim_controller import sim_controller
            await sim_controller.stop_mission()
            return carlasad_pb2.MissionResponse(ok=True)

        async def GetMissionStatus(self, request, context):
            from models.mission import get_active_mission
            from sim_controller import sim_controller
            mission = get_active_mission()
            pose = sim_controller.get_ego_pose()
            return carlasad_pb2.MissionStatusResponse(
                state=mission.state,
                mission_id=mission.mission_id or "",
                progress=mission.progress,
                elapsed_seconds=mission.elapsed_seconds,
                ego_pose=carlasad_pb2.EgoPose(
                    x=pose.get("x", 0), y=pose.get("y", 0),
                    z=pose.get("z", 0), yaw=pose.get("yaw", 0),
                    vx=pose.get("vx", 0), vy=pose.get("vy", 0),
                ),
            )

        async def LoadWorld(self, request, context):
            from carla_client import carla_client
            await carla_client.ensure_connected()
            if carla_client.is_connected():
                carla_client.load_world(request.map_name)
                return carlasad_pb2.WorldResponse(ok=True)
            return carlasad_pb2.WorldResponse(ok=False, error="CARLA not connected")

        async def SetWeather(self, request, context):
            from carla_client import carla_client
            await carla_client.ensure_connected()
            carla_client.set_weather(request.preset)
            return carlasad_pb2.WorldResponse(ok=True)

        async def PlaySim(self, request, context):
            from sim_controller import sim_controller
            await sim_controller.resume_sim()
            return carlasad_pb2.SimResponse(ok=True, state="playing")

        async def PauseSim(self, request, context):
            from sim_controller import sim_controller
            await sim_controller.pause_sim()
            return carlasad_pb2.SimResponse(ok=True, state="paused")

        async def TickSim(self, request, context):
            from carla_client import carla_client
            frame = carla_client.tick()
            return carlasad_pb2.SimResponse(ok=True, frame=frame)

        async def StartRecording(self, request, context):
            import datetime, uuid
            session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            return carlasad_pb2.RecordingResponse(ok=True, session_id=session_id)

        async def StopRecording(self, request, context):
            return carlasad_pb2.RecordingResponse(ok=True)

        async def StreamState(self, request, context):
            """Server-side streaming: push SimStateUpdate every 100ms."""
            from models.mission import get_active_mission
            from sim_controller import sim_controller
            from carla_client import carla_client

            while not context.cancelled():
                mission = get_active_mission()
                pose = sim_controller.get_ego_pose()
                status = carla_client.get_status()

                yield carlasad_pb2.SimStateUpdate(
                    state=mission.state,
                    mission_id=mission.mission_id or "",
                    progress=mission.progress,
                    timestamp=time.time(),
                    ego_pose=carlasad_pb2.EgoPose(
                        x=pose.get("x", 0), y=pose.get("y", 0),
                        z=pose.get("z", 0), yaw=pose.get("yaw", 0),
                    ),
                    carla=carlasad_pb2.CarlaStatus(
                        connected=status.get("connected", False),
                        map=status.get("map", ""),
                        synchronous=status.get("synchronous_mode", False),
                    ),
                )
                await asyncio.sleep(0.1)


async def serve(port: int = 50051):
    if not GRPC_AVAILABLE:
        logger.error("gRPC not available. Install: pip install grpcio grpcio-tools")
        return

    server = grpc_aio.server()
    carlasad_pb2_grpc.add_CarlaSadOperatorServicer_to_server(
        CarlaSadOperatorServicer(), server
    )
    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)
    await server.start()
    logger.info("gRPC server listening on %s", listen_addr)

    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        await server.stop(grace=5)


def generate_stubs():
    """Generate Python stubs from .proto file."""
    import subprocess
    proto_dir = Path(__file__).parent
    result = subprocess.run(
        [
            sys.executable, "-m", "grpc_tools.protoc",
            f"-I{proto_dir}",
            f"--python_out={proto_dir}",
            f"--grpc_python_out={proto_dir}",
            str(proto_dir / "carlasad.proto"),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("protoc error:", result.stderr)
    else:
        print("Stubs generated successfully")


if __name__ == "__main__":
    if "--gen-stubs" in sys.argv:
        generate_stubs()
    else:
        asyncio.run(serve())
