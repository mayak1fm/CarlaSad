// ThermalCamera.cpp
// CarlaSad thermal camera sensor implementation.
//
// P1 implementation: uses semantic segmentation pass as input,
// maps each semantic class to an estimated temperature range,
// adds configurable thermal noise (NETD simulation).
//
// TODO P2: real PBR-based thermal simulation using material emissivity
//           and scene thermal equilibrium model.

#include "Carla/Sensor/ThermalCamera.h"
#include "Carla/Actor/ActorBlueprintFunctionLibrary.h"
#include "Carla/Sensor/PixelReader.h"
#include "Runtime/RenderCore/Public/RenderingThread.h"

// Semantic label → approximate temperature (Kelvin)
static const TMap<uint8, float> SEMANTIC_TEMP_K = {
    {0,   288.0f},   // unlabeled
    {4,   310.0f},   // person (body temp)
    {6,   282.0f},   // vegetation
    {7,   288.0f},   // terrain
    {8,   295.0f},   // road
    {9,   290.0f},   // sidewalk
    {10,  330.0f},   // vehicle (engine heat)
    {100, 288.0f},   // normal_field
    {101, 284.0f},   // wet_field (evaporative cooling)
    {102, 280.0f},   // swamp (wet = cool)
    {103, 281.0f},   // mochak
    {104, 289.0f},   // rough_terrain
    {110, 287.0f},   // worked_area (disturbed soil)
    {111, 288.0f},   // unworked_area
};

FActorDefinition AThermalCamera::GetSensorDefinition()
{
    auto Definition = UActorBlueprintFunctionLibrary::MakeCameraDefinition(TEXT("thermal"));
    Definition.Id = TEXT("sensor.camera.thermal");

    FActorVariation MinTemp;
    MinTemp.Id = TEXT("min_temperature_k");
    MinTemp.Type = EActorAttributeType::Float;
    MinTemp.RecommendedValues = {TEXT("250.0")};
    Definition.Variations.Emplace(MinTemp);

    FActorVariation MaxTemp;
    MaxTemp.Id = TEXT("max_temperature_k");
    MaxTemp.Type = EActorAttributeType::Float;
    MaxTemp.RecommendedValues = {TEXT("400.0")};
    Definition.Variations.Emplace(MaxTemp);

    FActorVariation Noise;
    Noise.Id = TEXT("noise_sigma_k");
    Noise.Type = EActorAttributeType::Float;
    Noise.RecommendedValues = {TEXT("0.05")};
    Definition.Variations.Emplace(Noise);

    return Definition;
}

AThermalCamera::AThermalCamera(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
}

void AThermalCamera::Set(const FActorDescription& Description)
{
    Super::Set(Description);
    UActorBlueprintFunctionLibrary::SetCamera(Description, this);
    MinTemperatureK = UActorBlueprintFunctionLibrary::RetrieveActorAttributeToFloat(
        TEXT("min_temperature_k"), Description.Variations, 250.0f);
    MaxTemperatureK = UActorBlueprintFunctionLibrary::RetrieveActorAttributeToFloat(
        TEXT("max_temperature_k"), Description.Variations, 400.0f);
    NoiseSigmaK = UActorBlueprintFunctionLibrary::RetrieveActorAttributeToFloat(
        TEXT("noise_sigma_k"), Description.Variations, 0.05f);
}

void AThermalCamera::BeginPlay()
{
    Super::BeginPlay();
}

void AThermalCamera::PostPhysTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
    Super::PostPhysTick(World, TickType, DeltaSeconds);
    RenderThermalImage();
}

void AThermalCamera::RenderThermalImage()
{
    // Read semantic buffer (set by parent SceneCaptureSensor)
    // Convert each pixel semantic label → temperature → 16-bit value
    // Send via carla::Buffer to Python bridge
    // Full implementation requires CARLA FPixelReader integration
}

float AThermalCamera::EstimateTemperature(uint8 SemanticLabel, float SurfaceEmissivity) const
{
    const float* BaseTemp = SEMANTIC_TEMP_K.Find(SemanticLabel);
    float Temp = BaseTemp ? *BaseTemp : 288.0f;

    // Scale by emissivity (lower emissivity = lower apparent temperature)
    Temp = MinTemperatureK + (Temp - MinTemperatureK) * SurfaceEmissivity;

    // Add noise (NETD simulation)
    if (NoiseSigmaK > 0.0f)
    {
        Temp += FMath::RandRange(-NoiseSigmaK * 3.0f, NoiseSigmaK * 3.0f);
    }

    return FMath::Clamp(Temp, MinTemperatureK, MaxTemperatureK);
}
