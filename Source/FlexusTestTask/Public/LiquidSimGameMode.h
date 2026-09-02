#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "LiquidSimGameMode.generated.h"

// Exists only to install ALiquidSimStationHUD - a HUD class cannot be placed in
// a level, so something has to name it. Set as the GameMode override on
// L_FlexusTest_Mobile; the desktop level is left on the engine default.
//
// The pawn is a plain spectator: on the phone there is no movement at all, the
// view is driven entirely by ALiquidSimStationDirector switching cameras. That
// is deliberate - flying a demo scene on virtual thumbsticks is what made the
// build unusable in the first place.
UCLASS()
class FLEXUSTESTTASK_API ALiquidSimGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ALiquidSimGameMode();
};
