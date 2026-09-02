#include "LiquidSimGameMode.h"
#include "LiquidSimStationHUD.h"
#include "LiquidSimPlayerController.h"
#include "GameFramework/SpectatorPawn.h"

ALiquidSimGameMode::ALiquidSimGameMode()
{
	HUDClass = ALiquidSimStationHUD::StaticClass();

	// Custom controller because the stock one's GetInputTouchState() never
	// reported a finger on Android - see LiquidSimPlayerController.h.
	PlayerControllerClass = ALiquidSimPlayerController::StaticClass();

	// A spectator pawn rather than DefaultPawn: it has no movement bindings to
	// leave dangling now that the virtual joysticks are gone, and the view is
	// taken over by the station cameras on BeginPlay anyway.
	DefaultPawnClass = ASpectatorPawn::StaticClass();
}
