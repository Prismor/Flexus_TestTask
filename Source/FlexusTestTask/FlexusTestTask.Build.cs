// Module rules for the project's own gameplay code.
//
// Everything here is runtime-safe (no editor-only modules), so the module
// packages for Android exactly as it does for Windows.

using UnrealBuildTool;

public class FlexusTestTask : ModuleRules
{
	public FlexusTestTask(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"RenderCore",   // AddShaderSourceDirectoryMapping for /Project shaders
			"Projects",     // IPluginManager / FPaths for the shader directory
		});
	}
}
