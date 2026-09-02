#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "LiquidSimMaterialHelpers.generated.h"

class UMaterial;
class UMaterialExpression;

// EMaterialProperty::MP_WorldPositionOffset is UMETA(Hidden), so Python/
// Blueprint can't pass it to MaterialEditingLibrary::ConnectMaterialProperty -
// the engine strips hidden enum entries from script marshaling entirely.
// This does the same wiring the Material Editor does when you drag a wire
// onto the World Position Offset pin, directly in C++ where the enum value
// is still perfectly usable.
// Editor-only: used by the Python scripts that assemble the materials.
// Compiled out of packaged builds (see the .cpp).
UCLASS()
class FLEXUSTESTTASK_API ULiquidSimMaterialHelpers : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	// OutputName: pass "None" for an expression's main output, or the name
	// of one of its additional Custom node outputs.
	UFUNCTION(BlueprintCallable, Category = "LiquidSim")
	static bool ConnectToWorldPositionOffset(UMaterial* Material, UMaterialExpression* Expression, FName OutputName);
};
