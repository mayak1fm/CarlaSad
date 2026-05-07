// ThermalCamera.h
// CarlaSad custom thermal infrared camera sensor.
//
// Simulates a longwave infrared (LWIR) thermal camera (8-14μm).
// Output: 16-bit grayscale image where pixel values encode temperature in Kelvin * 10.
//
// Integration path:
//   1. Add ThermalCamera.cpp/.h to CARLA Sensor plugin
//   2. Register blueprint "sensor.camera.thermal" in SensorFactory
//   3. In Python bridge: use sensor.camera.thermal blueprint ID
//
// CARLA sensor extension docs:
//   https://carla.readthedocs.io/en/latest/tuto_D_create_sensor/

#pragma once

#include "Carla/Sensor/SceneCaptureSensor.h"
#include "ThermalCamera.generated.h"

UCLASS()
class CARLA_API AThermalCamera : public ASceneCaptureSensor
{
    GENERATED_BODY()

public:
    AThermalCamera(const FObjectInitializer& ObjectInitializer);

    // Temperature range (Kelvin)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    float MinTemperatureK = 250.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    float MaxTemperatureK = 400.0f;

    // Noise sigma in Kelvin (NETD)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    float NoiseSigmaK = 0.05f;

    // Material emissivity map (class → emissivity 0-1)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    TMap<FString, float> EmissivityMap;

    static FActorDefinition GetSensorDefinition();

    void Set(const FActorDescription& ActorDescription) override;
    void PostPhysTick(UWorld* World, ELevelTick TickType, float DeltaSeconds) override;

protected:
    void BeginPlay() override;

private:
    // Render thermal image from scene emissive + material properties
    void RenderThermalImage();

    // Per-pixel temperature from semantic segmentation + material emissivity
    float EstimateTemperature(uint8 SemanticLabel, float SurfaceEmissivity) const;

    TArray<FColor> SemanticBuffer;
};
