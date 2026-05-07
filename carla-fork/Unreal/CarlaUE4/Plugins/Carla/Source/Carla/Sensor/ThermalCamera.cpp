// ThermalCamera.cpp  — CarlaSad thermal infrared camera sensor
//
// Implementation strategy:
//   1. Attach a secondary USceneCaptureComponent2D with a custom thermal material
//      that renders each semantic class as a solid colour encoding temperature.
//   2. ReadPixels() from the render target on game thread → convert to 16-bit
//      Kelvin*10 values → send via carla::Buffer.
//
// The thermal material (M_ThermalOverlay) must exist in Content/CarlaSad/Materials/.
// It reads the CustomDepthStencil (semantic label) and outputs the mapped temperature
// as a greyscale value normalised to [MinTemperatureK, MaxTemperatureK].

#include "Carla/Sensor/ThermalCamera.h"
#include "Carla/Actor/ActorBlueprintFunctionLibrary.h"

#include "Engine/TextureRenderTarget2D.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Runtime/RenderCore/Public/RenderingThread.h"
#include "Runtime/Renderer/Public/SceneView.h"

#include "carla/sensor/s11n/ImageSerializer.h"
#include "carla/Buffer.h"

// Semantic label → approximate temperature (Kelvin)
// Matches the Python-side SEMANTIC_TEMP_K map in sensor_bridge.py
static const TMap<uint8, float> SEMANTIC_TEMP_K = {
    { 0,  288.0f},  // unlabeled / unknown
    { 4,  310.0f},  // Pedestrians (body temp ~37°C)
    { 9,  282.0f},  // Vegetation
    {10,  330.0f},  // Vehicles (engine heat)
    {14,  288.0f},  // Ground
    {22,  288.0f},  // Terrain
    // CarlaSad agricultural labels
    {100, 288.0f},  // NormalField  — ambient ~15°C
    {101, 284.0f},  // WetField     — evaporative cooling
    {102, 280.0f},  // Swamp        — very wet, cool
    {103, 281.0f},  // Mochak
    {104, 289.0f},  // RoughTerrain — slightly warmer (lower albedo)
    {105, 287.0f},  // FieldBoundary
    {106, 290.0f},  // DrivablePath — compacted, slightly warmer
    {107, 286.0f},  // NonDrivable
    {110, 287.0f},  // WorkedArea   — disturbed soil, near ambient
    {111, 288.0f},  // UnworkedArea
    {112, 288.0f},  // WorkedEdge
    {113, 290.0f},  // ActiveWorkZone — machinery present
    {114, 286.0f},  // RestrictedZone
};

// ── Actor definition (sensor blueprint) ──────────────────────────────────────

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

    // Surface emissivity override (0 = use per-class defaults, 1 = blackbody)
    FActorVariation Emissivity;
    Emissivity.Id = TEXT("emissivity");
    Emissivity.Type = EActorAttributeType::Float;
    Emissivity.RecommendedValues = {TEXT("0.0")};
    Definition.Variations.Emplace(Emissivity);

    return Definition;
}

// ── Constructor ───────────────────────────────────────────────────────────────

AThermalCamera::AThermalCamera(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostPhysics;
}

// ── Set (called when actor is spawned from Python) ────────────────────────────

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
    EmissivityOverride = UActorBlueprintFunctionLibrary::RetrieveActorAttributeToFloat(
        TEXT("emissivity"), Description.Variations, 0.0f);
}

// ── BeginPlay ─────────────────────────────────────────────────────────────────

void AThermalCamera::BeginPlay()
{
    Super::BeginPlay();
    SetupThermalRenderTarget();
}

void AThermalCamera::SetupThermalRenderTarget()
{
    const int32 W = ImageWidth;
    const int32 H = ImageHeight;

    ThermalRT = NewObject<UTextureRenderTarget2D>(this);
    ThermalRT->InitCustomFormat(W, H, PF_B8G8R8A8, false);
    ThermalRT->RenderTargetFormat = RTF_RGBA8;
    ThermalRT->bGPUSharedFlag = true;
    ThermalRT->UpdateResourceImmediate(true);

    ThermalCapture = NewObject<USceneCaptureComponent2D>(this,
        TEXT("ThermalCapture"));
    ThermalCapture->SetupAttachment(RootComponent);
    ThermalCapture->TextureTarget = ThermalRT;
    ThermalCapture->CaptureSource = SCS_FinalColorLDR;

    // Semantic pass: capture stencil buffer with thermal material override
    ThermalCapture->ShowFlags.SetPostProcessing(true);
    ThermalCapture->ShowFlags.SetAtmosphere(false);
    ThermalCapture->ShowFlags.SetFog(false);

    // Load thermal overlay material (must exist in project content)
    static const FString MaterialPath =
        TEXT("/Game/CarlaSad/Materials/M_ThermalOverlay.M_ThermalOverlay");
    UMaterial* ThermalMat = LoadObject<UMaterial>(nullptr, *MaterialPath);
    if (ThermalMat)
    {
        ThermalCapture->PostProcessSettings.AddBlendable(ThermalMat, 1.0f);
        ThermalCapture->PostProcessBlendWeight = 1.0f;
        UE_LOG(LogTemp, Log, TEXT("[ThermalCamera] M_ThermalOverlay loaded"));
    }
    else
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[ThermalCamera] M_ThermalOverlay not found — "
                 "falling back to software semantic mapping"));
    }

    ThermalCapture->RegisterComponent();
    UE_LOG(LogTemp, Log, TEXT("[ThermalCamera] Render target %dx%d created"), W, H);
}

