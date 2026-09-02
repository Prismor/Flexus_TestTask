#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "LiquidSimStationHUD.generated.h"

class ALiquidSimStationDirector;

// Station picker and gesture handling for the phone build.
//
// Input is polled in DrawHUD rather than going through AHUD hit boxes: hit
// boxes depend on click events being routed to the HUD, which an input-mode
// change silently breaks, whereas this is the same path the paint brush uses -
// if one works the other works.
//
// All geometry is a fraction of the viewport, so it lands correctly on any
// phone aspect without a UMG asset to keep in sync.
UCLASS()
class FLEXUSTESTTASK_API ALiquidSimStationHUD : public AHUD
{
	GENERATED_BODY()

public:
	ALiquidSimStationHUD();

	UPROPERTY(EditDefaultsOnly, Category = "LiquidSim")
	float BarHeightFrac = 0.072f;

	UPROPERTY(EditDefaultsOnly, Category = "LiquidSim")
	float ArrowWidthFrac = 0.13f;

	// The controls hint fades out after this long, so it explains itself once
	// and then stops covering the demo.
	UPROPERTY(EditDefaultsOnly, Category = "LiquidSim")
	float HintSeconds = 6.0f;

	virtual void DrawHUD() override;
	virtual void BeginPlay() override;

private:
	ALiquidSimStationDirector* FindDirector();

	void DrawPanel(float X, float Y, float W, float H, bool bHighlight);
	void DrawLabel(const FString& Text, float X, float Y, float W, float H,
	               float Scale, FLinearColor Colour);

	// Rising-edge detection: a held finger must not re-trigger a button every
	// frame.
	bool bWasPressed = false;

	// Previous frame's gesture, for deltas.
	bool bWasGesture = false;
	FVector2D LastGestureCentre = FVector2D::ZeroVector;
	float LastGestureSpread = 0.0f;

	// Desktop equivalent of the two-finger gesture, so the same build can be
	// driven with a mouse (and so the emulator, where a mouse is one finger,
	// can still exercise the orbit).
	bool bWasRightDown = false;
	FVector2D LastRightPos = FVector2D::ZeroVector;

	// Single-finger orbit, used only on stations with nothing to paint.
	bool bWasSingleOrbit = false;
	FVector2D LastSinglePos = FVector2D::ZeroVector;

	float HintTimer = 0.0f;

	TWeakObjectPtr<ALiquidSimStationDirector> CachedDirector;
};
