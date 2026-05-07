// Tagger.cpp  — CarlaSad fork patch
//
// Extends the standard CARLA Tagger with agricultural terrain labels (100–114).
// Sections marked "CarlaSad" are additions; everything else mirrors upstream 0.9.15.

#include "Carla/Tagger.h"
#include "Carla/Util/ActorWithRandomEngine.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"

// ── Label lookup ──────────────────────────────────────────────────────────────

crp::CityObjectLabel ATagger::GetLabelByFolderName(const FString &String)
{
  // Standard CARLA labels
  if (String == "Building")        return crp::CityObjectLabel::Buildings;
  if (String == "Fence")           return crp::CityObjectLabel::Fences;
  if (String == "Pedestrian")      return crp::CityObjectLabel::Pedestrians;
  if (String == "Pole")            return crp::CityObjectLabel::Poles;
  if (String == "RoadLine")        return crp::CityObjectLabel::RoadLines;
  if (String == "Road")            return crp::CityObjectLabel::Roads;
  if (String == "Sidewalk")        return crp::CityObjectLabel::Sidewalks;
  if (String == "Vegetation")      return crp::CityObjectLabel::Vegetation;
  if (String == "Car"  ||
      String == "Vehicle" ||
      String == "Tractor")         return crp::CityObjectLabel::Vehicles;
  if (String == "Wall")            return crp::CityObjectLabel::Walls;
  if (String == "TrafficSign")     return crp::CityObjectLabel::TrafficSigns;
  if (String == "Sky")             return crp::CityObjectLabel::Sky;
  if (String == "Ground")          return crp::CityObjectLabel::Ground;
  if (String == "Bridge")          return crp::CityObjectLabel::Bridge;
  if (String == "RailTrack")       return crp::CityObjectLabel::RailTrack;
  if (String == "GuardRail")       return crp::CityObjectLabel::GuardRail;
  if (String == "TrafficLight")    return crp::CityObjectLabel::TrafficLight;
  if (String == "Static")          return crp::CityObjectLabel::Static;
  if (String == "Dynamic")         return crp::CityObjectLabel::Dynamic;
  if (String == "Water")           return crp::CityObjectLabel::Water;
  if (String == "Terrain")         return crp::CityObjectLabel::Terrain;

  // ── CarlaSad agricultural terrain labels ───────────────────────────────────
  if (String == "NormalField")     return crp::CityObjectLabel::NormalField;
  if (String == "WetField")        return crp::CityObjectLabel::WetField;
  if (String == "Swamp")           return crp::CityObjectLabel::Swamp;
  if (String == "Mochak")          return crp::CityObjectLabel::Mochak;
  if (String == "RoughTerrain")    return crp::CityObjectLabel::RoughTerrain;
  if (String == "FieldBoundary")   return crp::CityObjectLabel::FieldBoundary;
  if (String == "DrivablePath")    return crp::CityObjectLabel::DrivablePath;
  if (String == "NonDrivable")     return crp::CityObjectLabel::NonDrivable;
  if (String == "WorkedArea")      return crp::CityObjectLabel::WorkedArea;
  if (String == "UnworkedArea")    return crp::CityObjectLabel::UnworkedArea;
  if (String == "WorkedEdge")      return crp::CityObjectLabel::WorkedEdge;
  if (String == "ActiveWorkZone")  return crp::CityObjectLabel::ActiveWorkZone;
  if (String == "RestrictedZone")  return crp::CityObjectLabel::RestrictedZone;

  return crp::CityObjectLabel::None;
}

crp::CityObjectLabel ATagger::GetLabelByTagValue(uint32 Tag)
{
  const uint8 Id = static_cast<uint8>(Tag);
  switch (Id)
  {
    case   1: return crp::CityObjectLabel::Buildings;
    case   2: return crp::CityObjectLabel::Fences;
    case   3: return crp::CityObjectLabel::Other;
    case   4: return crp::CityObjectLabel::Pedestrians;
    case   5: return crp::CityObjectLabel::Poles;
    case   6: return crp::CityObjectLabel::RoadLines;
    case   7: return crp::CityObjectLabel::Roads;
    case   8: return crp::CityObjectLabel::Sidewalks;
    case   9: return crp::CityObjectLabel::Vegetation;
    case  10: return crp::CityObjectLabel::Vehicles;
    case  11: return crp::CityObjectLabel::Walls;
    case  12: return crp::CityObjectLabel::TrafficSigns;
    case  13: return crp::CityObjectLabel::Sky;
    case  14: return crp::CityObjectLabel::Ground;
    case  15: return crp::CityObjectLabel::Bridge;
    case  16: return crp::CityObjectLabel::RailTrack;
    case  17: return crp::CityObjectLabel::GuardRail;
    case  18: return crp::CityObjectLabel::TrafficLight;
    case  19: return crp::CityObjectLabel::Static;
    case  20: return crp::CityObjectLabel::Dynamic;
    case  21: return crp::CityObjectLabel::Water;
    case  22: return crp::CityObjectLabel::Terrain;
    // CarlaSad
    case 100: return crp::CityObjectLabel::NormalField;
    case 101: return crp::CityObjectLabel::WetField;
    case 102: return crp::CityObjectLabel::Swamp;
    case 103: return crp::CityObjectLabel::Mochak;
    case 104: return crp::CityObjectLabel::RoughTerrain;
    case 105: return crp::CityObjectLabel::FieldBoundary;
    case 106: return crp::CityObjectLabel::DrivablePath;
    case 107: return crp::CityObjectLabel::NonDrivable;
    case 110: return crp::CityObjectLabel::WorkedArea;
    case 111: return crp::CityObjectLabel::UnworkedArea;
    case 112: return crp::CityObjectLabel::WorkedEdge;
    case 113: return crp::CityObjectLabel::ActiveWorkZone;
    case 114: return crp::CityObjectLabel::RestrictedZone;
    default:  return crp::CityObjectLabel::None;
  }
}

