// CarlaSadTractorVehicle.h
//
// Tractor vehicle actor for CarlaSad.
// Extends ACarlaWheeledVehicle with:
//   - Implement attachment point (rear PTO link)
//   - Work status tracking (working / transport / idle)
//   - Terrain-aware speed governor (reads current surface label)
//   - Articulation angle for steering (optional front-wheel steering model)
//
// Blueprint class: Content/CarlaSad/Vehicles/Tractor/BP_CarlaSadTractor.uasset
// Vehicle config:  Content/CarlaSad/Vehicles/Tractor/TractorVehicleData.json

#pragma once

#include "Vehicle/CarlaWheeledVehicle.h"
#include "CarlaSadTractorVehicle.generated.h"

UENUM(BlueprintType)
enum class ETractorWorkStatus : uint8
{
    Idle        UMETA(DisplayName = "Idle"),
    Transport   UMETA(DisplayName = "Transport"),
    Working     UMETA(DisplayName = "Working"),
    Emergency   UMETA(DisplayName = "Emergency"),
};

UCLASS()
class CARLA_API ACarlaSadTractorVehicle : public ACarlaWheeledVehicle
{
    GENERATED_BODY()

public:
    ACarlaSadTractorVehicle(const FObjectInitializer& ObjectInitializer);

    // ── Work state ──────────────────────────────────────────────────────────

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Tractor")
    ETractorWorkStatus WorkStatus = ETractorWorkStatus::Idle;

    UFUNCTION(BlueprintCallable, Category = "CarlaSad|Tractor")
    void SetWorkStatus(ETractorWorkStatus NewStatus);

    UFUNCTION(BlueprintPure, Category = "CarlaSad|Tractor")
    ETractorWorkStatus GetWorkStatus() const { return WorkStatus; }

    // ── Implement attachment (PTO / rear linkage) ───────────────────────────

    // World-space transform of the rear 3-point hitch attachment point.
    UFUNCTION(BlueprintPure, Category = "CarlaSad|Tractor")
    FTransform GetImplementAttachTransform() const;

    // ── Speed governor ──────────────────────────────────────────────────────

    // Max speed in current terrain class (m/s). Updated per tick.
    UPROPERTY(BlueprintReadOnly, Category = "CarlaSad|Tractor")
    float CurrentMaxSpeedMps = 10.0f;

    // If true, throttle is auto-clamped to respect CurrentMaxSpeedMps.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Tractor")
    bool bEnableTerrainSpeedGovernor = true;

    // ── Implement lift angle (0 = ground, 1 = fully raised) ────────────────

    UPROPERTY(EditAnywhere, BlueprintReadWrite,
              Category = "CarlaSad|Tractor",
              meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float ImplementLiftFraction = 0.0f;

    // ── Worked area reporting ───────────────────────────────────────────────

    // Width of the working implement in meters (used by ProcessLayer).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "CarlaSad|Tractor")
    float ImplementWidthM = 3.0f;

    // Returns true if the implement is lowered and tractor is in Working state.
    UFUNCTION(BlueprintPure, Category = "CarlaSad|Tractor")
    bool IsActivelyWorking() const {
        return WorkStatus == ETractorWorkStatus::Working
               && ImplementLiftFraction < 0.1f;
    }

    void Tick(float DeltaTime) override;

protected:
    void BeginPlay() override;

private:
    // Scene component marking rear PTO attachment point (set in Blueprint)
    UPROPERTY(VisibleAnywhere, Category = "CarlaSad|Tractor")
    USceneComponent* ImplementAttachPoint = nullptr;

    // Speed governor: clamp throttle if over terrain speed limit
    void ApplyTerrainSpeedGovernor(float DeltaTime);

    // Current semantic label under tractor (updated at 2 Hz)
    uint8 CurrentTerrainLabel = 100u;   // NormalField default
    float TerrainLabelTimer = 0.0f;
    static constexpr float TerrainLabelUpdateInterval = 0.5f;

    void UpdateTerrainLabel();
};
