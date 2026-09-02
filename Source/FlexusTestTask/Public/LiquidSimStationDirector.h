#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LiquidSimStationDirector.generated.h"

class ACameraActor;

// One demo station: a name for the picker and the point the camera orbits.
USTRUCT(BlueprintType)
struct FLiquidSimStation
{
	GENERATED_BODY()

	// Shown in the picker, e.g. "LVL3 Paint".
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	FString Label;

	// World-space point the camera looks at and orbits around.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	FVector Centre = FVector::ZeroVector;

	// Orbit radius for this station. Bigger stations need more room - LVL1's
	// spheres stand much taller than a flat plane.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	float Distance = 1000.0f;

	// True for the stations you paint on (LVL3/4/5). On those a single finger
	// belongs to the brush and the camera needs two; everywhere else a single
	// finger orbits, because there is nothing to paint and making the user
	// use two fingers would be pointless ceremony.
	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	bool bInteractive = false;
};

// Station switcher and orbit camera for the phone build.
//
// WHY: the desktop level is a row of stations meant to be flown past while
// recording video. On a phone that is unusable - virtual thumbsticks fight the
// paint brush for the same finger. Here there is no flying: one orbit camera,
// a picker to jump between stations, and two-finger drag to look around.
//
// One camera is spawned at runtime rather than placing eight CameraActors in
// the level: the view is computed from (Yaw, Pitch, Distance) around the
// current station's centre, so it stays correct even if a station moves.
UCLASS(Blueprintable)
class FLEXUSTESTTASK_API ALiquidSimStationDirector : public AActor
{
	GENERATED_BODY()

public:
	ALiquidSimStationDirector();

	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	TArray<FLiquidSimStation> Stations;

	UPROPERTY(EditAnywhere, Category = "LiquidSim")
	int32 StartIndex = 0;

	// Seconds the camera takes to glide between stations. A hard cut reads as a
	// glitch on a phone; a short blend shows that YOU moved.
	UPROPERTY(EditAnywhere, Category = "LiquidSim", meta = (ClampMin = "0.0"))
	float BlendTime = 0.35f;

	// --- orbit -------------------------------------------------------------
	// Default framing: slightly above the surface, looking down at it.
	UPROPERTY(EditAnywhere, Category = "LiquidSim|Orbit")
	float DefaultPitch = -38.0f;

	UPROPERTY(EditAnywhere, Category = "LiquidSim|Orbit")
	float MinPitch = -85.0f;

	// Not 0: level with the surface a flat plane collapses to a line.
	UPROPERTY(EditAnywhere, Category = "LiquidSim|Orbit")
	float MaxPitch = -6.0f;

	UPROPERTY(EditAnywhere, Category = "LiquidSim|Orbit")
	float OrbitSpeed = 0.35f;

	UPROPERTY(EditAnywhere, Category = "LiquidSim|Orbit")
	float ZoomSpeed = 1.6f;

	UPROPERTY(EditAnywhere, Category = "LiquidSim|Orbit")
	float MinDistanceScale = 0.45f;

	UPROPERTY(EditAnywhere, Category = "LiquidSim|Orbit")
	float MaxDistanceScale = 2.2f;

	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	void SelectStation(int32 Index);

	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	void NextStation();

	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	void PreviousStation();

	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	int32 GetCurrentStation() const { return CurrentIndex; }

	// Drag the orbit by a screen-space delta (two-finger drag).
	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	void AddOrbitInput(FVector2D ScreenDelta);

	// Pinch: positive spreads the fingers apart and moves the camera closer.
	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	void AddZoomInput(float PinchDelta);

	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	void ResetView();

	// Whether the CURRENT station wants a finger for painting.
	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	bool IsCurrentInteractive() const;

	// True while the picker list is expanded.
	UPROPERTY(BlueprintReadOnly, Category = "LiquidSim")
	bool bPickerOpen = false;

	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	void TogglePicker() { bPickerOpen = !bPickerOpen; }

	// Set by the HUD while a finger is over the bar or the open list, so
	// tapping a button never stamps a brush mark on the liquid behind it.
	UPROPERTY(BlueprintReadOnly, Category = "LiquidSim")
	bool bInputOverUI = false;

	// Set while two fingers are down: the gesture is a camera move, so the
	// brush must stay out of it.
	UPROPERTY(BlueprintReadOnly, Category = "LiquidSim")
	bool bOrbiting = false;

	// True while the pointer is actually over a paintable surface. The paint
	// controller sets it every tick; the HUD uses it to decide whether a single
	// finger belongs to the brush or to the camera.
	UPROPERTY(BlueprintReadOnly, Category = "LiquidSim")
	bool bPointerOnSurface = false;

	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	bool IsInputBlocked() const { return bPickerOpen || bInputOverUI || bOrbiting; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	void ApplyOrbit();

	UPROPERTY(Transient)
	TObjectPtr<ACameraActor> OrbitCamera;

	int32 CurrentIndex = 0;
	float Yaw = 90.0f;
	float Pitch = -38.0f;
	float DistanceScale = 1.0f;
};
