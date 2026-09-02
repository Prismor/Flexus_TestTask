#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "LiquidSimPlayerController.generated.h"

// Touch source for the mobile build.
//
// WHY THIS EXISTS: APlayerController::GetInputTouchState() returned
// touchDown=0 pos=(-1,-1) on the device even while a finger was held down, so
// both the station picker and the paint brush were dead on Android. Binding
// through the InputComponent (BindTouch) is the delivery path the engine
// actually drives on a phone, so the state is captured here and everything
// else reads it from this controller.
//
// GetInputTouchState is still consulted as a fallback, and the mouse path is
// kept so the same code stays testable on desktop.
UCLASS()
class FLEXUSTESTTASK_API ALiquidSimPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ALiquidSimPlayerController();

	// True while a finger (or the left mouse button) is down.
	UPROPERTY(BlueprintReadOnly, Category = "LiquidSim")
	bool bPointerDown = false;

	// Viewport-space position of that pointer.
	UPROPERTY(BlueprintReadOnly, Category = "LiquidSim")
	FVector2D PointerPos = FVector2D::ZeroVector;

	// Second finger, tracked so a two-finger gesture can drive the camera while
	// a single finger keeps painting.
	UPROPERTY(BlueprintReadOnly, Category = "LiquidSim")
	bool bSecondPointerDown = false;

	UPROPERTY(BlueprintReadOnly, Category = "LiquidSim")
	FVector2D SecondPointerPos = FVector2D::ZeroVector;

	// Single place every consumer asks, so the fallback order lives in one
	// spot instead of being duplicated in the HUD and the paint controller.
	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	bool GetPointer(FVector2D& OutPos) const;

	// True while exactly two fingers are down - the gesture is a camera move.
	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	bool IsTwoFingerGesture() const { return bPointerDown && bSecondPointerDown; }

	// Midpoint of the two fingers and their separation, which the HUD turns
	// into orbit and pinch deltas.
	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	void GetGesture(FVector2D& OutCentre, float& OutSpread) const;

	// Accumulated wheel ticks since the last call, then cleared. Bound rather
	// than polled - a wheel tick is an axis event and never shows up as a key
	// that is "down" for a frame.
	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	float ConsumeWheel();

protected:
	virtual void SetupInputComponent() override;
	virtual void BeginPlay() override;

private:
	UFUNCTION()
	void OnTouchPressed(ETouchIndex::Type Finger, FVector Location);

	UFUNCTION()
	void OnTouchMoved(ETouchIndex::Type Finger, FVector Location);

	UFUNCTION()
	void OnTouchReleased(ETouchIndex::Type Finger, FVector Location);

	void OnWheelUp();
	void OnWheelDown();

	float WheelDelta = 0.0f;
};
