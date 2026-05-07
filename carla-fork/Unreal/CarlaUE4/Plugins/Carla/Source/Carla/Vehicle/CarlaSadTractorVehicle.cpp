// CarlaSadTractorVehicle.cpp

#include "Carla/Vehicle/CarlaSadTractorVehicle.h"
#include "Carla/Tagger.h"

#include "WheeledVehicleMovementComponent4W.h"
#include "Components/SceneComponent.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"
#include "DrawDebugHelpers.h"

// Per-label max speed table (m/s) — mirrors Python terrain_physics.py
static const TMap<uint8, float> TERRAIN_MAX_SPEED = {
    {100,  8.0f},  // NormalField
    {101,  5.0f},  // WetField
    {102,  2.5f},  // Swamp
    {103,  2.0f},  // Mochak
    {104,  4.0f},  // RoughTerrain
    {105,  3.0f},  // FieldBoundary
    {106, 10.0f},  // DrivablePath
    {107,  1.5f},  // NonDrivable
    {110,  6.0f},  // WorkedArea
    {111,  7.0f},  // UnworkedArea
};

// ── Constructor ───────────────────────────────────────────────────────────────

ACarlaSadTractorVehicle::ACarlaSadTractorVehicle(
    const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    PrimaryActorTick.bCanEverTick = true;

    // Rear implement attachment point (positioned in Blueprint)
    ImplementAttachPoint = CreateDefaultSubobject<USceneComponent>(
        TEXT("ImplementAttachPoint"));
    ImplementAttachPoint->SetupAttachment(RootComponent);
    ImplementAttachPoint->SetRelativeLocation(FVector(-280.0f, 0.0f, 30.0f));
}

void ACarlaSadTractorVehicle::BeginPlay()
{
    Super::BeginPlay();
    UpdateTerrainLabel();
}

// ── Tick ──────────────────────────────────────────────────────────────────────

void ACarlaSadTractorVehicle::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    // Update terrain label at 2 Hz
    TerrainLabelTimer += DeltaTime;
    if (TerrainLabelTimer >= TerrainLabelUpdateInterval)
    {
        TerrainLabelTimer = 0.0f;
        UpdateTerrainLabel();
    }

    if (bEnableTerrainSpeedGovernor)
        ApplyTerrainSpeedGovernor(DeltaTime);
}

// ── Terrain label ─────────────────────────────────────────────────────────────

void ACarlaSadTractorVehicle::UpdateTerrainLabel()
{
    UWorld* World = GetWorld();
    if (!World)
        return;

    // Line trace downward from vehicle centre to terrain surface
    const FVector Start = GetActorLocation();
    const FVector End   = Start - FVector(0.0f, 0.0f, 200.0f);

    FHitResult Hit;
    FCollisionQueryParams Params(TEXT("TerrainLabel"), true, this);
    if (World->LineTraceSingleByChannel(Hit, Start, End,
                                         ECC_WorldStatic, Params))
    {
        UPrimitiveComponent* Comp = Hit.GetComponent();
        if (Comp)
        {
            // CustomDepthStencilValue stores the semantic label
            const int32 Stencil = Comp->CustomDepthStencilValue;
            if (Stencil >= 100 && Stencil <= 114)
            {
                CurrentTerrainLabel = static_cast<uint8>(Stencil);
                const float* MaxSpeed = TERRAIN_MAX_SPEED.Find(CurrentTerrainLabel);
                CurrentMaxSpeedMps = MaxSpeed ? *MaxSpeed : 5.0f;
            }
        }
    }
}

// ── Speed governor ────────────────────────────────────────────────────────────

void ACarlaSadTractorVehicle::ApplyTerrainSpeedGovernor(float DeltaTime)
{
    UWheeledVehicleMovementComponent* MoveComp = GetVehicleMovementComponent();
    if (!MoveComp)
        return;

    const float CurrentSpeedMps =
        FMath::Abs(GetVehicleForwardSpeed()) / 100.0f;   // cm/s → m/s

    if (CurrentSpeedMps > CurrentMaxSpeedMps)
    {
        // Reduce throttle proportionally to enforce speed limit
        const float ThrottleScale =
            FMath::Clamp(CurrentMaxSpeedMps / FMath::Max(CurrentSpeedMps, 0.1f),
                         0.0f, 1.0f);
        const float CurThrottle = MoveComp->GetThrottleInput();
        MoveComp->SetThrottleInput(CurThrottle * ThrottleScale);
    }
}

// ── Work status ───────────────────────────────────────────────────────────────

void ACarlaSadTractorVehicle::SetWorkStatus(ETractorWorkStatus NewStatus)
{
    WorkStatus = NewStatus;
    UE_LOG(LogTemp, Log, TEXT("[Tractor] WorkStatus → %d"),
           static_cast<int32>(NewStatus));
}

// ── Implement attachment ──────────────────────────────────────────────────────

FTransform ACarlaSadTractorVehicle::GetImplementAttachTransform() const
{
    if (ImplementAttachPoint)
        return ImplementAttachPoint->GetComponentTransform();
    return GetActorTransform();
}
