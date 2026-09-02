#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

// The project's own module. Its one startup job is to make the HLSL library
// in <Project>/Shaders reachable from materials as "/Project/*.ush" - without
// that mapping every Custom node's #include fails and no material compiles.
class FFlexusTestTaskModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