// ── Colour palette ────────────────────────────────────────────────────────────

FColor ATagger::GetColorForLabel(crp::CityObjectLabel Label)
{
  switch (Label)
  {
    // Standard CARLA palette (matches upstream 0.9.15 exactly)
    case crp::CityObjectLabel::Buildings:     return FColor( 70,  70,  70);
    case crp::CityObjectLabel::Fences:        return FColor(100,  40,  40);
    case crp::CityObjectLabel::Other:         return FColor( 55,  90,  80);
    case crp::CityObjectLabel::Pedestrians:   return FColor(220,  20,  60);
    case crp::CityObjectLabel::Poles:         return FColor(153, 153, 153);
    case crp::CityObjectLabel::RoadLines:     return FColor(157, 234,  50);
    case crp::CityObjectLabel::Roads:         return FColor(128,  64, 255);
    case crp::CityObjectLabel::Sidewalks:     return FColor(244,  35, 232);
    case crp::CityObjectLabel::Vegetation:    return FColor(107, 142,  35);
    case crp::CityObjectLabel::Vehicles:      return FColor(  0,   0, 142);
    case crp::CityObjectLabel::Walls:         return FColor(102, 102, 156);
    case crp::CityObjectLabel::TrafficSigns:  return FColor(220, 220,   0);
    case crp::CityObjectLabel::Sky:           return FColor( 70, 130, 180);
    case crp::CityObjectLabel::Ground:        return FColor( 81,   0,  81);
    case crp::CityObjectLabel::Bridge:        return FColor(150, 100, 100);
    case crp::CityObjectLabel::RailTrack:     return FColor(230, 150, 140);
    case crp::CityObjectLabel::GuardRail:     return FColor(180, 165, 180);
    case crp::CityObjectLabel::TrafficLight:  return FColor(250, 170,  30);
    case crp::CityObjectLabel::Static:        return FColor(110, 190, 160);
    case crp::CityObjectLabel::Dynamic:       return FColor(170, 120,  50);
    case crp::CityObjectLabel::Water:         return FColor( 45,  60, 150);
    case crp::CityObjectLabel::Terrain:       return FColor(145, 170, 100);

    // ── CarlaSad agricultural terrain palette ─────────────────────────────────
    // Colours chosen for clear visual distinction in the semantic camera output.
    case crp::CityObjectLabel::NormalField:    return FColor(180, 210, 100); // light yellow-green
    case crp::CityObjectLabel::WetField:       return FColor( 80, 140, 200); // medium blue
    case crp::CityObjectLabel::Swamp:          return FColor( 30,  80,  50); // dark swamp green
    case crp::CityObjectLabel::Mochak:         return FColor( 60, 100,  40); // olive bog
    case crp::CityObjectLabel::RoughTerrain:   return FColor(140, 120,  80); // brown rough
    case crp::CityObjectLabel::FieldBoundary:  return FColor(220, 180,  60); // amber edge
    case crp::CityObjectLabel::DrivablePath:   return FColor(200, 200, 200); // light grey track
    case crp::CityObjectLabel::NonDrivable:    return FColor(180,  40,  40); // red danger
    case crp::CityObjectLabel::WorkedArea:     return FColor(120,  80,  40); // dark tilled brown
    case crp::CityObjectLabel::UnworkedArea:   return FColor(200, 190, 140); // pale straw
    case crp::CityObjectLabel::WorkedEdge:     return FColor(255, 140,   0); // orange edge
    case crp::CityObjectLabel::ActiveWorkZone: return FColor(255, 255,   0); // bright yellow
    case crp::CityObjectLabel::RestrictedZone: return FColor(255,   0, 255); // magenta exclusion

    default: return FColor(0, 0, 0);
  }
}

// ── Actor tagging ─────────────────────────────────────────────────────────────

void ATagger::TagActor(const AActor &Actor, bool bTagForSemanticSegmentation)
{
  // Walk the folder path of the actor's asset and extract the label.
  // Pattern: Content/Static/NormalField/SM_FieldTile.uasset → NormalField
  FString AssetPath = Actor.GetClass()->GetPathName();
  TArray<FString> Parts;
  AssetPath.ParseIntoArray(Parts, TEXT("/"), true);

  crp::CityObjectLabel Label = crp::CityObjectLabel::None;
  for (const FString &Part : Parts)
  {
    Label = GetLabelByFolderName(Part);
    if (Label != crp::CityObjectLabel::None)
      break;
  }

  if (!bTagForSemanticSegmentation)
    return;

  const uint32 TagValue = static_cast<uint32>(Label);
  TArray<UPrimitiveComponent*> Components;
  Actor.GetComponents<UPrimitiveComponent>(Components);
  for (UPrimitiveComponent *Component : Components)
  {
    if (Component)
      Component->SetCustomDepthStencilValue(TagValue);
  }
}

void ATagger::TagActorsInLevel(UWorld &World, bool bTagForSemanticSegmentation)
{
  for (TActorIterator<AActor> It(&World); It; ++It)
  {
    TagActor(**It, bTagForSemanticSegmentation);
  }
}
