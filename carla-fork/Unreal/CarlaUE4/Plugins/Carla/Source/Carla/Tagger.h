// Tagger.h  — CarlaSad fork patch
//
// Drop-in replacement for Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Tagger.h
// Adds GetColorForCarlaSadLabel() and extends tag lookup for labels 100–114.

#pragma once

#include "GameFramework/Actor.h"
#include "Carla/Sensor/SemanticSegmentationCamera.h"
#include "carla/rpc/ObjectLabel.h"
#include "Tagger.generated.h"

namespace crp = carla::rpc;

/// Maps folder names / actor class names to CityObjectLabel.
/// CarlaSad extension: handles agricultural terrain folder names.
UCLASS()
class CARLA_API ATagger : public AActor
{
  GENERATED_BODY()

public:

  // Tag every component of Actor with its semantic label.
  static void TagActor(const AActor &Actor, bool bTagForSemanticSegmentation);

  // Tag all actors in World.
  static void TagActorsInLevel(UWorld &World, bool bTagForSemanticSegmentation);

  // Retrieve the label of a tagged component (0 = None).
  static crp::CityObjectLabel GetLabelByTagValue(uint32 Tag);

  // Map a folder path segment (e.g. "NormalField") to a label.
  static crp::CityObjectLabel GetLabelByFolderName(const FString &String);

  // Returns a deterministic colour for a given semantic label.
  // Standard labels: same palette as upstream CARLA.
  // CarlaSad labels 100–114: distinct agricultural colour palette.
  static FColor GetColorForLabel(crp::CityObjectLabel Label);

  // Convenience: colour directly from tag value.
  static FColor GetColorForTag(uint32 Tag) {
    return GetColorForLabel(GetLabelByTagValue(Tag));
  }
};
