#include "LiquidSimStationHUD.h"
#include "LiquidSimStationDirector.h"
#include "LiquidSimPlayerController.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"

ALiquidSimStationHUD::ALiquidSimStationHUD()
{
	PrimaryActorTick.bCanEverTick = false;
}

void ALiquidSimStationHUD::BeginPlay()
{
	Super::BeginPlay();

	// GAreScreenMessagesEnabled is the switch the DisableAllScreenMessages
	// console command flips, and the only one that silenced these: the two
	// UEngine flags were tried first and the warnings stayed on screen.
	GAreScreenMessagesEnabled = false;
	if (GEngine)
	{
		GEngine->bEnableOnScreenDebugMessages = false;
		GEngine->bEnableOnScreenDebugMessagesDisplay = false;
	}

	HintTimer = HintSeconds;
}

ALiquidSimStationDirector* ALiquidSimStationHUD::FindDirector()
{
	if (CachedDirector.IsValid())
	{
		return CachedDirector.Get();
	}
	// A plain first-match, not a for-loop with a break: the Android clang
	// treats "loop will run at most once" as an error under -Werror.
	TActorIterator<ALiquidSimStationDirector> It(GetWorld());
	if (It)
	{
		CachedDirector = *It;
		return *It;
	}
	return nullptr;
}

void ALiquidSimStationHUD::DrawPanel(float X, float Y, float W, float H, bool bHighlight)
{
	// Dark translucent slab with a bright top edge - reads against both a pale
	// sky and a bright liquid without needing a blur.
	DrawRect(bHighlight ? FLinearColor(0.10f, 0.44f, 0.56f, 0.94f)
	                    : FLinearColor(0.04f, 0.05f, 0.07f, 0.86f),
	         X, Y, W, H);
	DrawRect(FLinearColor(1.0f, 1.0f, 1.0f, bHighlight ? 0.30f : 0.12f), X, Y, W, 2.0f);
}

void ALiquidSimStationHUD::DrawLabel(const FString& Text, float X, float Y, float W, float H,
                                     float Scale, FLinearColor Colour)
{
	UFont* Font = GEngine ? GEngine->GetLargeFont() : nullptr;
	if (!Font || !Canvas)
	{
		return;
	}
	float TW = 0.0f;
	float TH = 0.0f;
	Canvas->TextSize(Font, Text, TW, TH, Scale, Scale);
	DrawText(Text, Colour, X + (W - TW) * 0.5f, Y + (H - TH) * 0.5f, Font, Scale, false);
}

