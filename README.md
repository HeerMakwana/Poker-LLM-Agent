# Gemini Poker AI Table

A desktop poker training application powered by Google's Gemini 2.5 Flash AI. Play hands against simulated opponents and get AI-driven decision recommendations based on game state, position, and action history.

## Features

- **AI-Powered Decisions**: Get real-time poker strategy recommendations from Gemini AI
- **Dynamic Position Modeling**: Automatically calculates table position context (2–10 players)
- **Multi-Opponent Support**: Track and log actions for multiple opponents with named selectors
- **Play Blind Mode**: Train by making decisions without seeing your hole cards
- **Real Card Graphics**: Display playing cards with images from the [playing-cards GitHub repo](https://github.com/hanhaechi/playing-cards)
- **Responsive UI**: Scrollable controls, responsive scaling, visible hand log at all window sizes
- **Action History**: AI receives complete opponent action history for better context-aware suggestions
- **Fallback Strategy**: Full game functionality with deterministic fallback logic when Gemini is unavailable

## Requirements

- **Python 3.8+**
- **tkinter** (usually included with Python)
- **urllib** (standard library)
- **google-genai** (Gemini SDK)
- **Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/app/apikey))

## Installation

1. Clone or download this repository.
2. Install dependencies:
   ```bash
   pip install google-genai
   ```
3. Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
   Replace `your_api_key_here` with your actual Gemini API key.

## Usage

### Running the Application

```bash
python gui.py
```

The application will open a desktop window with a poker table interface.

### Game Setup

1. **Players**: Select 2–10 players at the table.
2. **Position**: Choose your seat (e.g., BTN, SB, BB, UTG, etc.).
   - The app automatically displays how many players act before/after you.
3. **Hole Cards**: Enter your two cards (e.g., `Ah Kd`) or leave blank to play blind.
4. **Play Blind**: Check this box to hide your hole cards and make decisions without knowing them.
5. **Initial Pot**: Set the opening pot (default: $15).
6. Click **Start Hand** to begin.

### Game Flow

1. **Opponent Actions**: Select which opponent is acting and their action:
   - Check / Call / Bet or Raise / Fold
   - Specify the amount for calls and raises.
   - Click **Process Opponent** to log the action.

2. **AI Suggestion**: Click **Get AI Suggestion** to receive a recommendation.
   - AI considers your hole cards, position, pot odds, and opponent history.

3. **Your Decision**: Choose your action (Check, Call, Fold, Raise, All-In).

4. **Street Progression**: After betting round closes:
   - Enter community cards for the next street (e.g., `7h Tc 2d` for the flop).
   - Click the corresponding street button (Deal Flop, Deal Turn, Deal River).
   - Repeat opponent actions for the new street.

5. **Showdown**: After the river, click **Showdown** to end the hand and reset for a new one.

### Hand Log

The right panel displays a real-time log of all actions. Scroll to see full history. The log includes:
- Hand start information (position, player count, mode)
- Opponent actions (named, e.g., "Opponent 1 raised to $40")
- Street progressions
- AI suggestions
- Your actions

## File Descriptions

### `gui.py`
Main desktop application using tkinter. Includes:
- Dynamic position modeling by table size
- Multi-opponent action tracking
- Responsive UI with scrollable controls
- Card image rendering and caching
- Game state management (phase, street, pot, stack)

### `agent.py`
Poker AI engine powered by Gemini. Includes:
- `GeminiPokerAgent` class for API communication
- Prompt engineering for poker decision-making
- Response validation and fallback heuristics
- API key loading from environment or `.env` file

## Position & Action Model

### Positions (by Table Size)

| Players | Positions |
|---------|-----------|
| 2 | SB/BTN, BB |
| 3 | BTN, SB, BB |
| 4 | BTN, SB, BB, UTG |
| 5 | BTN, SB, BB, UTG, CO |
| 6 | BTN, SB, BB, UTG, HJ, CO |
| 7+ | Extended (UTG+1, MP, LJ, etc.) |

### Multi-Opponent Tracking

The app supports 2–9 opponents. Each opponent is labeled `Opponent 1`, `Opponent 2`, etc.:
- Actions are logged with opponent names.
- AI receives the last 12 actions for context.
- Reset after each hand.

## AI Context

The AI receives:
- **Hole cards**: Your two cards (or "Unknown" in blind mode)
- **Community cards**: Cards on board for current street
- **Stack size**: Your remaining chips
- **Pot size**: Total money in the pot
- **Amount to call**: Cost to stay in the hand
- **Opponent actions**: History of named opponent actions
- **Table size**: Number of players
- **Your position**: Seat at the table

## Fallback Mode

If Gemini is unavailable (missing API key, SDK not installed, network error):
- The app runs with a simple heuristic strategy.
- All features remain playable.
- Default action: Check if no bet to call, Call if small bet (≤ 25% pot), Fold if large bet.

## Troubleshooting

### "Gemini unavailable (.env missing key)"
- Create a `.env` file in the project root with your API key:
  ```
  GEMINI_API_KEY=your_key_here
  ```

### "Gemini unavailable (fallback mode)"
- Your API key may be invalid, expired, or blocked.
- Check your key in [Google AI Studio](https://aistudio.google.com/app/apikey).
- Ensure your network allows outbound HTTPS requests.

### Card images not loading
- The app will attempt to download card images from GitHub on first use.
- They are cached locally in `assets/cards/`.
- Ensure your internet connection is stable for first-time card fetch.

### Hand log not visible
- The log resizes with window height.
- Scroll within the right panel to see all game history.

## Future Enhancements

- Turn order enforcement (pre-flop action sequence validation)
- Hand strength evaluation (rank hole cards at showdown)
- Chip equity calculation
- Session history export (JSON/CSV)
- Keyboard shortcuts for faster gameplay
- Animated pot and chip movement
- Hand strength odds display

## License

This project is provided as-is for educational and training purposes.

## Acknowledgments

- **Card Graphics**: [hanhaechi/playing-cards](https://github.com/hanhaechi/playing-cards)
- **AI Engine**: Google's [Gemini 2.5 Flash](https://ai.google.dev/)

## Support

For issues, questions, or suggestions, please refer to the code comments or create an issue in the repository.

---

**Play smart. Train with AI. Master poker strategy.**
