// Build target for the packaged game (this is what an Android/Windows build uses).

using UnrealBuildTool;
using System.Collections.Generic;

public class FlexusTestTaskTarget : TargetRules
{
	public FlexusTestTaskTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("FlexusTestTask");
	}
}
