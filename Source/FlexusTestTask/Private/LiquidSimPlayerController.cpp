#include "LiquidSimPlayerController.h"
#include "Components/InputComponent.h"

ALiquidSimPlayerController::ALiquidSimPlayerController()
{
	// Touch has to be enabled before the input component is wired up, not in
	// some other actor's BeginPlay - ordering between actors is not guaranteed,
	// and the paint controller used to be the only thing switching these on.
	bEnableTouchEvents = true;
	bEnableTouchOverEvents = true;
	bEnableClickEvents = true;
	bEnableMouseOverEvents = true;
}

void ALiquidSimPlayerController::BeginPlay()
{
	Super::BeginPlay();

#if PLATFORM_ANDROID || PLATFORM_IOS
	bShowMouseCursor = false;
	SetInputMode(FInputModeGameOnly());
#else
	bShowMouseCursor = true;
	FInputModeGameAndUI InputMode;
	InputMode.SetHideCursorDuringCapture(false);
	SetInputMode(InputMode);
#endif
}

void ALiquidSimPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	if (InputComponent)
	{
		InputComponent->BindTouch(IE_Pressed, this, &ALiquidSimPlayerController::OnTouchPressed);
		InputComponent->BindTouch(IE_Repeat, this, &ALiquidSimPlayerController::OnTouchMoved);
		InputComponent->BindTouch(IE_Released, this, &ALiquidSimPlayerController::OnTouchReleased);

		// The wheel has to be BOUND. Polling it with WasInputKeyJustPressed
		// never reported anything: a wheel tick is an axis event, not a key
		// press that stays down for a frame.
		InputComponent->BindKey(EKeys::MouseScrollUp, IE_Pressed,
		                        this, &ALiquidSimPlayerController::OnWheelUp);
		InputComponent->BindKey(EKeys::MouseScrollDown, IE_Pressed,
		                        this, &ALiquidSimPlayerController::OnWheelDown);
	}
}

void ALiquidSimPlayerController::OnTouchPressed(ETouchIndex::Type Finger, FVector Location)
{
	// Finger 1 drives the UI and the brush; finger 2 turns the gesture into a
	// camera move. Anything beyond two is ignored rather than fighting for the
	// same state.
	if (Finger == ETouchIndex::Touch1)
	{
		bPointerDown = true;
		PointerPos = FVector2D(Location.X, Location.Y);
	}
	else if (Finger == ETouchIndex::Touch2)
	{
		bSecondPointerDown = true;
		SecondPointerPos = FVector2D(Location.X, Location.Y);
	}
}

void ALiquidSimPlayerController::OnTouchMoved(ETouchIndex::Type Finger, FVector Location)
{
	if (Finger == ETouchIndex::Touch1)
	{
		bPointerDown = true;
		PointerPos = FVector2D(Location.X, Location.Y);
	}
	else if (Finger == ETouchIndex::Touch2)
	{
		bSecondPointerDown = true;
		SecondPointerPos = FVector2D(Location.X, Location.Y);
	}
}

void ALiquidSimPlayerController::OnTouchReleased(ETouchIndex::Type Finger, FVector Location)
{
	if (Finger == ETouchIndex::Touch1)
	{
		bPointerDown = false;
	}
	else if (Finger == ETouchIndex::Touch2)
	{
		bSecondPointerDown = false;
	}
}

void ALiquidSimPlayerController::OnWheelUp()
{
	WheelDelta += 1.0f;
}

void ALiquidSimPlayerController::OnWheelDown()
{
	WheelDelta -= 1.0f;
}

float ALiquidSimPlayerController::ConsumeWheel()
{
	const float Value = WheelDelta;
	WheelDelta = 0.0f;
	return Value;
}

void ALiquidSimPlayerController::GetGesture(FVector2D& OutCentre, float& OutSpread) const
{
	OutCentre = (PointerPos + SecondPointerPos) * 0.5f;
	OutSpread = FVector2D::Distance(PointerPos, SecondPointerPos);
}

bool ALiquidSimPlayerController::GetPointer(FVector2D& OutPos) const
{
	// 1. The bound touch delegates - the only path that actually fires on the
	//    device.
	if (bPointerDown)
	{
		OutPos = PointerPos;
		return true;
	}

	// 2. Polled touch state, in case a platform delivers it this way instead.
	float TouchX = 0.0f;
	float TouchY = 0.0f;
	bool bTouchDown = false;
	GetInputTouchState(ETouchIndex::Touch1, TouchX, TouchY, bTouchDown);
	if (bTouchDown)
	{
		OutPos = FVector2D(TouchX, TouchY);
		return true;
	}

	// 3. Mouse, so the same build stays usable on desktop.
	if (IsInputKeyDown(EKeys::LeftMouseButton))
	{
		float MouseX = 0.0f;
		float MouseY = 0.0f;
		if (GetMousePosition(MouseX, MouseY))
		{
			OutPos = FVector2D(MouseX, MouseY);
			return true;
		}
	}

	return false;
}