void ALiquidSimStationHUD::DrawHUD()
{
	Super::DrawHUD();

	ALiquidSimStationDirector* Director = FindDirector();
	if (!Director || Director->Stations.Num() == 0 || !Canvas)
	{
		return;
	}

	ALiquidSimPlayerController* PC = Cast<ALiquidSimPlayerController>(GetOwningPlayerController());
	if (!PC)
	{
		return;
	}

	const float ScreenW = Canvas->SizeX;
	const float ScreenH = Canvas->SizeY;
	const float BarH = ScreenH * BarHeightFrac;
	const float ArrowW = ScreenW * ArrowWidthFrac;
	const float CentreW = ScreenW - ArrowW * 2.0f;
	const float TextScale = FMath::Max(1.0f, BarH / 32.0f);
	const int32 Count = Director->Stations.Num();

	// --- camera gestures ---------------------------------------------------
	// Two fingers always orbit and pinch. On a station with nothing to paint a
	// SINGLE finger orbits too - requiring two there would be ceremony for no
	// reason. On LVL3/4/5 the single finger stays with the brush.
	bool bGestureActive = false;
	if (PC->IsTwoFingerGesture())
	{
		FVector2D GestureCentre;
		float Spread = 0.0f;
		PC->GetGesture(GestureCentre, Spread);

		if (bWasGesture)
		{
			Director->AddOrbitInput(GestureCentre - LastGestureCentre);
			Director->AddZoomInput(Spread - LastGestureSpread);
		}
		LastGestureCentre = GestureCentre;
		LastGestureSpread = Spread;
		bGestureActive = true;
	}
	bWasGesture = bGestureActive;

	// Single-finger orbit. On a painting station the brush owns a finger that
	// is ON the surface, so the orbit takes anything that misses it - the sky
	// around the plane. Without this those three stations had no camera control
	// at all unless you had two fingers, which is impossible with a mouse.
	const bool bSingleOrbitAllowed =
		!Director->IsCurrentInteractive() || !Director->bPointerOnSurface;

	if (!bGestureActive && bSingleOrbitAllowed && !Director->bPickerOpen)
	{
		FVector2D Single;
		if (PC->GetPointer(Single) && Single.Y > BarH)
		{
			if (bWasSingleOrbit)
			{
				Director->AddOrbitInput(Single - LastSinglePos);
				bGestureActive = true;
			}
			LastSinglePos = Single;
			bWasSingleOrbit = true;
		}
		else
		{
			bWasSingleOrbit = false;
		}
	}
	else
	{
		bWasSingleOrbit = false;
	}

	// Mouse wheel zoom - the desktop equivalent of a pinch. The ticks are
	// accumulated by the controller's bound handlers and drained here.
	const float Wheel = PC->ConsumeWheel();
	if (!FMath::IsNearlyZero(Wheel))
	{
		Director->AddZoomInput(Wheel * 110.0f);
	}

	// Mouse equivalent: right-drag orbits. Keeps the build usable on desktop,
	// and lets the emulator - where a mouse arrives as a single finger -
	// exercise the orbit at all.
	const bool bRightDown = PC->IsInputKeyDown(EKeys::RightMouseButton);
	if (bRightDown)
	{
		float MX = 0.0f;
		float MY = 0.0f;
		if (PC->GetMousePosition(MX, MY))
		{
			const FVector2D Now(MX, MY);
			if (bWasRightDown)
			{
				Director->AddOrbitInput(Now - LastRightPos);
			}
			LastRightPos = Now;
			bGestureActive = true;
		}
	}
	bWasRightDown = bRightDown;

	// Painting stands down for the whole gesture.
	Director->bOrbiting = bGestureActive;

	// Consumed for this frame. The paint controllers raise it again during
	// their own tick, which runs before the HUD draws.
	Director->bPointerOnSurface = false;

	// --- pointer for the UI ------------------------------------------------
	float TouchX = 0.0f;
	float TouchY = 0.0f;
	bool bPressed = false;
	{
		FVector2D Pointer;
		if (!bGestureActive && PC->GetPointer(Pointer))
		{
			TouchX = Pointer.X;
			TouchY = Pointer.Y;
			bPressed = true;
		}
	}

	const bool bJustPressed = bPressed && !bWasPressed;
	bWasPressed = bPressed;

	auto Inside = [TouchX, TouchY](float X, float Y, float W, float H)
	{
		return TouchX >= X && TouchX <= X + W && TouchY >= Y && TouchY <= Y + H;
	};

	Director->bInputOverUI = bPressed && (Director->bPickerOpen || Inside(0.0f, 0.0f, ScreenW, BarH));

	// --- expanded list: two columns, so eight entries stay on one screen ----
	if (Director->bPickerOpen)
	{
		DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.62f), 0.0f, 0.0f, ScreenW, ScreenH);

		const int32 Cols = 2;
		const float Pad = ScreenW * 0.015f;
		const float ListW = ScreenW * 0.86f;
		const float ItemW = (ListW - Pad * float(Cols - 1)) / float(Cols);
		const float ItemH = BarH * 0.92f;
		const float ListX = (ScreenW - ListW) * 0.5f;
		const float ListY = BarH + ScreenH * 0.04f;

		for (int32 i = 0; i < Count; ++i)
		{
			const int32 Col = i % Cols;
			const int32 Row = i / Cols;
			const float ItemX = ListX + float(Col) * (ItemW + Pad);
			const float ItemY = ListY + float(Row) * (ItemH + Pad);

			if (bJustPressed && Inside(ItemX, ItemY, ItemW, ItemH))
			{
				Director->SelectStation(i);
				return; // list closed; do not also process the bar this frame
			}
			const bool bCurrent = (i == Director->GetCurrentStation());
			DrawPanel(ItemX, ItemY, ItemW, ItemH, bCurrent);
			DrawLabel(Director->Stations[i].Label, ItemX, ItemY, ItemW, ItemH,
			          TextScale, FLinearColor::White);
		}
	}

	// --- top bar -----------------------------------------------------------
	if (bJustPressed)
	{
		if (Inside(0.0f, 0.0f, ArrowW, BarH))
		{
			Director->PreviousStation();
		}
		else if (Inside(ScreenW - ArrowW, 0.0f, ArrowW, BarH))
		{
			Director->NextStation();
		}
		else if (Inside(ArrowW, 0.0f, CentreW, BarH))
		{
			Director->TogglePicker();
		}
	}

	const int32 Current = Director->GetCurrentStation();
	const FString Name = Director->Stations.IsValidIndex(Current)
		                     ? Director->Stations[Current].Label
		                     : TEXT("-");

	DrawPanel(0.0f, 0.0f, ScreenW, BarH, false);
	DrawLabel(TEXT("<"), 0.0f, 0.0f, ArrowW, BarH, TextScale * 1.3f, FLinearColor::White);
	DrawLabel(Name, ArrowW, 0.0f, CentreW, BarH, TextScale,
	          Director->bPickerOpen ? FLinearColor(0.45f, 0.85f, 1.0f, 1.0f) : FLinearColor::White);
	DrawLabel(TEXT(">"), ScreenW - ArrowW, 0.0f, ArrowW, BarH, TextScale * 1.3f, FLinearColor::White);

	// Progress dots instead of a "(3/8)" counter: position reads at a glance
	// and the title stays uncluttered.
	{
		const float Dot = FMath::Max(3.0f, ScreenH * 0.006f);
		const float Gap = Dot * 2.6f;
		const float TotalW = float(Count) * Gap;
		const float DotY = BarH - Dot * 2.6f;
		for (int32 i = 0; i < Count; ++i)
		{
			const float DotX = (ScreenW - TotalW) * 0.5f + float(i) * Gap;
			const bool bOn = (i == Current);
			DrawRect(bOn ? FLinearColor(0.45f, 0.85f, 1.0f, 1.0f)
			             : FLinearColor(1.0f, 1.0f, 1.0f, 0.28f),
			         DotX, DotY, Dot, Dot);
		}
	}

	// --- one-off controls hint ---------------------------------------------
	if (HintTimer > 0.0f)
	{
		HintTimer -= GetWorld()->GetDeltaSeconds();
		const float Alpha = FMath::Clamp(HintTimer / 1.5f, 0.0f, 1.0f);
		const FString Hint = TEXT("1 finger: paint      2 fingers: orbit / zoom");
		const float HintH = BarH * 0.8f;
		const float HintY = ScreenH - HintH * 1.6f;
		DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.5f * Alpha),
		         ScreenW * 0.16f, HintY, ScreenW * 0.68f, HintH);
		DrawLabel(Hint, ScreenW * 0.16f, HintY, ScreenW * 0.68f, HintH,
		          TextScale * 0.85f, FLinearColor(1.0f, 1.0f, 1.0f, Alpha));
	}
}
