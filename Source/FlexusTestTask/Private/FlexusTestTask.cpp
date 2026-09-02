#include "FlexusTestTask.h"

#include "Interfaces/IPluginManager.h"
#include "Misc/Paths.h"
#include "ShaderCore.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FFlexusTestTaskModule, FlexusTestTask, "FlexusTestTask");

void FFlexusTestTaskModule::StartupModule()
{
	// Materials include the shader library as "/Project/LiquidSim.ush". That
	// virtual path has to be registered before any material compiles.
	//
	// UE 5.7 and newer map /Project to <ProjectDir>/Shaders themselves, and
	// calling Add on an already-registered mapping asserts, so check first.
	if (!AllShaderSourceDirectoryMappings().Contains(TEXT("/Project")))
	{
		const FString ShaderDir = FPaths::Combine(FPaths::ProjectDir(), TEXT("Shaders"));
		AddShaderSourceDirectoryMapping(TEXT("/Project"), ShaderDir);
	}
}

void FFlexusTestTaskModule::ShutdownModule()
{
}
