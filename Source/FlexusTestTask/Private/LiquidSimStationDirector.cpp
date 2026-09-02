#include "LiquidSimStationDirector.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"

ALiquidSimStationDirector::ALiquidSimStationDirector()
{
	// Ticks because the orbit is recomputed from (Yaw, Pitch, Distance) rather
	// than being baked into a placed CameraActor.
	PrimaryActorTick.bCanEverTick = true;
}

void ALiquidSimStationDirector::BeginPlay()
{
	Super::BeginPlay();

	Pitch = DefaultPitch;

	// Spawned rather than placed: the level would otherwise need one
	// CameraActor per station kept in sync with the station positions by hand.
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	OrbitCamera = GetWorld()->SpawnActor<ACameraActor>(
		ACameraActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, Params);

	if (OrbitCamera)
	{
#if WITH_EDITOR
		// Editor-only: AActor::SetActorLabel does not exist in a packaged
		// build, and calling it unguarded fails the Android compile.
		OrbitCamera->SetActorLabel(TEXT("FX_OrbitCamera"));
#endif
		if (UCameraComponent* Cam = OrbitCamera->GetCameraComponent())
		{
			// Slightly wider than the 90 default: a phone is held close and a
			// narrow FOV makes the surface feel cramped.
			Cam->SetFieldOfView(75.0f);
			Cam->SetConstraintAspectRatio(false);
		}
	}

	CurrentIndex = Stations.IsValidIndex(StartIndex) ? StartIndex : 0;
	SelectStation(CurrentIndex);
}

void ALiquidSimStationDirector::SelectStation(int32 Index)
{
	if (!Stations.IsValidIndex(Index))
	{
		return;
	}

	CurrentIndex = Index;
	bPickerOpen = false;

	// Each station is framed fresh - carrying a wild orbit from the previous
	// one over means arriving at a station looking at nothing.
	ResetView();
	ApplyOrbit();

	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		if (OrbitCamera)
		{
			// Skip the blend on the very first selection: blending from an
			// as-yet unpositioned view target swoops in from the world origin.
			const float Blend = HasActorBegunPlay() ? BlendTime : 0.0f;
			PC->SetViewTargetWithBlend(OrbitCamera, Blend);
		}
	}
}

void ALiquidSimStationDirector::NextStation()
{
	if (Stations.Num() > 0)
	{
		SelectStation((CurrentIndex + 1) % Stations.Num());
	}
}

void ALiquidSimStationDirector::PreviousStation()
{
	if (Stations.Num() > 0)
	{
		SelectStation((CurrentIndex + Stations.Num() - 1) % Stations.Num());
	}
}

void ALiquidSimStationDirector::ResetView()
{
	Yaw = 90.0f;          // looking along +Y, the direction the stations face
	Pitch = DefaultPitch;
	DistanceScale = 1.0f;
}

bool ALiquidSimStationDirector::IsCurrentInteractive() const
{
	return Stations.IsValidIndex(CurrentIndex) && Stations[CurrentIndex].bInteractive;
}

void ALiquidSimStationDirector::AddOrbitInput(FVector2D ScreenDelta)
{
	Yaw += ScreenDelta.X * OrbitSpeed;
	// Dragging DOWN raises the camera, i.e. the surface follows the finger -
	// the grab-and-drag convention every map and model viewer uses. The sign
	// was the other way round and read as inverted.
	Pitch = FMath::Clamp(Pitch - ScreenDelta.Y * OrbitSpeed, MinPitch, MaxPitch);
	ApplyOrbit();
}

void ALiquidSimStationDirector::AddZoomInput(float PinchDelta)
{
	// Pinch is measured in pixels of finger separation; scale it down to a
	// fraction of the orbit radius per frame.
	DistanceScale = FMath::Clamp(
		DistanceScale - PinchDelta * ZoomSpeed * 0.001f,
		MinDistanceScale, MaxDistanceScale);
	ApplyOrbit();
}

void ALiquidSimStationDirector::ApplyOrbit()
{
	if (!OrbitCamera || !Stations.IsValidIndex(CurrentIndex))
	{
		return;
	}

	const FLiquidSimStation& Station = Stations[CurrentIndex];
	const float Radius = FMath::Max(Station.Distance * DistanceScale, 50.0f);

	// Spherical to cartesian. Pitch is negative when looking down, so the
	// camera sits ABOVE the centre by -sin(Pitch).
	const float PitchRad = FMath::DegreesToRadians(Pitch);
	const float YawRad = FMath::DegreesToRadians(Yaw);
	const float CosP = FMath::Cos(PitchRad);

	const FVector Offset(
		-CosP * FMath::Cos(YawRad) * Radius,
		-CosP * FMath::Sin(YawRad) * Radius,
		-FMath::Sin(PitchRad) * Radius);

	OrbitCamera->SetActorLocation(Station.Centre + Offset);
	OrbitCamera->SetActorRotation((Station.Centre - (Station.Centre + Offset)).Rotation());
}

void ALiquidSimStationDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The orbit is applied on input rather than every frame, but a station
	// whose actors moved (or a camera that lost its view target) is corrected
	// here cheaply.
	if (OrbitCamera && Stations.IsValidIndex(CurrentIndex))
	{
		ApplyOrbit();
	}
}
