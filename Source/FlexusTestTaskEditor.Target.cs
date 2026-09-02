// Build target for the editor.

using UnrealBuildTool;
using System.Collections.Generic;

public class FlexusTestTaskEditorTarget : TargetRules
{
	public FlexusTestTaskEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("FlexusTestTask");
	}
}
