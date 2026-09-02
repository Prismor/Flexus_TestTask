#include "LiquidSimPaintController.h"
#include "LiquidSimStationDirector.h"
#include "LiquidSimPlayerController.h"
#include "EngineUtils.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/TextureRenderTarget2D.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"

ALiquidSimPaintController::ALiquidSimPaintController()
{
	PrimaryActorTick.bCanEverTick = true;
}

void ALiquidSimPaintController::BeginPlay()
{
	Super::BeginPlay();

	if (PaintMaterial)
	{
		PaintMID = UMaterialInstanceDynamic::Create(PaintMaterial, this);
	}

	// Wrap whatever material the plane already wears in a dynamic instance,
	// so HeightMap can be repointed at the freshly written render target
	// every tick. This replaces an un-assignable EditAnywhere MID property -
	// dynamic instances can't be picked in a Details panel.
	if (TargetPlane)
	{
		TargetMeshComp = TargetPlane->FindComponentByClass<UStaticMeshComponent>();
		if (TargetMeshComp)
		{
			DisplayMID = TargetMeshComp->CreateAndSetMaterialInstanceDynamic(0);
		}
	}

	// Render targets keep whatever was painted in a previous session (they
	// are assets, not per-play buffers) - clear both so every run starts
	// from a flat surface.
	if (RenderTargetA)
	{
		UKismetRenderingLibrary::ClearRenderTarget2D(this, RenderTargetA, FLinearColor::Black);
	}
	if (RenderTargetB)
	{
		UKismetRenderingLibrary::ClearRenderTarget2D(this, RenderTargetB, FLinearColor::Black);
	}

	// Painting needs a visible, freely movable cursor. The default flying
	// pawn's mouse-look would fight the brush, so the view also snaps to a
	// fixed camera when one is assigned.
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		// Touch events are off by default; without this the phone build
		// receives nothing from the screen.
		PC->bEnableTouchEvents = true;
		PC->bEnableTouchOverEvents = true;
		PC->bEnableClickEvents = true;

#if PLATFORM_ANDROID || PLATFORM_IOS
		// A hardware cursor makes no sense on a touch screen.
		PC->bShowMouseCursor = false;
		PC->SetInputMode(FInputModeGameOnly());
#else
		PC->bShowMouseCursor = true;
		FInputModeGameAndUI InputMode;
		InputMode.SetHideCursorDuringCapture(false);
		PC->SetInputMode(InputMode);
#endif

		if (ViewCamera)
		{
			PC->SetViewTargetWithBlend(ViewCamera, 0.0f);
		}
	}

	// Present only in the mobile level; stays null on desktop, where the
	// station picker does not exist. Not a for-loop with a break: Android's
	// clang rejects "loop will run at most once" under -Werror.
	TActorIterator<ALiquidSimStationDirector> DirectorIt(GetWorld());
	if (DirectorIt)
	{
		StationDirector = *DirectorIt;
	}

	// RenderTargetB is read from on the very first tick, so the first frame
	// actually painted lands in RenderTargetA.
	bLastWrittenWasA = false;
}

void ALiquidSimPaintController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	SetLookLocked(false);
	Super::EndPlay(EndPlayReason);
}

// SetIgnoreLookInput stacks internally, so only flip it on transitions.
void ALiquidSimPaintController::SetLookLocked(bool bLocked)
{
	if (bLocked == bLookLocked)
	{
		return;
	}
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		if (bLocked)
		{
			PC->SetIgnoreLookInput(true);
		}
		else
		{
			PC->ResetIgnoreLookInput();
		}
		bLookLocked = bLocked;
	}
}

