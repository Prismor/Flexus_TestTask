#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LiquidSimPaintController.generated.h"

class UTextureRenderTarget2D;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UStaticMeshComponent;

// Drives LVL3/4/5 of the LiquidSim test task: every tick, re-draws one of the
// two ping-pong render targets from the other (decay + optional oscillation -
// see LiquidSim_PaintStep in LiquidSim.ush), stamping a new brush mark under
// the mouse cursor while the left mouse button is held over TargetPlane.
//
// All the actual math lives in the paint material (M_PaintBrush) and its
// .ush functions - this class only decides WHEN to draw and WHERE the brush
// currently is. Porting the same idea to another engine (Unity: a
// MonoBehaviour + Graphics.Blit into two RenderTextures) only means
// re-reading Tick() below, not re-deriving the technique.
//
// The brush position comes from a pure math ray/plane intersection, not a
// physics line trace - the client's imported PlaneMesh.fbx ships with no
// collision, and painting must not silently depend on collision setup.
// UVs are derived from the mesh's own local-space bounding box, so any
// import scale or actor scale keeps the brush exactly under the cursor.
UCLASS(Blueprintable)
class FLEXUSTESTTASK_API ALiquidSimPaintController : public AActor
{
	GENERATED_BODY()

public:
	ALiquidSimPaintController();

	// The plane the brush paints onto. Its mesh's local bounding box and
	// component transform convert a mouse hit into 0..1 paint UVs.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	TObjectPtr<AActor> TargetPlane;

	// Ping-pong pair: one is read from while the other is written to, then
	// they swap every tick. Both are cleared to black on BeginPlay so every
	// play session starts from a flat surface.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	TObjectPtr<UTextureRenderTarget2D> RenderTargetA;

	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	TObjectPtr<UTextureRenderTarget2D> RenderTargetB;

	// M_PaintBrush (or an instance of it) - a dynamic instance is made from
	// this in BeginPlay so BrushU/BrushV can change every tick.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	TObjectPtr<UMaterialInterface> PaintMaterial;

	// Optional fixed camera the player view snaps to on BeginPlay, so the
	// default flying pawn's mouse-look doesn't fight the paint cursor.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	TObjectPtr<AActor> ViewCamera;

	UPROPERTY(EditAnywhere, Category = "LiquidSim", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float DecaySpeed = 0.98f;

	// 0 = LVL3 (pure decay, no oscillation - cos(0) == 1). Above 0 = LVL4.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	float Viscosity = 0.0f;

	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	float BrushRadius = 0.05f;

	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	float BrushDepth = 0.05f;

	// Gaussian falloff width multiplier - higher is softer.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	float BrushSoftness = 1.2f;

	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	float RimHeight = 0.015f;

	// Per-frame decay of the wetness (paint coverage) channel: 1 = painted
	// color stays forever (LVL3), slightly below 1 = fades with the waves.
	UPROPERTY(EditAnywhere, Category = "LiquidSim", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float WetnessDecay = 1.0f;

	// Static spatial jitter of the damping, so the fade-out is slightly
	// uneven across the surface instead of perfectly uniform.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	float DecayVariation = 0.0f;

	// 4-neighbour relaxation strength - rounds off sharp stroke edges.
	UPROPERTY(EditAnywhere, Category = "LiquidSim", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Smoothing = 0.3f;

	// How strongly high-frequency noise tears the stroke border (0 = clean
	// round brush for water, higher = torn ragged edges for gels).
	UPROPERTY(EditAnywhere, Category = "LiquidSim", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Raggedness = 0.0f;

	// Flip these if the brush mark appears mirrored against the cursor -
	// depends on how the paint plane's UVs were authored.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	bool bFlipU = false;

	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	bool bFlipV = false;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> PaintMID;

	// Dynamic instance created on TargetPlane's mesh in BeginPlay (wrapping
	// whatever material the plane already has), so its HeightMap parameter
	// can be repointed at the freshly written render target every tick.
	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> DisplayMID;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> TargetMeshComp;

	// Optional - only present in the mobile level. When it is, the brush stands
	// down while the station picker has the finger, so tapping a button never
	// smears the surface behind it.
	UPROPERTY(Transient)
	TObjectPtr<class ALiquidSimStationDirector> StationDirector;

	// True once RenderTargetA holds the most recently painted frame.
	bool bLastWrittenWasA = false;

	// True while the player's look input is suppressed (during painting) -
	// otherwise a held LMB would rotate the flying pawn's camera and drag
	// the brush across the plane at the same time.
	bool bLookLocked = false;

	// Last frame's brush UV: the paint material stamps a CAPSULE between
	// this and the current position, so fast strokes stay continuous.
	FVector2D LastBrushUV = FVector2D::ZeroVector;
	bool bHadBrushLastFrame = false;

	bool TryGetBrushUV(FVector2D& OutUV) const;
	void SetLookLocked(bool bLocked);
};