// ── PostPhysTick ──────────────────────────────────────────────────────────────

void AThermalCamera::PostPhysTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
    Super::PostPhysTick(World, TickType, DeltaSeconds);
    RenderThermalImage();
}

// ── Core rendering ────────────────────────────────────────────────────────────

void AThermalCamera::RenderThermalImage()
{
    if (!ThermalRT || !HasActorBegunPlay())
        return;

    // Trigger scene capture
    if (ThermalCapture)
        ThermalCapture->CaptureScene();

    // Read pixels from render target (GPU → CPU readback on render thread)
    FTextureRenderTargetResource* RTResource = ThermalRT->GameThread_GetRenderTargetResource();
    if (!RTResource)
        return;

    const int32 W = ImageWidth;
    const int32 H = ImageHeight;

    // Allocate output buffer: 2 bytes per pixel (uint16, Kelvin * 10)
    const uint32 NumPixels = static_cast<uint32>(W * H);
    auto Buffer = GetEpisode().GetSharedBufferPool().Pop();
    Buffer.reset(NumPixels * sizeof(uint16));
    uint16* OutData = reinterpret_cast<uint16*>(Buffer.data());

    if (SemanticBuffer.Num() == 0 || ThermalCapture == nullptr)
    {
        // Software fallback: use stored semantic buffer from parent SceneCaptureSensor
        RenderFromSemanticBuffer(OutData, NumPixels);
    }
    else
    {
        // Hardware path: read from ThermalRT (which has M_ThermalOverlay applied)
        TArray<FColor> Pixels;
        Pixels.SetNum(NumPixels);
        RTResource->ReadPixels(Pixels);
        ConvertRGBAToThermal16(Pixels, OutData, NumPixels);
    }

    // Send via carla buffer to Python bridge
    auto Stream = GetDataStream(*this);
    {
        TRACE_CPUPROFILER_EVENT_SCOPE_STR("AThermalCamera::SendBuffer");
        Stream.SerializeAndSend(*this, std::move(Buffer),
            GetEpisode().GetElapsedGameTime());
    }
}

void AThermalCamera::RenderFromSemanticBuffer(uint16* OutData, uint32 NumPixels)
{
    // SemanticBuffer is filled by the parent ASceneCaptureSensor on each tick
    // Each pixel contains the semantic stencil ID in the R channel (from CARLA's
    // custom depth pass: FPixelReader reads stencil as 8-bit value in R).

    const uint32 BufSize = static_cast<uint32>(SemanticBuffer.Num());
    for (uint32 i = 0; i < NumPixels; ++i)
    {
        const uint8 Label  = (i < BufSize) ? SemanticBuffer[i].R : 0u;
        const float Emiss  = (EmissivityOverride > 0.0f) ? EmissivityOverride : 0.95f;
        const float TempK  = EstimateTemperature(Label, Emiss);
        // Encode: uint16 = Kelvin * 10  (range 250–400 K → 2500–4000)
        OutData[i] = static_cast<uint16>(
            FMath::Clamp(TempK * 10.0f, 0.0f, 65535.0f));
    }
}

void AThermalCamera::ConvertRGBAToThermal16(
    const TArray<FColor>& Pixels, uint16* OutData, uint32 NumPixels)
{
    // The thermal material encodes temperature as normalised greyscale:
    //   R = (T - MinK) / (MaxK - MinK) * 255
    // We decode back to Kelvin and store as uint16 * 10.
    const float Range = FMath::Max(MaxTemperatureK - MinTemperatureK, 1.0f);
    for (uint32 i = 0; i < NumPixels; ++i)
    {
        const float NormT  = static_cast<float>(Pixels[i].R) / 255.0f;
        float TempK = MinTemperatureK + NormT * Range;

        // Apply per-pixel noise (NETD simulation)
        if (NoiseSigmaK > 0.0f)
            TempK += FMath::RandRange(-NoiseSigmaK * 3.0f, NoiseSigmaK * 3.0f);

        TempK = FMath::Clamp(TempK, MinTemperatureK, MaxTemperatureK);
        OutData[i] = static_cast<uint16>(TempK * 10.0f);
    }
}

// ── Per-pixel temperature estimation ─────────────────────────────────────────

float AThermalCamera::EstimateTemperature(uint8 SemanticLabel, float SurfaceEmissivity) const
{
    const float* BaseTemp = SEMANTIC_TEMP_K.Find(SemanticLabel);
    float Temp = BaseTemp ? *BaseTemp : 288.0f;

    // Lower emissivity → apparent temperature shifts toward ambient (288 K)
    constexpr float AmbientK = 288.0f;
    Temp = AmbientK + (Temp - AmbientK) * FMath::Clamp(SurfaceEmissivity, 0.1f, 1.0f);

    // NETD noise
    if (NoiseSigmaK > 0.0f)
        Temp += FMath::RandRange(-NoiseSigmaK * 3.0f, NoiseSigmaK * 3.0f);

    return FMath::Clamp(Temp, MinTemperatureK, MaxTemperatureK);
}