bool ALiquidSimPaintController::TryGetBrushUV(FVector2D& OutUV) const
{
	if (!TargetPlane || !TargetMeshComp || !TargetMeshComp->GetStaticMesh())
	{
		return false;
	}

	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC)
	{
		return false;
	}

	// The station picker owns the finger while it is open or being touched.
	if (StationDirector && StationDirector->IsInputBlocked())
	{
		return false;
	}

	// Where the player is pointing, from either input device. On Android there
	// is no mouse at all, so a mouse-only check would make the paint levels
	// look broken on a phone: the surface would simply never respond.
	// Pointer comes from ALiquidSimPlayerController: on Android the polled
	// GetInputTouchState never reports a finger (measured on device), so the
	// controller captures touches via bound InputComponent delegates and
	// falls back to the mouse on desktop.
	float ScreenX = 0.0f;
	float ScreenY = 0.0f;

	// The custom controller is installed by the mobile game mode only. On the
	// DESKTOP level the engine default is in play, so requiring the cast here
	// silently disabled painting there entirely - the plane simply stopped
	// responding to the mouse.
	if (ALiquidSimPlayerController* LSPC = Cast<ALiquidSimPlayerController>(PC))
	{
		FVector2D Pointer;
		if (!LSPC->GetPointer(Pointer))
		{
			return false;
		}
		ScreenX = Pointer.X;
		ScreenY = Pointer.Y;
	}
	else
	{
		// Plain controller: mouse first, then any polled touch.
		bool bGot = false;
		if (PC->IsInputKeyDown(EKeys::LeftMouseButton))
		{
			float MX = 0.0f;
			float MY = 0.0f;
			if (PC->GetMousePosition(MX, MY))
			{
				ScreenX = MX;
				ScreenY = MY;
				bGot = true;
			}
		}
		if (!bGot)
		{
			bool bTouchDown = false;
			PC->GetInputTouchState(ETouchIndex::Touch1, ScreenX, ScreenY, bTouchDown);
			bGot = bTouchDown;
		}
		if (!bGot)
		{
			return false;
		}
	}

	FVector WorldOrigin, WorldDirection;
	if (!PC->DeprojectScreenPositionToWorld(ScreenX, ScreenY, WorldOrigin, WorldDirection))
	{
		return false;
	}

	// Pure math ray/plane intersection instead of a physics line trace: the
	// client's imported PlaneMesh.fbx has no collision, and painting should
	// not silently depend on collision setup.
	const FVector PlaneOrigin = TargetPlane->GetActorLocation();
	const FVector PlaneNormal = TargetPlane->GetActorUpVector();

	const float Facing = FVector::DotProduct(WorldDirection, PlaneNormal);
	if (FMath::Abs(Facing) < KINDA_SMALL_NUMBER)
	{
		return false; // ray parallel to the plane
	}

	const FVector Hit = FMath::RayPlaneIntersection(WorldOrigin, WorldDirection,
	                                                FPlane(PlaneOrigin, PlaneNormal));
	if (FVector::DotProduct(Hit - WorldOrigin, WorldDirection) < 0.0f)
	{
		return false; // intersection behind the camera
	}

	// UVs come from the mesh's own local-space bounding box, so any import
	// scale or actor scale keeps the brush exactly under the cursor.
	const FBox LocalBox = TargetMeshComp->GetStaticMesh()->GetBoundingBox();
	const FVector Local = TargetMeshComp->GetComponentTransform().InverseTransformPosition(Hit);

	const FVector Size = LocalBox.GetSize();
	if (Size.X < KINDA_SMALL_NUMBER || Size.Y < KINDA_SMALL_NUMBER)
	{
		return false;
	}

	float U = static_cast<float>((Local.X - LocalBox.Min.X) / Size.X);
	float V = static_cast<float>((Local.Y - LocalBox.Min.Y) / Size.Y);
	if (bFlipU)
	{
		U = 1.0f - U;
	}
	if (bFlipV)
	{
		V = 1.0f - V;
	}

	if (U < 0.0f || U > 1.0f || V < 0.0f || V > 1.0f)
	{
		return false; // cursor is off the plane
	}

	OutUV.X = U;
	OutUV.Y = V;
	return true;
}

void ALiquidSimPaintController::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!PaintMID || !RenderTargetA || !RenderTargetB)
	{
		return;
	}

	UTextureRenderTarget2D* ReadTarget = bLastWrittenWasA ? RenderTargetA : RenderTargetB;
	UTextureRenderTarget2D* WriteTarget = bLastWrittenWasA ? RenderTargetB : RenderTargetA;

	FVector2D BrushUV;
	const bool bPainting = TryGetBrushUV(BrushUV);

	// Tell the director whether the finger is on this surface, so a drag that
	// misses the plane can orbit the camera instead of doing nothing.
	if (StationDirector && bPainting)
	{
		StationDirector->bPointerOnSurface = true;
	}

	// While the brush is down, freeze the pawn's mouse-look so dragging the
	// cursor paints instead of spinning the camera.
	SetLookLocked(bPainting);

	PaintMID->SetTextureParameterValue(TEXT("PrevHeightMap"), ReadTarget);
	// brush depth/rim are rates per second in the material - it needs the
	// real frame time to press gradually and framerate-independently
	PaintMID->SetScalarParameterValue(TEXT("DeltaTime"), DeltaSeconds);
	PaintMID->SetScalarParameterValue(TEXT("DecaySpeed"), DecaySpeed);
	PaintMID->SetScalarParameterValue(TEXT("DecayVariation"), DecayVariation);
	PaintMID->SetScalarParameterValue(TEXT("Viscosity"), Viscosity);
	PaintMID->SetScalarParameterValue(TEXT("Smoothing"), Smoothing);
	PaintMID->SetScalarParameterValue(TEXT("WetnessDecay"), WetnessDecay);
	PaintMID->SetScalarParameterValue(TEXT("BrushRadius"), BrushRadius);
	PaintMID->SetScalarParameterValue(TEXT("BrushSoftness"), BrushSoftness);
	PaintMID->SetScalarParameterValue(TEXT("BrushDepth"), BrushDepth);
	PaintMID->SetScalarParameterValue(TEXT("RimHeight"), RimHeight);
	PaintMID->SetScalarParameterValue(TEXT("Raggedness"), Raggedness);
	PaintMID->SetScalarParameterValue(TEXT("BrushStrength"), bPainting ? 1.0f : 0.0f);
	if (bPainting)
	{
		// capsule stroke: on the first frame of a stroke the segment
		// collapses to a point (prev == current)
		const FVector2D PrevUV = bHadBrushLastFrame ? LastBrushUV : BrushUV;
		PaintMID->SetScalarParameterValue(TEXT("BrushU"), BrushUV.X);
		PaintMID->SetScalarParameterValue(TEXT("BrushV"), BrushUV.Y);
		PaintMID->SetScalarParameterValue(TEXT("BrushPrevU"), PrevUV.X);
		PaintMID->SetScalarParameterValue(TEXT("BrushPrevV"), PrevUV.Y);
		LastBrushUV = BrushUV;
	}
	bHadBrushLastFrame = bPainting;

	// Exactly one render-target switch per frame, as the brief asks.
	UKismetRenderingLibrary::DrawMaterialToRenderTarget(this, WriteTarget, PaintMID);

	if (DisplayMID)
	{
		DisplayMID->SetTextureParameterValue(TEXT("HeightMap"), WriteTarget);
	}

	bLastWrittenWasA = !bLastWrittenWasA;
}
