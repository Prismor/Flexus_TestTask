#include "LiquidSimMaterialHelpers.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpression.h"

bool ULiquidSimMaterialHelpers::ConnectToWorldPositionOffset(UMaterial* Material, UMaterialExpression* Expression, FName OutputName)
{
#if WITH_EDITOR
	if (!Material || !Expression)
	{
		return false;
	}

	// WorldPositionOffset lives on UMaterialEditorOnlyData (split off UMaterial
	// itself since the Substrate material rework), not on UMaterial directly.
	UMaterialEditorOnlyData* EditorOnly = Material->GetEditorOnlyData();
	if (!EditorOnly)
	{
		return false;
	}

	int32 OutputIndex = 0;
	if (!OutputName.IsNone())
	{
		const TArray<FExpressionOutput>& Outputs = Expression->GetOutputs();
		for (int32 Index = 0; Index < Outputs.Num(); ++Index)
		{
			if (Outputs[Index].OutputName == OutputName)
			{
				OutputIndex = Index;
				break;
			}
		}
	}

	EditorOnly->WorldPositionOffset.Expression = Expression;
	EditorOnly->WorldPositionOffset.OutputIndex = OutputIndex;
	Material->MarkPackageDirty();
	return true;
#else
	// Packaged builds have no material graph to edit - this helper only runs
	// while the Python asset-build scripts assemble materials in the editor.
	return false;
#endif
}
