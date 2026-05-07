// ThermalCamera.h  — CarlaSad custom thermal infrared camera sensor
//
// Simulates LWIR thermal camera (8–14 μm band).
// Output: 16-bit grayscale — pixel value = temperature in Kelvin × 10
//
// Integration into CARLA fork:
//   1. Add ThermalCamera.h/.cpp to Carla.Build.cs PrivateIncludePaths
//   2. Register in SensorFactory.cpp (see carlasad patch)
//   3. Add M_ThermalOverlay material to Content/CarlaSad/Materials/
//   4. Python: world.get_blueprint_library().find('sensor.camera.thermal')

#pragma once

#include "Carla/Sensor/SceneCaptureSensor.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Components/SceneCaptureComponent2D.h"
#include "ThermalCamera.generated.h"

UCLASS()
class CARLA_API AThermalCamera : public ASceneCaptureSensor
{
    GENERATED_BODY()

public:
    AThermalCamera(const FObjectInitializer& ObjectInitializer);

    static FActorDefinition GetSensorDefinition();

    void Set(const FActorDescription& ActorDescription) override;
    void PostPhysTick(UWorld* World, ELevelTick TickType, float DeltaSeconds) override;

    // ── Configurable parameters ─────────────────────────────────────────────

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    float MinTemperatureK = 250.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    float MaxTemperatureK = 400.0f;

    // NETD — noise equivalent temperature difference (K)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    float NoiseSigmaK = 0.05f;

    // Global emissivity override. 0 = use per-class defaults.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    float EmissivityOverride = 0.0f;

    // Per-material emissivity map (material slot name → 0–1)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Thermal")
    TMap<FString, float> EmissivityMap;

protected:
    void BeginPlay() override;

private:
    // Creates ThermalRT and ThermalCapture scene capture component
    void SetupThermalRenderTarget();

    // Main render entry — chooses hardware or software path
    void RenderThermalImage();

    // Software path: reads SemanticBuffer (parent stencil pass) → maps per label
    void RenderFromSemanticBuffer(uint16* OutData, uint32 NumPixels);

    // Hardware path: decodes M_ThermalOverlay output from ThermalRT
    void ConvertRGBAToThermal16(const TArray<FColor>& Pixels,
                                uint16* OutData, uint32 NumPixels);

    // Per-pixel temperature from semantic label + surface emissivity
    float EstimateTemperature(uint8 SemanticLabel, float SurfaceEmissivity) const;

    // Scene capture for thermal overlay render
    UPROPERTY()
    USceneCaptureComponent2D* ThermalCapture = nullptr;

    UPROPERTY()
    UTextureRenderTarget2D* ThermalRT = nullptr;

    // Semantic pixel buffer: R channel = semantic stencil ID, populated by parent
    TArray<FColor> SemanticBuffer;
};
