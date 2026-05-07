// ObjectLabel.h  — CarlaSad fork of LibCarla/source/carla/rpc/ObjectLabel.h
//
// Adds terrain semantic labels 100–114 for agricultural field simulation.
// Original CARLA labels 0–30 are preserved unchanged.

#pragma once

#include <cstdint>

namespace carla {
namespace rpc {

  enum class CityObjectLabel : uint8_t {
    None            =   0u,
    // ── Standard CARLA labels (0.9.15) ─────────────────────────────────────
    Buildings       =   1u,
    Fences          =   2u,
    Other           =   3u,
    Pedestrians     =   4u,
    Poles           =   5u,
    RoadLines       =   6u,
    Roads           =   7u,
    Sidewalks       =   8u,
    Vegetation      =   9u,
    Vehicles        =  10u,
    Walls           =  11u,
    TrafficSigns    =  12u,
    Sky             =  13u,
    Ground          =  14u,
    Bridge          =  15u,
    RailTrack       =  16u,
    GuardRail       =  17u,
    TrafficLight    =  18u,
    Static          =  19u,
    Dynamic         =  20u,
    Water           =  21u,
    Terrain         =  22u,
    // ── CarlaSad agricultural terrain labels ───────────────────────────────
    NormalField     = 100u,  // dry / normal arable field
    WetField        = 101u,  // waterlogged but trafficable field
    Swamp           = 102u,  // swamp — very high traversal risk
    Mochak          = 103u,  // mochak (boggy depression with rushes)
    RoughTerrain    = 104u,  // rough terrain with ruts / stones
    FieldBoundary   = 105u,  // field edge / fence / tree line
    DrivablePath    = 106u,  // farm track — drivable at normal speed
    NonDrivable     = 107u,  // ditch / obstacle — do not enter
    // 108–109 reserved
    WorkedArea      = 110u,  // already processed (tilled / sown)
    UnworkedArea    = 111u,  // not yet processed
    WorkedEdge      = 112u,  // boundary between worked / unworked
    ActiveWorkZone  = 113u,  // tractor is currently working here
    RestrictedZone  = 114u,  // exclusion zone (hazard / crop damage)

    ANY             = 0xFFu
  };

  inline bool IsCarlaSadLabel(CityObjectLabel label) {
    const uint8_t id = static_cast<uint8_t>(label);
    return id >= 100u && id <= 114u;
  }

} // namespace rpc
} // namespace carla
